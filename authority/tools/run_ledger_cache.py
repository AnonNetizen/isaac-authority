"""Exact accounting gate, unchanged model proof, then bounded initialization."""
import argparse,copy,gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_evidence_lifetime as parent
from init_profile_page import ProfilePage
from audit_wire import prefix
gate=parent.gate;ROOT=gate.ROOT
BIN=ROOT/'build-ledger-cache/Release'
DLL=BIN/'ia_lua533_ledger_cache.dll';EXE=BIN/'authority-ledger-cache.exe'
parent.BIN=BIN;parent.DLL=DLL;parent.EXE=EXE
gate.DLL=DLL;gate.EXE=EXE;gate.OLD=ROOT/'build-evidence-lifetime/Release/ia_lua533_evidence_lifetime.dll'
old_protected=gate.protected
def protected():
    result=old_protected()
    for folder in ['evidence_lifetime_runtime','build-evidence-lifetime/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file():result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    return result
gate.protected=protected
parent.protected=protected
BUDGETS={}
old_invoke=gate.invoke
def invoke(case,label,dll,out,timeout):
    report,artifact,journal=old_invoke(case,label,dll,out,min(5,timeout))
    BUDGETS[(case['id'],label)]=copy.deepcopy(report.get('budget'))
    return report,artifact,journal
gate.invoke=invoke

def native(out):
    out.mkdir(parents=True,exist_ok=False);rows=[];started=time.perf_counter();exe=BIN/'authority-ledger-tests.exe'
    env=os.environ.copy();env.pop('IA_LEDGER_LEGACY_LOOKUP',None)
    names=['repeat','mutable-address','equal-bytes','collision','many-labels','zero-empty-long','exact-limit','oversize','context-isolation','mirror-sequence','mirror-refusal']
    for name in names:
        p=subprocess.run([str(exe),name],capture_output=True,env=env,timeout=5)
        row={'id':name,'returncode':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace'),'report':json.loads(p.stdout) if p.returncode==0 else None}
        row['passed']=p.returncode==0 and row['report']['passed'] and row['report']['limit']==10000000 and row['report']['cache_bytes']==4096
        rows.append(row);gate.save(out/'progress.json',{'cases':rows})
        if not row['passed']:break
    timings=[]
    if all(r['passed'] for r in rows):
        for repeat in range(2):
            for mode in (['legacy','cached'] if repeat==0 else ['cached','legacy']):
                if time.perf_counter()-started>30:raise RuntimeError('Native batch deadline')
                if mode=='legacy':env['IA_LEDGER_LEGACY_LOOKUP']='1'
                else:env.pop('IA_LEDGER_LEGACY_LOOKUP',None)
                p=subprocess.run([str(exe),'bench'],capture_output=True,env=env,timeout=5)
                value=json.loads(p.stdout) if p.returncode==0 else None
                timings.append({'mode':mode,'repeat':repeat,'returncode':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace'),'report':value,'passed':p.returncode==0 and value['passed']})
        profiles=[]
        for mode in ['legacy','cached']:
            page=ProfilePage();env['IA_INIT_PROFILE']=page.name
            if mode=='legacy':env['IA_LEDGER_LEGACY_LOOKUP']='1'
            else:env.pop('IA_LEDGER_LEGACY_LOOKUP',None)
            try:
                p=subprocess.run([str(exe),'profile'],capture_output=True,env=env,timeout=5);value=json.loads(p.stdout) if p.returncode==0 else None;profile=page.read()
            finally:page.close()
            ok=p.returncode==0 and profile and profile['work_accounting_valid'] and bool(profile['flags']&1) and profile['used']==value['result']['used'] and profile['categories']==value['result']['categories']
            profiles.append({'mode':mode,'report':value,'profile':profile,'passed':bool(ok)})
    else:profiles=[]
    same=bool(timings) and len({json.dumps(r['report']['result']['categories'],sort_keys=True) for r in timings if r['passed']})==1
    result={'schema':'ledger-cache-native-1','passed':len(rows)==len(names) and all(r['passed'] for r in rows) and len(timings)==4 and all(r['passed'] for r in timings) and len(profiles)==2 and all(r['passed'] for r in profiles) and same,'cases':rows,'microbenchmark':timings,'profile_checks':profiles,'small_sample':True,'work_limit':10000000,'case_timeout_seconds':5,'seconds':time.perf_counter()-started,'exe_sha256':gate.digest(exe)}
    gate.save(out/'result.json',result);(out/'progress.json').unlink();return result

def storage(out):
    out.mkdir(parents=True,exist_ok=False);exe=BIN/'authority-ledger-cache-storage.exe';rows=[];started=time.perf_counter()
    names=['repeat-32','repeat-4096','repeat-65536','churn','collision','retired-reference','collect-regenerate','append-failure','quota-before-use','budget','oversize','site-stream']
    for name in names:
        if time.perf_counter()-started>45:raise RuntimeError('Storage batch deadline')
        case=out/name;case.mkdir();p=subprocess.run([str(exe),name,str(case)],capture_output=True,timeout=5)
        value=json.loads(p.stdout) if p.returncode==0 else None
        row={'id':name,'returncode':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace'),'report':value}
        row['passed']=p.returncode==0 and value['passed'] and value['limit']==10000000 and value['work']<=10000000 and value['work_sum_valid']
        journal=case/'events.audit'
        if journal.exists():
            row['prefix']=prefix(journal);row['sha256']=gate.digest(journal)
            if name not in ['append-failure','quota-before-use','budget','retired-reference']:
                data=parent.decode(journal);row['logical_events']=len(parent.logical_events(data));row['passed']=row['passed'] and row['prefix']['tail_error'] is None
            if row['passed']:
                if journal.is_symlink() or journal.resolve().parent!=case.resolve():raise RuntimeError('Unsafe audit cleanup path')
                journal.unlink();case.rmdir()
        rows.append(row);gate.save(out/'progress.json',{'cases':rows});print(json.dumps({'storage':name,'passed':row['passed']}),flush=True)
        if not row['passed']:break
    result={'schema':'ledger-cache-storage-1','passed':len(rows)==len(names) and all(r['passed'] for r in rows),'cases':rows,'exe_sha256':gate.digest(exe),'work_limit':10000000,'case_timeout_seconds':5,'seconds':time.perf_counter()-started}
    gate.save(out/'result.json',result)
    if result['passed']:(out/'progress.json').unlink()
    return result

def model(out,accounting_gate,storage_gate):
    a=json.loads(accounting_gate.read_text(encoding='utf-8'));s=json.loads(storage_gate.read_text(encoding='utf-8'))
    if not a['passed'] or a['exe_sha256']!=gate.digest(BIN/'authority-ledger-tests.exe') or not s['passed'] or s['exe_sha256']!=gate.digest(BIN/'authority-ledger-cache-storage.exe'):raise RuntimeError('Current accounting and storage gates required')
    old=os.environ.get('IA_LEDGER_VERIFY');os.environ['IA_LEDGER_VERIFY']='1'
    try:r=parent.parent.base.previous.run(out,None)
    finally:
        if old is None:os.environ.pop('IA_LEDGER_VERIFY',None)
        else:os.environ['IA_LEDGER_VERIFY']=old
    checks=[]
    for row in r['cases']:
        with gzip.open(out/(row['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:report=json.load(f)
        before=report.get('execution_before_diagnostics',{}).get('ledger_verification')
        after=report.get('execution_after_diagnostics',{}).get('ledger_verification')
        ok=row['kind']=='process-safety' and report.get('process_failure')
        if row['kind']!='process-safety':ok=all(v and v['enabled'] and v['complete_equal'] and v['verified_charges']>0 and v['cache_bytes']==4096 for v in [before,after])
        checks.append({'id':row['id'],'passed':bool(ok),'before':before,'after':after})
    r.update(schema='ledger-cache-model-2',accounting_gate_sha256=gate.digest(accounting_gate),storage_gate_sha256=gate.digest(storage_gate))
    r['same_execution_accounting_checks']=checks;r['passed']=r['passed'] and all(c['passed'] for c in checks)
    gate.save(out/'result.json',r);return r

def accounting_model(out,model_path):
    source=json.loads(model_path.read_text(encoding='utf-8'))
    # v1 added an invalid comparison to a baseline using fewer diagnostic
    # oracles. Reuse its complete, independently passed proofs; do not rerun
    # those models or overwrite the historical validator failure.
    if source['dll_sha256']!=gate.digest(DLL) or not source['complete_manifest'] or not all(c['passed'] for c in source['cases']) or not all(c['passed'] for c in source['profile_checks']) or not source['preserved_formal_files_unchanged'] or not source['save_files_unchanged']:raise RuntimeError('Complete current model evidence required')
    out.mkdir(parents=True,exist_ok=False);spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'));rows=[];started=time.perf_counter();before=protected()
    old=os.environ.get('IA_LEDGER_LEGACY_LOOKUP');os.environ['IA_LEDGER_LEGACY_LOOKUP']='1'
    try:
        for case in spec['cases']:
            if time.perf_counter()-started>90:raise RuntimeError('Accounting batch deadline')
            with gzip.open(model_path.parent/(case['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:first=json.load(f)
            # Paths are serialized into diagnostics and charged by byte length.
            # Reuse the original (already removed) audit pathname, with no report
            # overwrite, so the complete accounting input is identical too.
            expected_journal=model_path.parent/(case['id']+'-candidate-1.audit')
            if expected_journal.exists():raise RuntimeError('Original audit pathname is occupied')
            other,artifact,journal=invoke(case,'candidate-1',DLL,model_path.parent,5)
            a=first.get('budget');b=other.get('budget')
            if case['kind']=='process-safety':
                ok=first.get('process_failure') and other.get('process_failure') and case['error_contains'] in first.get('error','') and case['error_contains'] in other.get('error','') and a is None and b is None
            else:
                ok=a==b and parent.canonical(copy.deepcopy(first))==parent.canonical(copy.deepcopy(other))
                profile=artifact.get('runtime_profile');ok=ok and profile and profile['work_accounting_valid']
            row={'id':case['id'],'kind':case['kind'],'passed':bool(ok),'used':(a or {}).get('used'),'budget_equal':a==b,'artifact':artifact,'same_audit_path':True}
            if a is not None and a!=b:
                left=a['categories'];right=(b or {}).get('categories',{})
                row['budget_differences']={k:[left.get(k),right.get(k)] for k in sorted(set(left)|set(right)) if left.get(k)!=right.get(k)}
            if a is not None:row['budget_sha256']=hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if journal.exists():
                row['prefix']=prefix(journal);row['audit_sha256']=gate.digest(journal)
                if case['kind']!='process-safety':row['passed']=row['passed'] and row['prefix']['tail_error'] is None
                journal.unlink()
            rows.append(row);gate.save(out/'progress.json',{'cases':rows});print(json.dumps({'accounting':case['id'],'passed':row['passed']}),flush=True)
    finally:
        if old is None:os.environ.pop('IA_LEDGER_LEGACY_LOOKUP',None)
        else:os.environ['IA_LEDGER_LEGACY_LOOKUP']=old
    r={'schema':'ledger-cache-accounting-model-1','passed':len(rows)==len(spec['cases']) and all(r['passed'] for r in rows) and before==protected(),'complete_manifest':len(rows)==len(spec['cases']),'cases':rows,'model_evidence_path':model_path.relative_to(ROOT).as_posix(),'model_evidence_sha256':gate.digest(model_path),'historical_validator_issue':bool(source.get('accounting_checks') and not source['passed']),'dll_sha256':gate.digest(DLL),'exe_sha256':gate.digest(EXE),'work_limit':10000000,'case_timeout_seconds':5,'seconds':time.perf_counter()-started}
    gate.save(out/'result.json',r);(out/'progress.json').unlink();return r

def require_model(path):
    r=json.loads(path.read_text(encoding='utf-8'))
    if not r['passed'] or not r['complete_manifest'] or r['dll_sha256']!=gate.digest(DLL) or not r.get('same_execution_accounting_checks') or not all(c['passed'] for c in r['same_execution_accounting_checks']):raise RuntimeError('Current complete model and same-execution accounting gate required')

def benchmark(out,model_gate):
    require_model(model_gate);out.mkdir(parents=True,exist_ok=False);rows=[];started=time.perf_counter();before=protected()
    spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'))
    keys=['IA_LEDGER_LEGACY_LOOKUP','IA_LEDGER_VERIFY','IA_EVIDENCE_KEEP_HISTORY','IA_INIT_PROFILE','IA_CONSUMER_VERIFY','IA_INCREMENTAL_VERIFY','IA_INIT_EVIDENCE_COLLISION']
    prior={k:os.environ.get(k) for k in keys}
    try:
        for name in ['root-128','graph-churn-16','dual-config-2']:
            case=next(c for c in spec['cases'] if c['id']==name)
            for repeat in range(2):
                for mode in (['legacy','cached'] if repeat==0 else ['cached','legacy']):
                    if time.perf_counter()-started>45:raise RuntimeError('Benchmark batch deadline')
                    for key in keys:os.environ.pop(key,None)
                    if mode=='legacy':os.environ['IA_LEDGER_LEGACY_LOOKUP']='1'
                    os.environ['IA_CONSUMER_VERIFY']='1'
                    r,a,j=invoke(case,mode+'-'+str(repeat),DLL,out,5)
                    if r.get('process_failure'):raise RuntimeError('Bounded benchmark process failed: '+str(a))
                    data=prefix(j);profile=a.get('runtime_profile');before_diag=r['execution_before_diagnostics'];after_diag=r['execution_after_diagnostics']
                    ok=r['compact_storage']['journal']['complete'] and r['compact_storage']['journal']['sealed'] and before_diag['journal_reads']==0 and before_diag.get('cache_hit_history_reads')==0 and r['compact_storage']['journal']['reads']==after_diag['journal_reads'] and data['tail_error'] is None and profile and profile['work_accounting_valid']
                    proof=hashlib.sha256(json.dumps(parent.canonical(copy.deepcopy(r)),sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    row={'id':name,'mode':mode,'repeat':repeat,'seconds':a['seconds'],'offline_seconds':a.get('offline_reconstruction_seconds'),'budget':{k:r['budget'].get(k) for k in ['used','categories','failure','rejected_charge','limit']},'proof_sha256':proof,'profile':profile,'prefix':data,'passed':bool(ok)}
                    rows.append(row);gate.save(out/'progress.json',{'rows':rows});j.unlink()
    finally:
        for k,v in prior.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    checks=[{'id':name,'proof_equal':len({r['proof_sha256'] for r in rows if r['id']==name})==1,'budget_equal':len({json.dumps(r['budget'],sort_keys=True) for r in rows if r['id']==name})==1} for name in ['root-128','graph-churn-16','dual-config-2']]
    result={'schema':'ledger-cache-benchmark-1','passed':len(rows)==12 and all(c['proof_equal'] for c in checks) and all(r['passed'] for r in rows) and before==protected(),'rows':rows,'checks':checks,'accounting_equality_proof':'per-charge legacy mirror in the complete model gate; cross-process physical index work is reported without normalization','dll_sha256':gate.digest(DLL),'exe_sha256':gate.digest(EXE),'work_limit':10000000,'case_timeout_seconds':5,'small_sample':True,'seconds':time.perf_counter()-started}
    gate.save(out/'result.json',result);(out/'progress.json').unlink();return result

def initialization(out,model_gate,benchmark_gate,eviction_gate):
    require_model(model_gate)
    for p in [benchmark_gate,eviction_gate]:
        g=json.loads(p.read_text(encoding='utf-8'))
        if not g['passed'] or g['dll_sha256']!=gate.digest(DLL):raise RuntimeError('Current short gates required')
    import run_audit_batch_initialization as real
    real.previous.DLL=DLL;real.previous.EXE=BIN/'authority-ledger-cache-real.exe';real.previous.prefix=prefix
    before=protected();r=real.previous.run(out,None)
    r['schema']='ledger-cache-real-1';r['preserved_formal_files_unchanged']=before==protected()
    r['compatibility_passed']=all((c.get('report') or {}).get('case',{}).get('compatibility_passed') is True for c in r['cases'])
    r['passed']=r['compatibility_passed'] and r['preserved_formal_files_unchanged'] and r['save_files_unchanged'] and r['frozen_sources_unchanged']
    r['accepted_gate_sha256']=[gate.digest(p) for p in [model_gate,benchmark_gate,eviction_gate]];gate.save(out/'result.json',r);return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['native','storage','model','accounting-model','benchmark','eviction','initialization']);p.add_argument('--output',required=True,type=Path);p.add_argument('--gate',type=Path);p.add_argument('--accounting',type=Path);p.add_argument('--benchmark',type=Path);p.add_argument('--eviction',type=Path);a=p.parse_args()
    os.environ.pop('IA_LEDGER_LEGACY_LOOKUP',None)
    os.environ.pop('IA_LEDGER_VERIFY',None)
    if a.phase=='native':r=native(a.output.resolve())
    elif a.phase=='storage':r=storage(a.output.resolve())
    elif a.phase=='model':r=model(a.output.resolve(),a.accounting.resolve(),a.gate.resolve())
    elif a.phase=='accounting-model':r=accounting_model(a.output.resolve(),a.gate.resolve())
    elif a.phase=='benchmark':r=benchmark(a.output.resolve(),a.gate.resolve())
    elif a.phase=='eviction':require_model(a.gate.resolve());r=parent.eviction(a.output.resolve(),a.gate.resolve(),4)
    else:r=initialization(a.output.resolve(),a.gate.resolve(),a.benchmark.resolve(),a.eviction.resolve())
    print(json.dumps({'phase':a.phase,'passed':r['passed'],'seconds':r['seconds']}));sys.exit(0 if r['passed'] else 1)
