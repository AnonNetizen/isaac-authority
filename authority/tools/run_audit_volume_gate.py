"""Keep the frozen model contract and parent runtime intact."""
import argparse,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_audit_batch_gate as base
from read_volume_audit import read as volume_decode
gate=base.gate;ROOT=gate.ROOT
gate.DLL=ROOT/'build-audit-volume/Release/ia_lua533_audit_volume.dll';gate.EXE=gate.DLL.with_name('authority-audit-volume.exe');gate.OLD=ROOT/'build-audit-batch/Release/ia_lua533_audit_batch.dll'
parent_protected=gate.protected
def protected():
    result=parent_protected()
    for folder in ['audit_batch_runtime','build-audit-batch/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='audit_batch_runtime' or p.suffix in ['.dll','.exe','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    return result
gate.protected=protected
def decode(path):
    result=volume_decode(path);name=path.name.removesuffix('-candidate-1.audit');expected=base.previous.previous.CAPTURED.get((name,'candidate-1'),{}).get('consumer')
    if expected is not None and result['consumer_records']!=expected['records']:raise RuntimeError('Packed consumer independent audit mismatch')
    return result
gate.decode=decode
def run(out,journal_gate,only,wire_gate):
    accepted=json.loads(journal_gate.read_text())
    if not accepted['passed'] or len(accepted['cases'])!=23 or accepted['exe_sha256']!=gate.digest(gate.DLL.with_name('authority-audit-volume-tests.exe')):raise RuntimeError('Current explicit quota and recovery gate required')
    wire=json.loads(wire_gate.read_text())
    if not wire['passed'] or wire['exe_sha256']!=gate.digest(gate.DLL.with_name('authority-audit-wire-tests.exe')):raise RuntimeError('Current codec and encoded recovery gate required')
    prior={key:os.environ.pop(key,None) for key in ['IA_AUDIT_IMMEDIATE','IA_AUDIT_WIRE_RAW']}
    try:r=base.previous.run(out,only)
    finally:
        for key,value in prior.items():
            if value is not None:os.environ[key]=value
    r['schema']='audit-volume-model-gate-1';r['journal_gate_sha256']=gate.digest(journal_gate)
    r['wire_gate_sha256']=gate.digest(wire_gate)
    r['close_checks']=[{'id':c['id'],**base.CLOSED[(c['id'],'candidate-1')]} for c in r['cases'] if (c['id'],'candidate-1') in base.CLOSED]
    r['audit_batch_close_verified']=bool(r['close_checks']) and all(c['passed'] for c in r['close_checks']);r['passed']=r['passed'] and r['audit_batch_close_verified'];gate.save(out/'result.json',r);return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--journal-gate',type=Path,required=True);p.add_argument('--wire-gate',type=Path,required=True);p.add_argument('--case',action='append');a=p.parse_args();sys.exit(0 if run(a.output.resolve(),a.journal_gate.resolve(),a.case,a.wire_gate.resolve())['passed'] else 1)
