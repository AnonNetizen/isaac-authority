"""Bounded lifecycle checks, unchanged model regression, then short real probes."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_audit_volume_gate as parent
from read_volume_audit import read as decode
from audit_wire import prefix
from init_profile_page import ProfilePage
from bounded_profile_child import collect
gate=parent.gate;ROOT=gate.ROOT
BIN=ROOT/'build-evidence-lifetime/Release'
DLL=BIN/'ia_lua533_evidence_lifetime.dll';EXE=BIN/'authority-evidence-lifetime.exe'
gate.DLL=DLL;gate.EXE=EXE;gate.OLD=ROOT/'build-audit-volume/Release/ia_lua533_audit_volume.dll'
old_protected=gate.protected
def protected():
    result=old_protected()
    for folder in ['audit_volume_runtime','build-audit-volume/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file():result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    return result
gate.protected=protected

def logical_events(inc):
    definitions=inc.get('cache_descriptors',[]);result=[]
    for number,(descriptor,epoch,site,before,after) in enumerate(inc.get('cache_uses',[]),1):
        if descriptor<1 or descriptor>len(definitions):raise RuntimeError('Unknown reconstructed descriptor')
        value=copy.deepcopy(definitions[descriptor-1]);value.update(event=number,epoch=epoch)
        if site:value['site_ref']=site
        if before!=-1:value.update(logical_walk_before=before,logical_walk_after=after)
        result.append(value)
    return result

old_canonical=gate.canonical
def canonical(report):
    value=old_canonical(report);inc=value.get('cache_evidence')
    if inc:
        inc['logical_events_expanded']=logical_events(inc)
        inc.pop('cache_descriptors',None);inc.pop('cache_uses',None)
        encoding=inc.get('evidence_encoding',{})
        # Encoding policy can vary; do not remove semantic object certificates,
        # completed event numbers, epochs, control/data graph or logical events.
        inc['evidence_encoding']={k:encoding.get(k) for k in ['logical_events','every_logical_use_charged','first_fault']}
    return value
gate.canonical=canonical
def baseline_equal(first,old):
    if first['id']=='consumer-poison':return gate.ordinary(first)==gate.ordinary(old)
    return canonical(copy.deepcopy(first))==canonical(copy.deepcopy(old))
gate.baseline_equal=baseline_equal
old_invoke=gate.invoke
def hydrate(report,journal):
    inc=report.get('trace',{}).get('incremental')
    if inc and inc.get('evidence_encoding',{}).get('history_streamed'):
        data=decode(journal)
        for key in ['cache_descriptors','cache_uses','cache_sites']:
            if inc[key]:raise RuntimeError('Stream mode unexpectedly retained history export')
            inc[key]=data[key]
        if len(inc['cache_uses'])!=inc['evidence_encoding']['logical_events']:raise RuntimeError('Logical use loss')
    return report
def invoke(case,label,dll,out,timeout):
    report,artifact,journal=old_invoke(case,label,dll,out,min(5,timeout))
    if dll==DLL:artifact['runtime_profile']=parent.base.previous.PAGES.get((case['id'],label))
    if not report.get('process_failure') and journal.exists():
        started=time.perf_counter();hydrate(report,journal);artifact['offline_reconstruction_seconds']=time.perf_counter()-started
    return report,artifact,journal
gate.invoke=invoke

def storage(out):
    out.mkdir(exist_ok=False,parents=True);exe=BIN/'authority-evidence-lifetime-storage.exe';rows=[];start=time.perf_counter()
    names=['repeat-32','repeat-4096','repeat-65536','churn','collision','retired-reference','collect-regenerate','append-failure','quota-before-use','budget','oversize','site-stream']
    for name in names:
        if time.perf_counter()-start>45:raise RuntimeError('Storage batch deadline')
        case=out/name;case.mkdir();p=subprocess.run([str(exe),name,str(case)],capture_output=True,timeout=5)
        value=json.loads(p.stdout) if p.returncode==0 else None
        row={'id':name,'returncode':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace'),'report':value}
        row['passed']=p.returncode==0 and value['passed'] and value['limit']==10000000 and value['work']<=10000000 and value['work_sum_valid']
        journal=case/'events.audit'
        if journal.exists():
            row['prefix']=prefix(journal);row['sha256']=gate.digest(journal)
            if name not in ['append-failure','quota-before-use','budget','retired-reference']:
                data=decode(journal);row['logical_events']=len(logical_events(data));row['passed']=row['passed'] and row['prefix']['tail_error'] is None
            if row['passed']:
                if journal.is_symlink() or journal.resolve().parent!=case.resolve():raise RuntimeError('Unsafe storage audit path')
                journal.unlink();case.rmdir()
        rows.append(row);gate.save(out/'progress.json',{'cases':rows});print(json.dumps({'storage':name,'passed':row['passed'],'stderr':row['stderr']}),flush=True)
        if not row['passed']:break
    result={'schema':'evidence-lifetime-storage-1','passed':len(rows)==len(names) and all(c['passed'] for c in rows),'cases':rows,'exe_sha256':gate.digest(exe),'work_limit':10000000,'case_timeout_seconds':5,'seconds':time.perf_counter()-start}
    gate.save(out/'result.json',result)
    if result['passed']:(out/'progress.json').unlink()
    return result

def model(out,storage_gate):
    accepted=json.loads(storage_gate.read_text(encoding='utf-8'))
    if not accepted['passed'] or accepted['exe_sha256']!=gate.digest(BIN/'authority-evidence-lifetime-storage.exe'):raise RuntimeError('Current storage gate required')
    result=parent.base.previous.run(out,None)
    result['schema']='evidence-lifetime-model-1';result['storage_gate_sha256']=gate.digest(storage_gate)
    result['evidence_proof']='exact expanded logical events, observations, value/control graph and active certificates; encoding IDs separate'
    checks=[]
    import gzip
    for row in result['cases']:
        with gzip.open(out/(row['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:r=json.load(f)
        stats=r.get('execution_before_diagnostics',{}).get('evidence_lifetime')
        if stats:
            valid=not stats['keep_history'] and stats['resident_use_slots']<=1 and stats['resident_entries']<=8192 and stats['accounted_resident_bytes']<=8388608
            checks.append({'id':row['id'],'passed':valid,'stats':stats})
    result['lifetime_checks']=checks;result['passed']=result['passed'] and all(c['passed'] for c in checks)
    gate.save(out/'result.json',result);return result

def benchmark(out,model_gate):
    accepted=json.loads(model_gate.read_text(encoding='utf-8'))
    if not accepted['passed'] or not accepted['complete_manifest'] or accepted['dll_sha256']!=gate.digest(DLL):raise RuntimeError('Current complete model gate required')
    out.mkdir(exist_ok=False,parents=True);rows=[];start=time.perf_counter();before=protected()
    spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'))
    env_keys=['IA_EVIDENCE_KEEP_HISTORY','IA_INIT_PROFILE','IA_CONSUMER_VERIFY','IA_INCREMENTAL_VERIFY','IA_INIT_EVIDENCE_COLLISION']
    previous={k:os.environ.get(k) for k in env_keys}
    try:
        for name in ['root-128','graph-churn-16','dual-config-2']:
            case=next(c for c in spec['cases'] if c['id']==name)
            for repeat in range(2):
                for mode in (['retained','streamed'] if repeat==0 else ['streamed','retained']):
                    if time.perf_counter()-start>45:raise RuntimeError('Benchmark batch deadline')
                    for k in env_keys:os.environ.pop(k,None)
                    if mode=='retained':os.environ['IA_EVIDENCE_KEEP_HISTORY']='1'
                    os.environ['IA_CONSUMER_VERIFY']='1'
                    report,artifact,journal=invoke(case,mode+'-'+str(repeat),DLL,out,5);profile=artifact.get('runtime_profile')
                    if report.get('process_failure'):raise RuntimeError('Benchmark process failed: '+str(artifact))
                    value=report['compact_storage']['journal'];p=prefix(journal);stats=report['execution_before_diagnostics']['evidence_lifetime']
                    passed=value['complete'] and value['sealed'] and value['reads']==report['execution_after_diagnostics']['journal_reads'] and report['execution_before_diagnostics']['journal_reads']==0 and p['tail_error'] is None and profile and profile['work_accounting_valid']
                    row={'id':name,'mode':mode,'repeat':repeat,'seconds':artifact['seconds'],'offline_seconds':artifact.get('offline_reconstruction_seconds'),'work':report['budget']['used'],'stats':stats,'profile':profile,'proof_sha256':hashlib.sha256(json.dumps(canonical(copy.deepcopy(report)),sort_keys=True,separators=(',',':')).encode()).hexdigest(),'prefix':p,'passed':bool(passed)}
                    rows.append(row);gate.save(out/'progress.json',{'rows':rows});journal.unlink()
    finally:
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    checks=[{'id':name,'proof_equal':len({r['proof_sha256'] for r in rows if r['id']==name})==1} for name in ['root-128','graph-churn-16','dual-config-2']]
    result={'schema':'evidence-lifetime-benchmark-1','passed':all(c['proof_equal'] for c in checks) and all(r['passed'] for r in rows) and before==protected(),'rows':rows,'checks':checks,'dll_sha256':gate.digest(DLL),'exe_sha256':gate.digest(EXE),'work_limit':10000000,'case_timeout_seconds':5,'seconds':time.perf_counter()-start,'small_sample':True}
    gate.save(out/'result.json',result);(out/'progress.json').unlink();return result

def eviction(out,model_gate,entries=8):
    accepted=json.loads(model_gate.read_text(encoding='utf-8'))
    if not accepted['passed'] or not accepted['complete_manifest'] or accepted['dll_sha256']!=gate.digest(DLL):raise RuntimeError('Current complete model gate required')
    out.mkdir(exist_ok=False,parents=True);spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'));rows=[];started=time.perf_counter()
    previous=os.environ.get('IA_EVIDENCE_CACHE_ENTRIES');os.environ['IA_EVIDENCE_CACHE_ENTRIES']=str(entries)
    try:
        for name in ['leaf-128','graph-churn-16','legacy-closed-shared-upvalue','consumer-history-timepoint','dual-config-2']:
            if time.perf_counter()-started>45:raise RuntimeError('Eviction gate batch deadline')
            case=copy.deepcopy(next(c for c in spec['cases'] if c['id']==name));case['verify_full_origins']=True
            results=[];artifacts=[]
            for label,dll in [('evicted-1',DLL),('baseline',gate.OLD),('evicted-2',DLL)]:
                r,a,j=invoke(case,label,dll,out,5)
                if r.get('process_failure'):raise RuntimeError('Eviction execution failed: '+str(a))
                data=prefix(j);value={'proof':hashlib.sha256(json.dumps(canonical(copy.deepcopy(r)),sort_keys=True,separators=(',',':')).encode()).hexdigest(),'ordinary':gate.ordinary(r),'stats':r['execution_before_diagnostics'].get('evidence_lifetime'),'execution_reads':r['execution_before_diagnostics']['journal_reads'],'cache_hit_reads':r['execution_before_diagnostics'].get('cache_hit_history_reads'),'prefix':data}
                results.append(value);artifacts.append(a);j.unlink()
            live=results[0]['stats'];passed=len({r['proof'] for r in results})==1 and all(r['execution_reads']==0 and r['cache_hit_reads']==0 and r['prefix']['tail_error'] is None for r in results) and live['resident_entries']<=entries and live['resident_use_slots']<=1
            if results[1]['prefix']['channels'].get('8',0)>entries:passed=passed and live['evictions']>0
            rows.append({'id':name,'passed':bool(passed),'results':results,'artifacts':artifacts});gate.save(out/'progress.json',{'cases':rows})
            print(json.dumps({'eviction':name,'passed':bool(passed),'evictions':live['evictions']}),flush=True)
    finally:
        if previous is None:os.environ.pop('IA_EVIDENCE_CACHE_ENTRIES',None)
        else:os.environ['IA_EVIDENCE_CACHE_ENTRIES']=previous
    result={'schema':'evidence-lifetime-eviction-1','passed':all(r['passed'] for r in rows),'cases':rows,'cache_entries':entries,'work_limit':10000000,'case_timeout_seconds':5,'seconds':time.perf_counter()-started,'dll_sha256':gate.digest(DLL),'frozen_manifest_sha256':gate.digest(gate.MANIFEST)}
    gate.save(out/'result.json',result);(out/'progress.json').unlink();return result

def initialization(out,model_gate,benchmark_gate,eviction_gate):
    gates=[json.loads(p.read_text(encoding='utf-8')) for p in [model_gate,benchmark_gate,eviction_gate]]
    if not all(g['passed'] and g['dll_sha256']==gate.digest(DLL) for g in gates) or not gates[0]['complete_manifest']:raise RuntimeError('Current complete short gates required before real probes')
    import run_audit_batch_initialization as real
    real.previous.DLL=DLL;real.previous.EXE=BIN/'authority-evidence-lifetime-real.exe';real.previous.prefix=prefix
    before=protected();result=real.previous.run(out,None)
    result['schema']='evidence-lifetime-real-1';result['preserved_formal_files_unchanged']=before==protected()
    result['compatibility_passed']=all((c.get('report') or {}).get('case',{}).get('compatibility_passed') is True for c in result['cases'])
    result['passed']=result['compatibility_passed'] and result['preserved_formal_files_unchanged'] and result['save_files_unchanged'] and result['frozen_sources_unchanged']
    result['accepted_gate_sha256']=[gate.digest(p) for p in [model_gate,benchmark_gate,eviction_gate]]
    gate.save(out/'result.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['storage','model','benchmark','eviction','initialization']);p.add_argument('--output',required=True,type=Path);p.add_argument('--gate',type=Path);p.add_argument('--cache-entries',type=int,default=8);p.add_argument('--benchmark',type=Path);p.add_argument('--eviction',type=Path);a=p.parse_args()
    if a.phase=='storage':r=storage(a.output.resolve())
    elif a.phase=='model':r=model(a.output.resolve(),a.gate.resolve())
    elif a.phase=='eviction':r=eviction(a.output.resolve(),a.gate.resolve(),a.cache_entries)
    elif a.phase=='initialization':r=initialization(a.output.resolve(),a.gate.resolve(),a.benchmark.resolve(),a.eviction.resolve())
    else:r=benchmark(a.output.resolve(),a.gate.resolve())
    print(json.dumps({'phase':a.phase,'passed':r['passed'],'seconds':r['seconds']}));sys.exit(0 if r['passed'] else 1)
