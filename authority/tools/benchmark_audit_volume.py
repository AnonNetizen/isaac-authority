"""Same-binary raw/packed comparison with complete canonical audit equality."""
import argparse,sys,json,os,time,hashlib,copy
from pathlib import Path
sys.dont_write_bytecode=True
import benchmark_audit_batch as base
import run_audit_volume_gate as experiment
from init_profile_page import ProfilePage
from audit_wire import prefix
gate=experiment.gate
def run(out,accepted_path):
    accepted=json.loads(accepted_path.read_text())
    if not accepted['passed'] or not accepted['complete_manifest'] or accepted['dll_sha256']!=gate.digest(gate.DLL) or not accepted['audit_batch_close_verified']:raise RuntimeError('Current packed model gate required')
    out.mkdir(parents=True,exist_ok=False);spec=json.loads(gate.MANIFEST.read_text());rows=[];started=time.perf_counter();before=gate.protected();names=['root-128','graph-churn-16','dual-config-2']
    keys=['IA_AUDIT_WIRE_RAW','IA_AUDIT_IMMEDIATE','IA_INIT_PROFILE','IA_INIT_PRESENCE_VERIFY','IA_INIT_LEGACY_PRESENCE','IA_INIT_LEGACY_EVIDENCE','IA_INIT_EVIDENCE_COLLISION','IA_CONSUMER_VERIFY'];prior={k:os.environ.get(k) for k in keys}
    try:
        for name in names:
            case=next(c for c in spec['cases'] if c['id']==name)
            for repeat in range(2):
                for mode in (['raw','packed'] if repeat==0 else ['packed','raw']):
                    remaining=45-(time.perf_counter()-started)
                    if remaining<=0:raise RuntimeError('Volume benchmark deadline')
                    for key in keys:os.environ.pop(key,None)
                    page=ProfilePage();os.environ['IA_INIT_PROFILE']=page.name;os.environ['IA_CONSUMER_VERIFY']='1'
                    if mode=='raw':os.environ['IA_AUDIT_WIRE_RAW']='1'
                    try:r,a,j=base.raw_invoke(case,mode+'-'+str(repeat),gate.DLL,out,min(5,remaining));profile=page.read()
                    finally:page.close()
                    if r.get('process_failure'):raise RuntimeError('Bounded volume benchmark failed: '+str(a))
                    metrics=gate.compact_metrics(r);m=r['compact_storage']['journal'];decoded=prefix(j)
                    if decoded['tail_error'] or not m['sealed'] or m['pending_bytes'] or m['bytes']!=m['durable_bytes'] or metrics['all_execution_journal_reads']!=0 or not profile or not profile['work_accounting_valid']:raise RuntimeError('Packed integrity/close/read/accounting failure')
                    proof=hashlib.sha256(json.dumps(gate.canonical(copy.deepcopy(r)),sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    rows.append({'id':name,'mode':mode,'repeat':repeat,'seconds':a['seconds'],'budget':r['budget'],'metrics':metrics,'journal':m,'decoded_prefix':decoded,'proof_sha256':proof,'file_sha256':gate.digest(j),'profile':profile})
                    if j.is_symlink() or j.resolve().parent!=out.resolve():raise RuntimeError('Benchmark cleanup escaped')
                    j.unlink();gate.save(out/'progress.json',{'rows':rows})
    finally:
        for key,value in prior.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    checks=[]
    for name in names:
        rs=[r for r in rows if r['id']==name];checks.append({'id':name,'proof_equal':len({r['proof_sha256'] for r in rs})==1,'decoded_audit_byte_equal':len({r['decoded_prefix']['canonical_sha256'] for r in rs})==1})
    result={'schema':'audit-volume-benchmark-1','passed':all(c['proof_equal'] and c['decoded_audit_byte_equal'] for c in checks) and before==gate.protected(),'rows':rows,'checks':checks,'seconds':time.perf_counter()-started,'work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':45,'dll_sha256':gate.digest(gate.DLL),'exe_sha256':gate.digest(gate.EXE),'manifest_sha256':gate.digest(gate.MANIFEST),'preserved_files_unchanged':before==gate.protected(),'timing_includes_flush_export_decode':True,'small_sample':True};gate.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps({'passed':result['passed'],'runs':len(rows),'seconds':result['seconds']}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.output.resolve(),a.gate.resolve())['passed'] else 1)
