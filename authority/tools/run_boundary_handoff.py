"""Freeze/run only the first API-boundary handoff gate; never claim projection."""
import argparse,copy,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from audit_baseline import audit
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'research/boundary_handoff_v1.json';EXE=ROOT/'build-boundary/Release/authority-boundary.exe'
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def store(amount=2,x=137,language='en',**kw):return json.dumps(dict(amount=amount,x=x,language=language,**kw),sort_keys=True,separators=(',',':'))
def dispatch(role='personal',event=2,phase='presentation',**buttons):return {'op':'dispatch','role':role,'event':event,'phase':phase,'input':buttons}
def inspect(callback=2,upvalue='cfg',fields=None):return {'op':'inspect','callback':callback,'upvalue':upvalue,'fields':fields if fields is not None else ['amount','x','language']}
def freeze():
    cases=[]
    def case(name,file,steps,kind='handoff',stores=None,**extra):
        p=ROOT/'research/boundary_handoff'/file
        cases.append(dict(id=name,source=p.relative_to(ROOT).as_posix(),source_sha256=digest(p),stores=stores or [store(1,17,'en'),store(2,137,'zh')],steps=steps,kind=kind,**extra))
    base=[inspect(),inspect(upvalue='alias'),inspect(3),inspect(upvalue='get',fields=[]),dispatch('host',1,'authority'),dispatch('host'),dispatch(move=True),inspect(),inspect(3,'count',[]),inspect(2,'count',[]),{'op':'gc'},dispatch(),inspect(2,'reader',[])]
    case('configuration-closure-cache','handoff.lua',base,assertions='continuity')
    case('configuration-swapped','handoff.lua',base,stores=[store(2,17,'zh'),store(1,137,'en')],assertions='continuity')
    case('saved-reload','handoff.lua',[dispatch('host',1,'authority'),dispatch(move=True),{'op':'reload_saved'},inspect(),dispatch()],assertions='reload')
    case('rebuild-history','handoff.lua',[dispatch('host',1,'authority'),dispatch(move=True),{'op':'rebuild'},inspect(),dispatch()],assertions='reload')
    case('shared-upvalue-factory','upvalues.lua',[inspect(1,'counter',[]),inspect(2,'counter',[]),dispatch(change=True),inspect(1,'counter',[]),inspect(2,'counter',[]),dispatch()],assertions='shared')
    case('remove-gc-reregister','lifecycle.lua',[inspect(1,'value',[]),dispatch(event=3),{'op':'gc'},inspect(3,'value',[]),dict(inspect(1,'value',[]),expect_error='retired'),dispatch()],assertions='lifecycle')
    case('stale-context-handle','handoff.lua',[{'op':'rebuild'},{'op':'stale_handle','generation':2,'expect_error':'Stale context generation'},dispatch()],assertions='stale')
    for button,error in [('write','World write requires authority phase'),('random','Random result has no proven authority reference'),('error','injected callback failure'),('unknown','Unknown module contract')]:
        case('rollback-'+button,'rejection.lua',[dispatch('host',1,'authority'),dispatch(),dict(dispatch(**{button:True}),expect_error=error),dispatch()],kind='boundary-rejection',assertions='rollback')
    for n in [128,4096,32768]:case('opaque-table-'+str(n),'large.lua',[inspect(1,'cfg',['amount','x']),dispatch()],stores=[store(bulk=n),store(bulk=n)],assertions='large',bulk=n)
    case('observation-is-not-write-version','handoff.lua',[inspect(),dispatch(aba=True),inspect()],kind='known-limitation',assertions='aba')
    case('ordinary-bytes-false-nil','handoff.lua',[{'op':'evaluate','code':"return false,nil,string.char(0,255),string.sub('abcd',2,3)"}],assertions='bytes')
    case('unproven-mixed-rejected','mixed.lua',[dispatch('host',1,'authority'),{'op':'projection_gate','expect_error':'Mixed callback projection not implemented'}],kind='compatibility-not-implemented',assertions='mixed')
    case('work-limit','budget.lua',[],kind='process-rejection',process_error='Boundary work limit exceeded')
    obj={'schema':'boundary-handoff-frozen-1','work_limit':10000000,'timeout_seconds':5,'batch_timeout_seconds':60,'view_rule':'personal-settings-authority-hud-v1','unit':'prepaid 64 VM instructions plus API/observation/encoding work; not the old full-trace unit','lua_source_manifest_sha256':digest(ROOT/'third_party/lua533/SOURCE.json'),'cases':cases}
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text(encoding='utf-8'))!=obj:raise RuntimeError('Frozen handoff suite differs; create a new version')
    else:save(MANIFEST,obj)
    print(json.dumps({'frozen_cases':len(cases),'manifest_sha256':digest(MANIFEST)}))
def protected():
    baseline=json.loads((ROOT/'reports/ledger-cache-final.json').read_text(encoding='utf-8'))
    result={n:digest(ROOT/n) for n in baseline['inputs']}
    for n in baseline['binary_sha256']:result['build-ledger-cache/Release/'+n]=digest(ROOT/'build-ledger-cache/Release'/n)
    for folder in ['research/slice3_ui_inputs','third_party/lua533/src']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file():result[p.relative_to(ROOT).as_posix()]=digest(p)
    return result
def canonical(r):
    out={'semantic':r['semantic'],'steps':copy.deepcopy(r['steps'])}
    for step in out['steps']:step.pop('metadata',None)
    return out
def assertions(c,r):
    a=c['assertions'];steps=r['steps'];semantic=r['semantic'];draws=semantic['draws'][1];out=[]
    def check(name,condition):out.append({'check':name,'passed':bool(condition)})
    def text(row):return bytes.fromhex(row['text_hex']).decode('utf-8')
    if a=='continuity':
        first,alias,other=steps[:3];m=first['metadata'];check('table_alias_identity',m['value']['object']==alias['metadata']['value']['object']==other['metadata']['value']['object']);check('shared_cfg_cell',m['cell']==other['metadata']['cell']);check('cached_native_actual_identity',steps[3]['metadata']['value']['api_identity']==7)
        cfg=json.loads(c['stores'][1]);cfg['amount']+=1;cfg['x']+=10
        check('personal_save_and_position',json.loads(semantic['stores'][1])==cfg and draws[0]['x']==cfg['x'])
        check('host_reward_once',semantic['world']['coins']==1 and len(semantic['world']['effects'])==1)
        check('personal_setting_authority_query',text(draws[0])==f"{cfg['language']}|setting={cfg['amount']}|coins=1|reader={cfg['amount']}")
        check('shared_counter_cell',steps[8]['metadata']['cell']==steps[9]['metadata']['cell'] and text(draws[1])=='counter=2')
        before=m['fields'];after=steps[7]['metadata']['fields'];check('selected_observed_fields',before['amount']['observed_version']!=after['amount']['observed_version'] and before['language']['observed_version']==after['language']['observed_version'])
    elif a=='reload':
        cfg=json.loads(c['stores'][1]);cfg['amount']+=1;cfg['x']+=10;check('saved_configuration_restored',json.loads(semantic['stores'][1])==cfg and steps[3]['values']['amount']['value']==cfg['amount']);check('authority_preserved_once',semantic['world']['coins']==1 and len(semantic['world']['effects'])==1);check('nested_closure_after_rebuild',f"|reader={cfg['amount']}" in text(draws[0]))
    elif a=='shared':check('actual_shared_upvalue',steps[0]['metadata']['cell']==steps[1]['metadata']['cell']==steps[3]['metadata']['cell']==steps[4]['metadata']['cell']);check('changed_observed_version',steps[0]['metadata']['observed_version']!=steps[3]['metadata']['observed_version']);check('returned_closure_reads_updated_cell',text(draws[1])=='reader=10|direct=10')
    elif a=='lifecycle':check('live_shared_cell_survives_remove',steps[0]['metadata']['cell']==steps[3]['metadata']['cell']);check('retired_callback_rejected','error' in steps[4]);check('new_callback_after_gc',text(draws[0])=='value=2' and r['metadata'][1]['active_callbacks']==2);check('retired_prototype_reclaimed',r['metadata'][1]['prototype_entries']==2)
    elif a=='rollback':check('world_rng_and_effects_restored',semantic['world']['coins']==1 and len(semantic['world']['effects'])==1);check('save_and_private_state_restored',semantic['stores']==c['stores'] and text(draws[0])=='count=2|amount=2' and len(draws)==1);check('whole_callback_refused','error' in steps[2])
    elif a=='large':check('opaque_table_not_enumerated',r['metadata'][1]['observed_fields']==2 and r['metadata'][0]['observed_fields']==0 and r['metadata'][1]['field_reads']==2);check('ordinary_large_table_output',text(draws[0])==f"length={c['bulk']}|amount=2")
    elif a=='aba':check('observation_limit_explicit',steps[0]['metadata']['fields']['amount']['observed_version']==steps[2]['metadata']['fields']['amount']['observed_version'] and steps[0]['metadata']['version_semantics']=='observed-value-only')
    elif a=='bytes':check('bytes_false_nil',[v for v in steps[0]['values']]==[{'type':'boolean','value':False},{'type':'nil'},{'type':'string','hex':'00ff'},{'type':'string','hex':'6263'}])
    elif a=='mixed':check('no_fake_compatibility',r['automatic_projection_implemented'] is False and r['personal_draws_publishable'] is False and semantic['draws'][1]==[] and 'error' in steps[1])
    elif a=='stale':check('generation_checked_before_use','error' in steps[1])
    return out
def run(out):
    spec=json.loads(MANIFEST.read_text(encoding='utf-8'));pristine=json.loads((ROOT/'third_party/lua533/SOURCE.json').read_text(encoding='utf-8'))
    assert digest(ROOT/'third_party/lua533/SOURCE.json')==spec['lua_source_manifest_sha256']
    for file in pristine['files']:assert digest(ROOT/'third_party/lua533'/file['path'])==file['sha256']
    out.mkdir(exist_ok=False,parents=True);before=protected();saves=audit(ROOT.parent/'artifacts/authority-baseline-20261009');start=time.perf_counter();rows=[]
    for c in spec['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline; no further child launched')
        reports=[];artifacts=[]
        for mode in ['reference','boundary','boundary']:
            p=subprocess.run([str(EXE),'--handoff-suite',str(ROOT),str(MANIFEST),c['id'],mode],capture_output=True,timeout=5);artifact={'mode':mode,'returncode':p.returncode,'stderr':p.stderr.decode('utf-8',errors='replace')};artifacts.append(artifact)
            if c['kind']=='process-rejection':reports.append(None);continue
            if p.returncode:raise RuntimeError(c['id']+': '+artifact['stderr'])
            if len(p.stdout)>1024**2:raise RuntimeError('Diagnostic output cap exceeded')
            reports.append(json.loads(p.stdout))
        if c['kind']=='process-rejection':checks=[{'check':'work_rejection','passed':all(a['returncode']!=0 and c['process_error'] in a['stderr'] for a in artifacts)}];equal=True
        else:
            reference,first,second=reports;equal=canonical(reference)==canonical(first)==canonical(second);checks=assertions(c,first)
            for name,r in [('boundary-1',first),('boundary-2',second)]:
                checks.append({'check':name+'-budget','passed':r['budget']['limit']==10000000 and r['budget']['used']<=10000000 and r['budget']['used']==sum(r['budget']['categories'].values()) and not r['full_trace_enabled'] and r['source_unchanged'] and all(m['normal_audit_bytes']==0 and m['full_value_graph_nodes']==0 for m in r['metadata'])})
            checks.append({'check':'repeat_metadata','passed':first['steps']==second['steps'] and first['metadata']==second['metadata']})
        row={'id':c['id'],'kind':c['kind'],'passed':equal and all(v['passed'] for v in checks),'ordinary_reference_equal':equal,'checks':checks,'artifacts':artifacts,'reports':reports};rows.append(row);save(out/'progress.json',{'cases':rows});print(json.dumps({'case':c['id'],'passed':row['passed']}),flush=True)
        if not row['passed']:break
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');result={'schema':'boundary-handoff-gate-1','passed':len(rows)==len(spec['cases']) and all(r['passed'] for r in rows) and before==protected() and saves['files']==after['files'],'stage':'initialization_handoff_only','automatic_mixed_projection_passed':False,'precise_write_versions_implemented':False,'world_view_rule':'personal-settings-authority-hud-v1','cases':rows,'seconds':time.perf_counter()-start,'work_limit':10000000,'case_timeout_seconds':5,'manifest_sha256':digest(MANIFEST),'driver_sha256':digest(Path(__file__)),'exe_sha256':digest(EXE),'lua_archive_sha256':pristine['archive_sha256'],'protected_files_unchanged':before==protected(),'save_files_unchanged':saves['files']==after['files'],'game_started':False,'normal_audit_files_created':False}
    save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps({'passed':result['passed'],'cases':len(rows),'seconds':result['seconds']}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output.resolve())['passed'] else 1)
