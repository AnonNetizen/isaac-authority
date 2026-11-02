"""Run unchanged 37-case model gate only after bounded Journal recovery tests."""
import argparse,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_init_profile_gate as previous
gate=previous.gate;ROOT=gate.ROOT
gate.DLL=ROOT/'build-audit-batch/Release/ia_lua533_audit_batch.dll';gate.EXE=gate.DLL.with_name('authority-audit-batch.exe')
gate.OLD=ROOT/'build-init-profile/Release/ia_lua533_init_profile.dll'
parent_protected=gate.protected
def protected():
    result=parent_protected()
    for folder in ['init_profile_runtime','build-init-profile/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='init_profile_runtime' or p.suffix in ['.dll','.exe','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    return result
gate.protected=protected
CLOSED={}
parent_invoke=gate.invoke
def invoke(case,label,dll,out,timeout):
    report,artifact,journal=parent_invoke(case,label,dll,out,timeout)
    if dll==gate.DLL and not report.get('process_failure'):
        metrics=(report.get('compact_storage') or {}).get('journal') or {}
        CLOSED[(case['id'],label)]={'metrics':metrics,'passed':metrics.get('sealed') is True and metrics.get('complete') is True and metrics.get('pending_bytes')==0 and metrics.get('bytes')==metrics.get('durable_bytes')}
    return report,artifact,journal
gate.invoke=invoke
def run(out,journal_gate,only):
    accepted=json.loads(journal_gate.read_text(encoding='utf-8'))
    if not accepted['passed'] or len(accepted['cases'])!=20 or accepted['exe_sha256']!=gate.digest(gate.DLL.with_name('authority-audit-journal-tests.exe')):raise RuntimeError('Current bounded Journal recovery gate must pass first')
    prior=os.environ.pop('IA_AUDIT_IMMEDIATE',None)
    try:result=previous.run(out,only)
    finally:
        if prior is not None:os.environ['IA_AUDIT_IMMEDIATE']=prior
    result['schema']='audit-batch-model-gate-1';result['journal_gate_sha256']=gate.digest(journal_gate)
    result['close_checks']=[{'id':row['id'],**CLOSED[(row['id'],'candidate-1')]} for row in result['cases'] if (row['id'],'candidate-1') in CLOSED]
    result['audit_batch_close_verified']=all(row['passed'] for row in result['close_checks']) and bool(result['close_checks'])
    result['passed']=result['passed'] and result['audit_batch_close_verified']
    gate.save(out/'result.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--journal-gate',type=Path,required=True);p.add_argument('--case',action='append');a=p.parse_args();sys.exit(0 if run(a.output.resolve(),a.journal_gate.resolve(),a.case)['passed'] else 1)
