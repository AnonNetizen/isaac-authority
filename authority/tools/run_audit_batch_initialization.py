"""Real source initialization only after integrity/recovery and short benchmarks."""
import argparse,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import profile_initialization as previous
from init_profile_page import ProfilePage
from bounded_profile_child import collect
ROOT=previous.ROOT
previous.DLL=ROOT/'build-audit-batch/Release/ia_lua533_audit_batch.dll';previous.EXE=previous.DLL.with_name('authority-audit-batch-real.exe')
def invoke(case,out,label='measured',legacy=False,legacy_evidence=False):
    page=ProfilePage();journal=out/(case+'-'+label+'.audit');env=os.environ.copy();env['IA_INIT_PROFILE']=page.name;env['IA_COMPACT_AUDIT_FILE']=str(journal)
    for key in ['IA_AUDIT_IMMEDIATE','IA_INCREMENTAL_VERIFY','IA_CONSUMER_VERIFY','IA_INIT_PRESENCE_VERIFY','IA_INIT_LEGACY_PRESENCE','IA_INIT_LEGACY_EVIDENCE','IA_INIT_EVIDENCE_COLLISION']:env.pop(key,None)
    command=[str(previous.EXE),'--suite',str(previous.DLL),previous.digest(previous.DLL),str(ROOT),str(previous.MANIFEST),case,'trace']
    try:child=collect(command,env,page)
    finally:page.close()
    if child['output_limit_exceeded']:raise RuntimeError('Initialization exceeded bounded output capture')
    stdout=child.pop('stdout');stderr=child.pop('stderr').decode('utf-8',errors='replace');points=child['progress']
    result={'id':case,**child,'last_profile':points[-1] if points else None,'stderr_tail':stderr[-8192:],'stdout_bytes':len(stdout),'timeout_seconds':5,'work_limit':10000000,'report':json.loads(stdout) if child['returncode']==0 else None,'output_collector':'concurrent-bounded-pipes-1'}
    if journal.exists():
        if journal.stat().st_size>16*1024*1024:raise RuntimeError('Audit quota exceeded')
        result['audit_prefix']=previous.prefix(journal);result['audit_sha256']=previous.digest(journal);journal.unlink()
    previous.save(out/(case+'.json'),result);print(json.dumps({'id':case,'timed_out':result['timed_out'],'seconds':result['seconds'],'first_unsupported':(result['report'] or {}).get('case',{}).get('first_unsupported_entry')}),flush=True);return result
previous.invoke=invoke
def run(out,gate_path,bench_path):
    gate=json.loads(gate_path.read_text(encoding='utf-8'));bench=json.loads(bench_path.read_text(encoding='utf-8'));expected=previous.digest(previous.DLL)
    if not gate['passed'] or not gate['complete_manifest'] or not gate['audit_batch_close_verified'] or not bench['passed'] or gate['dll_sha256']!=expected or bench['dll_sha256']!=expected:raise RuntimeError('Current integrity/recovery/model/performance gates must pass before real initialization')
    old=os.environ.pop('IA_AUDIT_IMMEDIATE',None)
    try:result=previous.run(out,None)
    finally:
        if old is not None:os.environ['IA_AUDIT_IMMEDIATE']=old
    result['schema']='audit-batch-initialization-1';result['model_gate_sha256']=previous.digest(gate_path);result['benchmark_sha256']=previous.digest(bench_path);result['batch_capacity']=262144
    result['compatibility_passed']=all((r.get('report') or {}).get('case',{}).get('compatibility_passed') is True for r in result['cases'])
    previous.save(out/'result.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);p.add_argument('--benchmark',type=Path,required=True);a=p.parse_args();run(a.output.resolve(),a.gate.resolve(),a.benchmark.resolve())
