"""Original Journal recovery cases plus explicit record/file quota classification."""
import argparse,json,sys,os
from pathlib import Path
sys.dont_write_bytecode=True
import run_audit_journal_tests as base
ROOT=base.ROOT
base.EXE=ROOT/'build-audit-volume/Release/authority-audit-volume-tests.exe';base.MANIFEST=ROOT/'research/audit_volume_journal_v1.json'
def freeze():
    spec={'schema':'audit-volume-journal-1','work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':60,'buffer_capacity':262144,'harness_sha256':base.digest(ROOT/'audit_batch_runtime/journal_tests.cpp'),'derived_harness_sha256':base.digest(ROOT/'build-audit-volume/generated/volume_journal_tests.cpp'),'cases':[{'id':n,'exit':73 if n=='kill-pending' else 0} for n in base.NAMES+['record-limit','exact-file-quota','both-limits']]}
    if base.MANIFEST.exists():
        if json.loads(base.MANIFEST.read_text())!=spec:raise RuntimeError('Frozen volume manifest differs')
    else:base.save(base.MANIFEST,spec)
def run(out):
    spec=json.loads(base.MANIFEST.read_text());assert spec['derived_harness_sha256']==base.digest(ROOT/'build-audit-volume/generated/volume_journal_tests.cpp')
    prior=os.environ.get('IA_AUDIT_WIRE_RAW');os.environ['IA_AUDIT_WIRE_RAW']='1'
    try:result=base.run(out)
    finally:
        if prior is None:os.environ.pop('IA_AUDIT_WIRE_RAW',None)
        else:os.environ['IA_AUDIT_WIRE_RAW']=prior
    result['schema']='audit-volume-journal-gate-1';result['wire_mode']='raw';checks=[]
    for row in result['cases']:
        value=(row.get('report') or {}).get('result',{});m=value.get('metrics',value if 'volume' in value else {})
        if 'volume' not in m:continue
        volume=m['volume'];valid=volume['accepted_records']==m['records'] and volume['accepted_payload_bytes']+volume['accepted_header_bytes']==m['bytes']
        checks.append({'id':row['id'],'passed':valid})
    result['volume_checks']=checks;result['passed']=result['passed'] and all(c['passed'] for c in checks);base.save(out/'result.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve())['passed'] else 1)
