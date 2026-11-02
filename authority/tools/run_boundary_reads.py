"""Frozen, bounded callback read sets; never authorize cache reuse or projection."""
import argparse,copy,json,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_handoff as old
import run_boundary_writes as writes
import verify_boundary_writes
ROOT=old.ROOT;MANIFEST=ROOT/'research/boundary_reads_v5.json';EXE=ROOT/'build-read-set/Release/authority-reads.exe';REF=EXE.with_name('authority-reads-reference.exe')
def capture(event=2,**buttons):return dict(op='capture_reads',event=event,phase='presentation',input=buttons)
def status(consumer=2):return dict(op='consumer_status',consumer=consumer)
def mutate(selector,button):return old.dispatch(event=3,**dict(selector,**{button:True}))
def freeze():
    cases=[];source='research/boundary_reads/consumers.lua'
    def case(name,steps,check='validity',kind='functional',file=source,**extra):
        cases.append(dict(id=name,source=file,source_sha256=old.digest(ROOT/file),stores=[old.store(1,17,'en'),old.store()],steps=steps,check=check,kind=kind,**extra))
    pairs=[('sibling',None,'mut_unused',True),('amount-aba',None,'mut_amount',False),('raw-aba','raw','mut_amount',False),('missing-aba','missing','mut_absent',False),('missing-sibling','missing','mut_unused',True),('length-value','length','mut_list_value',True),('length-structure','length','mut_list_shape',False),('length-binding','length','mut_list_meta',False),('rawlen-binding','rawlen','mut_list_meta',True),('iteration-value','iter','mut_list_value',False),('iteration-structure','iter','mut_list_shape',False),('ipairs-value','ipairs','mut_list_value',False),('ipairs-terminal','ipairs','mut_list_shape',False),('ipairs-unread-index','ipairs','mut_list_far',True),('metatable-backing','indexed','mut_backing',False),('metatable-unread-field','indexed','mut_proxy_unused',True),('metatable-shadow-aba','indexed','mut_proxy_shadow',False),('metatable-binding-aba','indexed','mut_proxy_meta',False),('metatable-index-aba','indexed','mut_index',False),('raw-access-ignores-binding','rawproxy','mut_proxy_meta',True),('raw-access-own-field','rawproxy','mut_proxy_shadow',False),('scalar-aba','scalar','mut_scalar',False),('scalar-sibling','scalar','mut_unused',True),('nested-cell-aba','nested','mut_amount',False),('nested-cell-sibling','nested','mut_unused',True),('weak-value-gc','weak','mut_weak',False),('equality-metamethod','eq','mut_eq',False),('call-metamethod','callmeta','mut_amount',False),('private-load','load','mut_store',False),('private-has','has','mut_store',True)]
    for name,mode,button,expected in pairs:
        selector={mode:True} if mode else {};case(name,[capture(**selector),status(),mutate(selector,button),status()],expected_valid=expected,selector=mode)
    case('world-revision',[capture(world=True),status(),old.dispatch('host',1,'authority'),status()],expected_valid=False,selector='world')
    case('unread-input-key',[capture(),status(),dict(op='set_input',input={'unrelated-button':True}),status()],expected_valid=True)
    case('read-input-key',[capture(),status(),dict(op='set_input',input={'raw':True}),status()],expected_valid=False)
    case('dynamic-replacement',[capture(dynamic=True),status(),mutate({'dynamic':True},'mut_which'),status(),capture(dynamic=True),status(),mutate({'dynamic':True},'mut_amount'),status()],'dynamic')
    case('deduplicated-20000-reads',[capture(repeat=True),status()],'repeat')
    steps=[]
    for i in range(20):steps += [capture(),status()]
    case('replace-without-growth',steps,'replacement')
    case('shared-consumers',[capture(),capture(event=4),status(),status(4),mutate({},'mut_amount'),status(),status(4)],'shared')
    case('self-modification',[capture(self=True),status()],'self',kind='diagnostic-not-reusable')
    for mode,error in [('fail','consumer-injected'),('unknown','Unknown native consumer contract')]:
        case('rollback-'+mode,[capture(),status(),dict(capture(**{mode:True}),expect_error=error),status()],'rollback',kind='safety-rejection',candidate_only=mode=='unknown')
    case('consumer-capacity',[dict(capture(),expect_error='Consumer dependency capacity exceeded')],'capacity',kind='safety-rejection',file='research/boundary_reads/capacity.lua',candidate_only=True)
    case('consumer-retirement',[capture(),status(1),old.dispatch(event=3),dict(status(1),expect_error='Consumer read set unavailable'),capture(),status(3)],'retirement',file='research/boundary_handoff/lifecycle.lua')
    case('single-evaluation-parser-gc',[capture(),status(1)],'parser',file='research/boundary_reads/parser_edges.lua')
    for name,file,error in [('external-capacity','external_capacity.lua','Consumer external dependency capacity exceeded'),('total-read-capacity','total_capacity.lua','Consumer total read entry capacity exceeded'),('unknown-native-swallowed','native_guard.lua','Unknown native consumer contract')]:
        case(name,[dict(capture(),expect_error=error)],'capacity',kind='safety-rejection',file='research/boundary_reads/'+file,candidate_only=True)
    case('gc-token-replacement',[capture(),status(1),capture(),status(1)],'gc-token',kind='diagnostic-not-reusable',file='research/boundary_reads/gc_consumer.lua')
    case('error-name-aba',[capture(),status(1),old.dispatch(event=3),status(1)],'error-name',file='research/boundary_reads/error_name.lua')
    case('logical-mode-aba',[capture(),status(1),old.dispatch(event=3),status(1)],'logical-mode',file='research/boundary_reads/logical_mode.lua')
    case('real-finalizer-reads',[capture(),status(1)],'finalizer',kind='diagnostic-not-reusable',file='research/boundary_reads/finalizer.lua')
    spec=dict(schema='boundary-reads-frozen-1',work_limit=10000000,timeout_seconds=5,batch_timeout_seconds=60,view_rule='personal-settings-authority-hud-v1',cases=cases,write_manifest_sha256=old.digest(writes.MANIFEST),lua_source_manifest_sha256=old.digest(ROOT/'third_party/lua533/SOURCE.json'))
    if MANIFEST.exists():assert json.loads(MANIFEST.read_text(encoding='utf-8'))==spec,'Frozen read manifest differs'
    else:old.save(MANIFEST,spec)
    print(json.dumps(dict(frozen_cases=len(cases),manifest_sha256=old.digest(MANIFEST))))
def canonical(r):
    steps=copy.deepcopy(r['steps'])
    for step in steps:step.pop('metadata',None)
    return dict(semantic=r['semantic'],steps=steps)
def checks(c,r):
    s=r['steps'];out=[]
    def check(name,condition):out.append(dict(check=name,passed=bool(condition)))
    def meta(i):return s[i]['metadata']
    def texts(i):return [bytes.fromhex(v['text_hex']).decode('utf-8') for v in s[i]['draws']]
    def fields(i):return [v['key'] for v in meta(i)['dependencies'] if v['kind']=='field']
    if c['check']=='validity':
        check('initial-read-versions-valid',meta(1)['versions_valid']);check('invalidation-exact',meta(3)['versions_valid']==c['expected_valid'])
        if c.get('selector') is None:check('personal-hud-content',texts(0)==['en|2'])
        mode=c.get('selector')
        if mode=='nested':check('nested-closure-reads',texts(0)==['2'] and 'amount'in fields(1))
        if mode=='world':check('world-token',meta(1)['external']['world.coins_revision']==0 and meta(3)['external']['world.coins_revision']==0 and r['semantic']['world']['coins']==1)
        if c['id']=='rawlen-binding':check('rawlen-no-meta-read',not any(d['kind']=='metatable' for d in meta(1)['dependencies']))
        if c['id']=='raw-access-ignores-binding':check('raw-nil-no-meta-read',not any(d['kind']=='metatable' for d in meta(1)['dependencies']))
    elif c['check']=='dynamic':
        check('old-selector-invalidates',not meta(3)['versions_valid']);check('new-read-set-valid',meta(5)['versions_valid'] and meta(7)['versions_valid']);check('old-field-released','amount'not in fields(5) and 'language'in fields(5));check('selected-output',texts(4)==['en'])
    elif c['check']=='repeat':check('reads-deduplicated',meta(1)['read_events']>=20000 and len(meta(1)['dependencies'])<64 and r['metadata'][1]['write_barrier']['selected_fields']<64 and meta(1)['versions_valid']);check('ordinary-content',texts(0)==['40000'])
    elif c['check']=='replacement':check('one-latest-set',r['metadata'][1]['consumer_reads']['active_consumers']==1 and r['metadata'][1]['consumer_reads']['replaced_sets']==19);check('bounded-watch-metadata',r['metadata'][1]['write_barrier']['selected_fields']<64 and r['metadata'][1]['write_barrier']['peak_fields']<64);check('all-replacements-valid',all(meta(i)['versions_valid'] for i in range(1,len(s),2)))
    elif c['check']=='shared':check('shared-version-invalidation',meta(2)['versions_valid'] and meta(3)['versions_valid'] and not meta(5)['versions_valid'] and not meta(6)['versions_valid']);check('two-independent-sets',r['metadata'][1]['consumer_reads']['active_consumers']==2)
    elif c['check']=='self':check('mixed-read-time-explicit',not meta(1)['versions_valid'] and meta(1)['mixed_times'] and meta(1)['effect_calls']>0 and texts(0)==['2|3'])
    elif c['check']=='rollback':check('complete-read-set-rollback',meta(1)==meta(3) and r['semantic']['stores']==c['stores'] and r['metadata'][1]['consumer_reads']['active_consumers']==1);check('draw-after-rebuild',bytes.fromhex(r['semantic']['draws'][1][0]['text_hex']).decode()=='en|2')
    elif c['check']=='capacity':check('capacity-fails-without-published-set','error'in s[0] and r['metadata'][1]['consumer_reads']['active_consumers']==0 and r['metadata'][1]['write_barrier']['selected_fields']==0)
    elif c['check']=='retirement':check('retired-set-unavailable','error'in s[3]);check('new-consumer-captured',meta(5)['versions_valid'] and r['metadata'][1]['consumer_reads']['active_consumers']==1)
    elif c['check']=='parser':check('constants-arguments-nils-gc',texts(0)==['80|constant-001|constant-080'] and meta(1)['versions_valid'])
    elif c['check']=='gc-token':check('gc-not-certified',all(not meta(i)['versions_valid'] and meta(i)['external']['unreusable-gc'] for i in [1,3]));check('gc-token-counter-reclaimed',r['metadata'][1]['consumer_reads']['live_read_entries']==len(meta(3)['dependencies'])+len(meta(3)['external']))
    elif c['check']=='error-name':check('error-name-read-and-invalidated',meta(1)['versions_valid'] and not meta(3)['versions_valid'] and '__name'in fields(1) and 'KindA'in texts(0)[0])
    elif c['check']=='logical-mode':check('actual-mode-read-still-tracked',meta(1)['versions_valid'] and not meta(3)['versions_valid'] and '__mode'in fields(1) and texts(0)==['v'])
    elif c['check']=='finalizer':check('actual-finalizer-body-tracked',texts(0)==['final=2','done'] and 'amount'in fields(1) and meta(1)['output_calls']==2 and not meta(1)['versions_valid'])
    for step in s:
        if isinstance(step.get('metadata'),dict) and 'reusable'in step['metadata']:check('no-cache-or-projection-certificate',step['metadata']['reusable'] is False)
    return out
def invoke(exe,manifest,c,mode):
    started=time.perf_counter()
    try:p=subprocess.run([str(exe),'--read-suite',str(ROOT),str(manifest),c['id'],mode],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,stderr='5-second timeout; killed and reaped',wall_seconds=time.perf_counter()-started),None
    except OSError as error:return dict(returncode=-10,stderr='Child launch failed: '+str(error),wall_seconds=time.perf_counter()-started),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Child output cap exceeded')
    return dict(returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace'),wall_seconds=time.perf_counter()-started),json.loads(p.stdout) if p.returncode==0 else None
def protected():
    result=writes.protected();prior=json.loads((ROOT/'reports/boundary-writes-final.json').read_text(encoding='utf-8'))
    for group in ['inputs','binaries','imported_libraries']:
        for p,h in prior[group].items():assert old.digest(ROOT/p)==h;result[p]=h
    return result
def run(out):
    verify_boundary_writes.main();spec=json.loads(MANIFEST.read_text(encoding='utf-8'));assert spec['work_limit']==10000000 and spec['timeout_seconds']==5
    derived=json.loads((ROOT/'build-read-set/generated/derived_sha256.json').read_text())
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-read-set/generated'/name)==h,'Derived read source differs: '+name
    binary_before={e.name:old.digest(e) for e in [EXE,REF]}
    for c in spec['cases']:assert old.digest(ROOT/c['source'])==c['source_sha256']
    for e in [EXE,REF]:
        data=e.read_bytes();off=struct.unpack_from('<I',data,0x3c)[0];assert data[off:off+4]==b'PE\0\0' and struct.unpack_from('<H',data,off+4)[0]==0x14c
    out.mkdir(parents=True,exist_ok=False);before=protected();saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');start=time.perf_counter();rows=[]
    probes=[]
    for name,expected in [('read-tag-probe-legacy.exe',2),('read-tag-probe.exe',1)]:
        p=subprocess.run([str(EXE.with_name(name))],capture_output=True,timeout=5);assert p.returncode==0
        proof=json.loads(p.stdout);assert proof['target_evaluations']==expected and proof['notifications']==1
        probes.append(dict(binary_sha256=old.digest(EXE.with_name(name)),result=proof))
    for c in spec['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline reached')
        ref=None;artifacts=[]
        if not c.get('candidate_only'):
            a,ref=invoke(REF,MANIFEST,c,'reference');artifacts.append(dict(mode='stock-reference',**a))
        reports=[]
        for n in range(2):
            a,r=invoke(EXE,MANIFEST,c,'boundary');artifacts.append(dict(mode='candidate-'+str(n+1),**a));reports.append(r)
        tests=[]
        if all(v is not None for v in reports):
            r,repeat=reports;tests=checks(c,r);tests.append(dict(check='repeat-set-and-output',passed=r['steps']==repeat['steps'] and r['metadata']==repeat['metadata'] and r['semantic']==repeat['semantic']));tests.append(dict(check='capability-ABI',passed=all(v['abi']=='ia-lua533-boundary-reads-1' and v['stage']=='consumer_read_sets' and v['consumer_read_sets_implemented'] and v['legacy_write_macro_repaired'] and v['source_unchanged'] and not v['cache_reuse_enabled'] for v in reports)))
            if not c.get('candidate_only'):tests.append(dict(check='stock-Lua-behavior',passed=ref is not None and canonical(ref)==canonical(r)))
            for v in reports:tests.append(dict(check='formal-limits-no-trace',passed=v['budget']['used']<=10000000 and v['budget']['used']==sum(v['budget']['categories'].values()) and not v['full_trace_enabled'] and not v['automatic_projection_implemented'] and not v['personal_draws_publishable'] and all(m['normal_audit_bytes']==m['full_value_graph_nodes']==0 and m['consumer_reads']['historical_read_records']==0 for m in v['metadata'])))
        else:tests=[dict(check='children-completed',passed=False)]
        row=dict(id=c['id'],kind=c['kind'],passed=all(t['passed'] for t in tests),checks=tests,artifacts=artifacts,stock_reference=ref,candidate_runs=reports);rows.append(row);old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'])),flush=True)
        if not row['passed']:break
    regressions=[]
    if len(rows)==len(spec['cases']) and all(c['passed'] for c in rows):
        for manifest,kind in [(writes.MANIFEST,'write-barriers'),(old.MANIFEST,'handoff')]:
            previous=json.loads(manifest.read_text(encoding='utf-8'))
            for c in previous['cases']:
                if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline reached')
                artifact,r=invoke(EXE,manifest,c,'boundary')
                if c.get('process_error'):tests=[dict(check='expected-process-rejection',passed=artifact['returncode']!=0 and c['process_error'] in artifact['stderr'])]
                elif r is None:tests=[dict(check='completed',passed=False)]
                else:tests=writes.checks(c,r) if kind=='write-barriers' else old.assertions(c,r)
                regressions.append(dict(id=c['id'],suite=kind,passed=all(t['passed'] for t in tests),checks=tests,artifact=artifact))
                if not regressions[-1]['passed']:break
            if not regressions[-1]['passed']:break
    stability=[]
    if len(regressions)==56 and all(v['passed'] for v in regressions):
        c=next(c for c in spec['cases'] if c['id']=='error-name-aba');baseline=next(v['candidate_runs'][0] for v in rows if v['id']==c['id'])
        for n in range(12):
            if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline reached')
            a,v=invoke(EXE,MANIFEST,c,'boundary');equal=v is not None and all(v[k]==baseline[k] for k in ['steps','metadata','semantic'])
            stability.append(dict(iteration=n,passed=equal,artifact=a))
            if not equal:break
    binaries_unchanged=binary_before=={e.name:old.digest(e) for e in [EXE,REF]}
    final_saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');result=dict(schema='boundary-read-set-gate-1',passed=len(rows)==len(spec['cases']) and all(r['passed'] for r in rows) and len(regressions)==56 and all(r['passed'] for r in regressions) and len(stability)==12 and all(v['passed'] for v in stability) and before==protected() and saves['files']==final_saves['files'] and binaries_unchanged,single_evaluation_probes=probes,stability_probes=stability,cases=rows,regressions=regressions,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,consumer_cache_enabled=False,automatic_projection_passed=False,game_started=False,protected_files_unchanged=before==protected(),save_files_unchanged=saves['files']==final_saves['files'],binaries_unchanged=binaries_unchanged,driver_sha256=old.digest(Path(__file__)),manifest_sha256=old.digest(MANIFEST),derived_manifest_sha256=old.digest(ROOT/'build-read-set/generated/derived_sha256.json'),binary_sha256=binary_before)
    old.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps(dict(passed=result['passed'],cases=len(rows),regressions=len(regressions),seconds=result['seconds'])));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output.resolve())['passed'] else 1)
