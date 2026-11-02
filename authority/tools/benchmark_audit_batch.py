"""Same binary immediate/buffered comparison, bounded children and exact audits."""
import argparse,copy,hashlib,json,os,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_audit_batch_gate as experiment
from init_profile_page import ProfilePage
gate=experiment.gate;raw_invoke=experiment.previous.previous.old_invoke
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run(out,accepted_path):
    accepted=json.loads(accepted_path.read_text(encoding='utf-8'))
    if not accepted['passed'] or not accepted['complete_manifest'] or accepted['dll_sha256']!=gate.digest(gate.DLL) or not accepted['audit_batch_close_verified']:raise RuntimeError('Complete current batch model gate must pass first')
    out.mkdir(parents=True,exist_ok=False);spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'));names=['root-128','graph-churn-16','dual-config-2'];rows=[];started=time.perf_counter();before=gate.protected()
    keys=['IA_AUDIT_IMMEDIATE','IA_INIT_PROFILE','IA_INIT_PRESENCE_VERIFY','IA_INIT_LEGACY_PRESENCE','IA_INIT_LEGACY_EVIDENCE','IA_INIT_EVIDENCE_COLLISION','IA_CONSUMER_VERIFY'];prior={k:os.environ.get(k) for k in keys}
    try:
        for name in names:
            case=next(c for c in spec['cases'] if c['id']==name)
            for repeat in range(2):
                for mode in (['immediate','batch'] if repeat==0 else ['batch','immediate']):
                    remaining=45-(time.perf_counter()-started)
                    if remaining<=0:raise RuntimeError('Batch benchmark deadline reached')
                    for key in keys:os.environ.pop(key,None)
                    page=ProfilePage();os.environ['IA_INIT_PROFILE']=page.name;os.environ['IA_CONSUMER_VERIFY']='1'
                    if mode=='immediate':os.environ['IA_AUDIT_IMMEDIATE']='1'
                    try:r,a,j=raw_invoke(case,mode+'-'+str(repeat),gate.DLL,out,min(5,remaining));profile=page.read()
                    finally:page.close()
                    if r.get('process_failure'):raise RuntimeError('Bounded batch benchmark failed: '+str(a))
                    m=r['compact_storage']['journal'];metrics=gate.compact_metrics(r)
                    if not m['sealed'] or m['pending_bytes'] or m['durable_bytes']!=m['bytes'] or metrics['all_execution_journal_reads']!=0 or not profile or not profile['work_accounting_valid']:raise RuntimeError('Audit commit/read/accounting regression')
                    row={'id':name,'mode':mode,'repeat':repeat,'seconds':a['seconds'],'metrics':metrics,'journal':m,'budget':r['budget'],'profile':profile,'proof_sha256':fingerprint(gate.canonical(copy.deepcopy(r))),'audit_sha256':gate.digest(j)}
                    if j.is_symlink() or j.resolve().parent!=out.resolve():raise RuntimeError('Benchmark cleanup target escaped')
                    j.unlink();rows.append(row);gate.save(out/'progress.json',{'rows':rows})
    finally:
        for key,value in prior.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    checks=[]
    for name in names:
        values=[r for r in rows if r['id']==name];checks.append({'id':name,'proof_equal':len({r['proof_sha256'] for r in values})==1,'audit_byte_equal':len({r['audit_sha256'] for r in values})==1})
    result={'schema':'audit-batch-benchmark-1','passed':all(c['proof_equal'] and c['audit_byte_equal'] for c in checks) and before==gate.protected(),'rows':rows,'checks':checks,'seconds':time.perf_counter()-started,'work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':45,'dll_sha256':gate.digest(gate.DLL),'exe_sha256':gate.digest(gate.EXE),'manifest_sha256':gate.digest(gate.MANIFEST),'preserved_files_unchanged':before==gate.protected(),'small_sample_not_statistical_claim':True,'primary_timing':'whole child wall time, including phase flushes and diagnostic export'}
    gate.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps({'passed':result['passed'],'runs':len(rows),'seconds':result['seconds']}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.output.resolve(),a.gate.resolve())['passed'] else 1)
