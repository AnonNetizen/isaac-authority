"""Bounded short gate: cache certificates, exact proof parity, and audit reconstruction."""
import argparse,copy,gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_incremental2 import digest,ordinary,proof
from measure_compact_completion import protected
from audit_baseline import audit
from read_compact_audit import read as decode
MANIFEST=ROOT/'research/ui_execution_audit_v2.json'
BINARY=ROOT/'build-execution-audit/Release'
DLL=BINARY/'ia_lua533_execution_audit.dll'
EXE=BINARY/'authority-execution-audit.exe'
OLD=ROOT/'build-ui-incremental2/compact/Release/ia_lua533_ui_compact.dll'
REFERENCE=ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_reference.dll'
RUN_DEADLINE=None
AUDIT_WRITTEN_BYTES=0
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def freeze():
    def chunk(name):
        path=ROOT/'research/execution_audit_fixtures'/name
        return {'file':path.relative_to(ROOT).as_posix(),'sha256':digest(path)}
    cases=[]
    for kind in ['root','leaf']:
        for n in [32,64,128]:cases.append({'id':kind+'-'+str(n),'kind':'functional','n':n,'chunks':[chunk(kind+'.lua')],'expected':[[7,n]],'require_cache_hits':True})
    for manifest,ids in [('ui_incremental2_stage1_v7.json',['reparent','closure','rawset-return','unknown-native']),('ui_incremental2_legacy_oracle_v2.json',['legacy-closed-shared-upvalue','legacy-monotone-upvalue-coverage','legacy-scalar-leaf-shared-upvalue','legacy-scalar-leaf-cycle-shared'])]:
        source=json.loads((ROOT/'research'/manifest).read_text(encoding='utf-8'))
        for case in source['cases']:
            if case['id'] in ids:
                c=copy.deepcopy(case);c['frozen_source_manifest']=manifest;c['baseline']=False;c['origin_oracle']=False;cases.append(c)
    source=json.loads((ROOT/'research/ui_compact_storage_v3.json').read_text(encoding='utf-8'))
    for case in source['cases']:
        if case['id'] in ['dual-config-2','dual-config-1']:
            c=copy.deepcopy(case);c['frozen_source_manifest']='ui_compact_storage_v3.json';cases.append(c)
    for fault in [1,2]:
        first=chunk('cert_setup.lua');first['certificate_fault']=fault
        cases.append({'id':'certificate-fault-'+str(fault),'kind':'certificate-safety','chunks':[first,chunk('cert_use.lua')],'error_contains':'Invalid resident cache completion certificate'})
    cases.append({'id':'work-limit','kind':'process-safety','chunks':[chunk('cert_setup.lua')],'extra_work':10000000,'error_contains':'Work budget rejected'})
    cases.append({'id':'cache-read-guard','kind':'process-safety','chunks':[chunk('cert_setup.lua')],'read_guard_probe':True,'error_contains':'Cache hit attempted historical audit read'})
    cases.append({'id':'audit-write-failure','kind':'process-safety','chunks':[chunk('cert_setup.lua')],'fault_after_last_phase':2,'error_contains':'Audit seek failed'})
    for c in cases:c['audit_disk_limit']=16*1024*1024
    spec={'schema':'execution-audit-short-2','mode':'ui-execution-audit','work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':90,'audit_batch_bytes':128*1024*1024,'view_rule':'personal-settings-authority-hud-v1','acceptance':{'semantic_and_audit_repeat_required':True,'each_run_budget_valid_required':True,'identical_work_counts_required':False,'work_variation_reported':True},'cases':cases}
    if MANIFEST.exists() and json.loads(MANIFEST.read_text(encoding='utf-8'))!=spec:raise RuntimeError('Frozen manifest differs')
    if not MANIFEST.exists():save(MANIFEST,spec)
    print(json.dumps({'frozen_manifest':str(MANIFEST),'sha256':digest(MANIFEST),'cases':len(cases)}))
def canonical(report):
    result=proof(report)
    for phase in result.get('phases',[]):
        for field in ['execution_probe','storage_checkpoint','trace_checkpoint','private_commit_checkpoint']:phase.pop(field,None)
    return result
def compact_metrics(report):
    s=report.get('execution_before_diagnostics',{})
    phases=report.get('phases',[])
    return {'work':report.get('budget',{}).get('used'),'cache_hit_calls':s.get('cache_hit_calls'),'cache_hit_history_reads':s.get('cache_hit_history_reads'),'all_execution_journal_reads':s.get('journal_reads'),'diagnostic_journal_reads':report.get('execution_after_diagnostics',{}).get('journal_reads',0)-s.get('journal_reads',0),'execution_wall_seconds':sum(p.get('execution_probe',{}).get('wall_seconds',0) for p in phases),'execution_cpu_seconds':sum(p.get('execution_probe',{}).get('cpu_seconds',0) for p in phases),'private_commit_bytes':report.get('private_commit_bytes')}
def baseline_equal(first,old):
    return canonical(copy.deepcopy(first))==canonical(copy.deepcopy(old))
def invoke(case,label,dll,out,timeout):
    global AUDIT_WRITTEN_BYTES
    if RUN_DEADLINE is not None:
        timeout=min(timeout,RUN_DEADLINE-time.perf_counter())
        if timeout<=0:raise RuntimeError('Short batch deadline exceeded; no further process launched')
    if AUDIT_WRITTEN_BYTES>=128*1024*1024:raise RuntimeError('Short batch audit volume exceeded; no further process launched')
    journal=out/(case['id']+'-'+label+'.audit');env=os.environ.copy();env['IA_COMPACT_AUDIT_FILE']=str(journal);env.pop('IA_INCREMENTAL_VERIFY',None)
    if case.get('verify_full_origins'):env['IA_INCREMENTAL_VERIFY']='1'
    command=[str(EXE),'--suite',str(dll),digest(dll),str(ROOT),str(MANIFEST),case['id'],'plain' if label=='reference' else 'trace']
    if label!='reference':command.append('--evidence')
    start=time.perf_counter()
    try:p=subprocess.run(command,capture_output=True,env=env,timeout=timeout)
    except subprocess.TimeoutExpired:return {'process_failure':True,'error':'short-case timeout'},{'timeout':True,'seconds':time.perf_counter()-start},journal
    if len(p.stdout)>32*1024*1024:raise RuntimeError('Short-case output exceeds 32 MiB')
    artifact={'seconds':time.perf_counter()-start,'returncode':p.returncode,'stderr':p.stderr[:8192].decode('utf-8',errors='replace')}
    if journal.exists():AUDIT_WRITTEN_BYTES+=journal.stat().st_size
    if p.returncode:return {'process_failure':True,'error':artifact['stderr']},artifact,journal
    return json.loads(p.stdout),artifact,journal
def run(out,only=None):
    global RUN_DEADLINE,AUDIT_WRITTEN_BYTES
    spec=json.loads(MANIFEST.read_text(encoding='utf-8'));out.mkdir(parents=True,exist_ok=False);before=protected();save(out/'protected-before.json',before)
    saves=audit(ROOT.parent/'artifacts/authority-baseline-20261009');save(out/'save-before.json',saves)
    started=time.perf_counter();RUN_DEADLINE=started+spec['batch_timeout_seconds'];AUDIT_WRITTEN_BYTES=0;rows=[]
    for case in spec['cases']:
        if only and case['id'] not in only:continue
        remaining=spec['batch_timeout_seconds']-(time.perf_counter()-started)
        if remaining<=0:raise RuntimeError('Short batch deadline exceeded; no further case launched')
        print('Short gate '+case['id'],flush=True);row={'id':case['id'],'kind':case['kind']};journals=[]
        first,a,j=invoke(case,'candidate-1',DLL,out,min(5,remaining));journals.append(j);row['candidate']=compact_metrics(first);row['artifact']=a
        if case['kind']=='process-safety':row['passed']=first.get('process_failure') and case['error_contains'] in first.get('error','')
        elif case['kind']=='certificate-safety':row['passed']=not first.get('process_failure') and any(case['error_contains'] in p.get('error','') for p in first.get('phases',[]))
        else:
            old,b,j=invoke(case,'baseline',OLD,out,min(5,max(.01,90-(time.perf_counter()-started))));journals.append(j)
            ref,c,j=invoke(case,'reference',REFERENCE,out,min(5,max(.01,90-(time.perf_counter()-started))));journals.append(j)
            second,d,j=invoke(case,'candidate-2',DLL,out,min(5,max(.01,90-(time.perf_counter()-started))));journals.append(j)
            row['baseline']=compact_metrics(old);row['baseline_artifact']=b;row['repeat_artifact']=d;row['reference_artifact']=c
            row['proof_equal_baseline']=not first.get('process_failure') and not old.get('process_failure') and baseline_equal(first,old)
            row['repeat_equal']=not second.get('process_failure') and canonical(copy.deepcopy(first))==canonical(copy.deepcopy(second))
            row['repeat_work_equal']=first.get('budget')==second.get('budget')
            repeated_budget=second.get('budget',{})
            row['repeat_budget_valid']=repeated_budget.get('limit')==10000000 and repeated_budget.get('used',10000001)<=10000000 and repeated_budget.get('used')==sum(repeated_budget.get('categories',{}).values())
            if not row['repeat_work_equal']:
                left=first.get('budget',{}).get('categories',{});right=second.get('budget',{}).get('categories',{})
                row['repeat_budget_differences']={k:[left.get(k),right.get(k)] for k in sorted(set(left)|set(right)) if left.get(k)!=right.get(k)}
                row['repeat_proof_equal']=canonical(copy.deepcopy(first))==canonical(copy.deepcopy(second))
                if not row['repeat_equal']:
                    with gzip.open(out/(case['id']+'-repeat-difference.json.gz'),'xb') as packed:packed.write(json.dumps(second,ensure_ascii=False,separators=(',',':')).encode())
            row['ordinary_equal_reference']=ordinary(first)==ordinary(ref)
            if case['kind']=='safety':functional=any(case['error_contains'] in p.get('error','') for p in first.get('phases',[]))
            else:functional=row['ordinary_equal_reference'] and all(p['success'] for p in first.get('phases',[]))
            if case.get('expected') is not None:functional=functional and [p['values'] for p in first.get('phases',[])]==case['expected']
            if case['id'].startswith('dual-config-'):
                text=lambda v:{'text_hex':v.encode().hex()}
                row['personal_values_preserved']=all(p['values']==[case['personal'],137,text('en'),text('amount='+str(case['personal']))] for p in first.get('phases',[]))
                row['authority_views_preserved']=all([v.get('value') for v in p.get('views',[])]==[case['authority'],137,'en','amount='+str(case['authority'])] and all(v.get('ok') for v in p['views']) for p in first.get('phases',[]))
                functional=functional and row['personal_values_preserved'] and row['authority_views_preserved']
            if not first.get('process_failure'):
                graph=first.get('value_graph',{});incremental=first.get('trace',{}).get('incremental',{});decoded=decode(journals[0])
                row['audit_reconstruction_equal']=all(decoded[k]==graph[k] for k in ['nodes','consumption_records','storage_versions','static_regions','code','purpose_records']) and all(decoded[k]==incremental[k] for k in ['cache_descriptors','cache_sites','cache_uses'])
                row['audit_repeat_equal']=digest(journals[0])==digest(journals[3])
            row['passed']=bool(functional and row['proof_equal_baseline'] and row['repeat_equal'] and row['repeat_budget_valid'] and row.get('audit_reconstruction_equal') and row.get('audit_repeat_equal'))
            row['proof_sha256']=hashlib.sha256(json.dumps(canonical(copy.deepcopy(first)),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        budget=first.get('budget',{})
        if not first.get('process_failure'):
            row['budget_valid']=budget.get('limit')==10000000 and budget.get('used',10000001)<=10000000 and budget.get('used')==sum(budget.get('categories',{}).values())
            row['zero_cache_hit_reads']=row['candidate'].get('cache_hit_history_reads')==0
            row['passed']=bool(row['passed'] and row['budget_valid'] and row['zero_cache_hit_reads'])
        if case.get('require_cache_hits'):row['passed']=bool(row['passed'] and (row['candidate'].get('cache_hit_calls') or 0)>=case['n'])
        with (out/(case['id']+'-candidate.json.gz')).open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as packed:packed.write(json.dumps(first,ensure_ascii=False,separators=(',',':')).encode())
        row['audit_files_removed']=[]
        for path in journals:
            if path.exists():
                if path.parent.resolve()!=out.resolve():raise RuntimeError('Cleanup path mismatch')
                # The full candidate report retains the reconstructed evidence.
                row['audit_files_removed'].append({'file':path.name,'bytes':path.stat().st_size,'sha256':digest(path)});path.unlink()
        rows.append(row);save(out/(case['id']+'-result.json'),row)
        print(json.dumps({'id':case['id'],'passed':row['passed'],'candidate':row['candidate'],'baseline':row.get('baseline')},ensure_ascii=False),flush=True)
    saved_after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');save(out/'save-after.json',saved_after)
    result={'schema':'execution-audit-step1-gate','passed':bool(rows) and all(r['passed'] for r in rows),'complete_manifest':len(rows)==len(spec['cases']),'cases':rows,'seconds':time.perf_counter()-started,'work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':90,'audit_written_bytes':AUDIT_WRITTEN_BYTES,'manifest_sha256':digest(MANIFEST),'dll_sha256':digest(DLL),'exe_sha256':digest(EXE),'preserved_formal_files_unchanged':protected()==before,'save_files_unchanged':saves['files']==saved_after['files'],'whole_execution_decoupled':False,'field_and_upvalue_invalidation_changed':False,'game_started':False,'real_mod_initialization_run':False}
    result['growth']=[]
    for kind in ['root','leaf']:
        scaled=[next((r for r in rows if r['id']==kind+'-'+str(n)),None) for n in [32,64,128]]
        if not all(scaled):continue
        units=[r['candidate']['work'] for r in scaled];ratios=[units[i+1]/units[i] for i in range(2)]
        result['growth'].append({'kind':kind,'n':[32,64,128],'charged_work':units,'doubling_ratios':ratios,'work_growth_gate':all(v<=2.5 for v in ratios)})
    result['passed']=result['passed'] and all(g['work_growth_gate'] for g in result['growth'])
    result['passed']=result['passed'] and result['preserved_formal_files_unchanged'] and result['save_files_unchanged'];save(out/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--case',action='append');a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve(),a.case)['passed'] else 1)
