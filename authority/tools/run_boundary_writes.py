"""Bounded selective-write gate. Stock Lua reference is a separate executable."""
import argparse,copy,json,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_handoff as old
ROOT=old.ROOT;MANIFEST=ROOT/'research/boundary_writes_v2.json'
EXE=ROOT/'build-write-barrier/Release/authority-writes.exe'
REF=EXE.with_name('authority-writes-reference.exe')
def watch(callback=1,upvalue='cfg',fields=None):return dict(op='inspect_writes',callback=callback,upvalue=upvalue,fields=fields if fields is not None else ['amount','x','language'])
def dispatch(**buttons):return old.dispatch(**buttons)
def freeze():
    cases=[]
    def case(name,file,steps,check,kind='functional',**extra):
        p=ROOT/file;cases.append(dict(id=name,source=file,source_sha256=old.digest(p),stores=[old.store(1,17,'en'),old.store()],steps=steps,check=check,kind=kind,**extra))
    fields='research/boundary_writes/fields.lua';opening='research/boundary_writes/open.lua';gc='research/boundary_writes/gc.lua'
    for button,delta in [('aba',{'amount':2}),('same',{'amount':1}),('raw',{'amount':2}),('nil',{'new':3}),('typed',{1:1,'1':1}),('insert',{2:1,3:1,4:1}),('remove',{2:1,3:1}),('move',{2:1,3:1,4:1}),('sibling',{}),('proxy',{'amount':2}),('deny',{}),('meta',{}),('many',{'amount':20000})]:
        keys=['amount','x','language','new',1,2,3,4,'1']
        case('field-'+button,fields,[watch(fields=keys),dispatch(**{button:True}),watch(fields=keys)],'field',expected=[[k,v] for k,v in delta.items()],button=button)
    case('table-sort',fields,[watch(fields=[1,2,3]),dispatch(sort=True),watch(fields=[1,2,3])],'sort')
    case('late-registration',fields,[dispatch(aba=True),watch(fields=['amount']),dispatch(aba=True),watch(fields=['amount'])],'late')
    for api,key in [('rawset','amount'),('setfield','amount'),('rawseti',1),('seti',1)]:
        case('native-'+api,fields,[watch(fields=[key]),dict(op='native_write',callback=1,upvalue='cfg',api=api,key=key,value=9),dict(op='native_write',callback=1,upvalue='cfg',api=api,key=key,value=2),watch(fields=[key])],'native')
    case('native-pointer-key',fields,[watch(fields=['amount']),dict(op='native_write',callback=1,upvalue='cfg',api='rawsetp',value=9),watch(fields=['amount'])],'pointer')
    for button,delta in [('aba',2),('same',1),('change',1)]:
        case('upvalue-'+button,opening,[watch(upvalue='counter',fields=[]),dispatch(**{button:True}),watch(upvalue='counter',fields=[])],'cell',delta=delta)
    case('shared-open-close-stack',opening,[watch(upvalue='counter',fields=[]),watch(2,'counter',[]),dispatch(change=True),old.dispatch(event=3),watch(upvalue='counter',fields=[]),watch(2,'counter',[]),dict(op='gc'),watch(upvalue='counter',fields=[])],'shared')
    case('native-setupvalue',opening,[watch(upvalue='counter',fields=[]),dict(op='native_write',callback=1,upvalue='counter',api='setupvalue',value=9),dict(op='native_write',callback=1,upvalue='counter',api='setupvalue',value=7),watch(upvalue='counter',fields=[])],'native-cell')
    case('weak-value-gc',gc,[watch(upvalue='weak',fields=['target',1]),dispatch(release=True),watch(upvalue='weak',fields=['target',1]),dict(op='gc'),watch(upvalue='weak',fields=['target',1])],'weak')
    case('table-lifetime-replacement',gc,[watch(fields=['amount']),dispatch(replace=True),watch(fields=['amount'])],'replace')
    steps=[watch(fields=['amount'])]
    for i in range(30):steps +=[old.dispatch(event=3),watch(3+i,fields=['amount'])]
    steps += [dispatch(),watch(32,fields=['amount'])]
    case('retire-gc-reregister', 'research/boundary_writes/churn.lua',steps,'churn')
    for button,error in [('write','World write requires authority phase'),('error','injected callback failure')]:
        case('rollback-'+button,'research/boundary_handoff/rejection.lua',[watch(2,fields=['amount','x']),watch(2,'count',[]),old.dispatch('host',1,'authority'),dispatch(),dict(dispatch(**{button:True}),expect_error=error),watch(2,fields=['amount','x']),watch(2,'count',[]),dispatch()],'rollback',kind='safety-rejection')
    case('unsupported-watch-key',fields,[dict(watch(fields=[True]),expect_error='Selected write key type unsupported'),dispatch()],'rejected',kind='safety-rejection')
    case('unsupported-native-rebind',opening,[watch(upvalue='counter',fields=[]),dict(op='native_write',callback=1,upvalue='counter',api='upvaluejoin',expect_error='Native upvalue rebinding unsupported'),watch(upvalue='counter',fields=[])],'join',kind='safety-rejection',reference_step_difference=[1])
    case('field-capacity',fields,[dict(watch(fields=['watch'+str(i) for i in range(1025)]),expect_error='Write field capacity exceeded'),dispatch()],'rejected',kind='safety-rejection',candidate_only=True)
    case('work-limit','research/boundary_handoff/budget.lua',[],'budget',kind='safety-rejection',process_error='Boundary work limit exceeded')
    case('metamethod-destination-only',fields,[watch(fields=['amount']),watch(upvalue='proxy',fields=['amount']),dispatch(proxy=True),watch(fields=['amount']),watch(upvalue='proxy',fields=['amount'])],'destination')
    case('shared-cell-owner-removal','research/boundary_handoff/lifecycle.lua',[watch(1,'value',[]),old.dispatch(event=3),dict(op='gc'),watch(3,'value',[])],'shared-retire')
    case('shared-table-alias-owners','research/boundary_handoff/handoff.lua',[watch(2,'cfg',['amount','x']),watch(2,'alias',['amount','x']),watch(3,'cfg',['amount','x']),dispatch(move=True),watch(2,'cfg',['amount','x']),watch(3,'cfg',['amount','x'])],'aliases')
    case('weak-object-key-gc','research/boundary_writes/weak_keys.lua',[watch(upvalue='weak',fields=['marker']),dispatch(release=True),watch(upvalue='weak',fields=['marker'])],'weak-key')
    spec=dict(schema='boundary-writes-frozen-1',work_limit=10000000,timeout_seconds=5,batch_timeout_seconds=60,view_rule='personal-settings-authority-hud-v1',unit='prepaid VM64 + API/encoding/observations + selected writes and lifecycle; not old trace units',cases=cases,lua_source_manifest_sha256=old.digest(ROOT/'third_party/lua533/SOURCE.json'))
    if MANIFEST.exists():assert json.loads(MANIFEST.read_text(encoding='utf-8'))==spec,'Frozen cases differ; version the manifest'
    else:old.save(MANIFEST,spec)
    print(json.dumps(dict(frozen_cases=len(cases),manifest_sha256=old.digest(MANIFEST))))
def ordinary(r,ignored=()):
    steps=[]
    for i,s in enumerate(r['steps']):
        if i in ignored:continue
        s=copy.deepcopy(s);s.pop('metadata',None)
        for f in s.get('fields',[]):f.pop('write_version',None);f.pop('gc_writes',None)
        steps.append(s)
    return dict(semantic=r['semantic'],steps=steps)
def checks(c,r):
    s=r['steps'];kind=c['check'];out=[]
    def check(name,test):out.append(dict(check=name,passed=bool(test)))
    def delta(a,b,k):return b['fields'][next(i for i,f in enumerate(b['fields']) if f['key']==k)]['write_version']-a['fields'][next(i for i,f in enumerate(a['fields']) if f['key']==k)]['write_version']
    def cell(a,b):return b['metadata']['write_version']-a['metadata']['write_version']
    if kind=='field':
        a,b=s[0],s[2];expected=c['expected']
        for f in a['fields']:
            target=next((v for k,v in expected if type(k)==type(f['key']) and k==f['key']),0);check('exact-field-'+str(f['key']),delta(a,b,f['key'])==target)
        check('root-cell-not-written',cell(a,b)==0)
        check('no-field-record-per-write',r['metadata'][1]['write_barrier']['selected_fields']==len(a['fields']))
        if c['button']=='sibling':check('rehash-not-extra-assignments',b['metadata']['table']['writes']==3000 and b['metadata']['table']['shape']==3000)
        if c['button']=='meta':check('separate-metatable-version',b['metadata']['table']['metatable']==2 and b['metadata']['table']['writes']==0)
        if c['button']=='proxy':check('actual-destination-counted',b['metadata']['table']['writes']==2)
        if c['button']=='nil':check('nil-to-nil-no-shape-change',b['metadata']['table']['shape']==2)
    elif kind=='sort':check('sorted-values',[f['value']['value'] for f in s[2]['fields']]==[1,2,3]);check('sort-stores-captured',sum(f['write_version'] for f in s[2]['fields'])==s[2]['metadata']['table']['writes'] and s[2]['metadata']['table']['writes']>0)
    elif kind=='late':check('registration-boundary-explicit',s[1]['fields'][0]['write_version']==0 and delta(s[1],s[3],'amount')==2)
    elif kind=='native':check('native-double-write',delta(s[0],s[3],s[0]['fields'][0]['key'])==2)
    elif kind=='pointer':check('unselected-pointer-key-shape',delta(s[0],s[2],'amount')==0 and s[2]['metadata']['table']['writes']==1 and s[2]['metadata']['table']['shape']==1)
    elif kind=='destination':check('redirected-only-real-table-mutates',delta(s[0],s[3],'amount')==2 and delta(s[1],s[4],'amount')==0 and s[4]['metadata']['table']['writes']==0)
    elif kind=='shared-retire':check('remaining-owner-keeps-cell-identity',s[0]['metadata']['cell']==s[3]['metadata']['cell'] and cell(s[0],s[3])==1)
    elif kind=='aliases':check('aliases-share-table-field-versions',len({s[i]['metadata']['table']['lifetime'] for i in [0,1,2,4,5]})==1 and delta(s[0],s[4],'amount')==1 and s[4]['fields']==s[5]['fields'] and r['metadata'][1]['write_barrier']['selected_fields']==2)
    elif kind=='weak-key':check('weak-key-cleared-without-retaining-object',s[2]['metadata']['table']['shape']==1 and s[2]['metadata']['table']['gc']==1 and delta(s[0],s[2],'marker')==0 and bytes.fromhex(r['semantic']['draws'][1][0]['text_hex']).decode()=='count=1|marker=7')
    elif kind=='cell':check('open-initial-aba-captured',s[0]['metadata']['write_version']==4);check('closed-cell-exact-delta',cell(s[0],s[2])==c['delta']);check('closing-and-stack-move-observed',s[0]['metadata']['moves']>=2)
    elif kind=='shared':
        check('shared-actual-cell',len({s[i]['metadata']['cell'] for i in [0,1,4,5,7]})==1);check('two-closure-writes',cell(s[0],s[4])==2 and cell(s[1],s[5])==2);check('gc-no-value-write',cell(s[4],s[7])==0);check('open-aba-not-lost',s[0]['metadata']['write_version']==4 and s[0]['metadata']['moves']>=2)
    elif kind=='native-cell':check('c-setupvalue-captured',cell(s[0],s[3])==2)
    elif kind=='weak':
        check('weak-hash-and-array-clears',all(f['write_version']==1 and f['gc_writes']==1 and f['value']=={'type':'nil'} for f in s[2]['fields']));check('second-gc-no-phantom-clear',s[2]==s[4]);check('gc-shape',s[2]['metadata']['table']['shape']==2)
    elif kind=='replace':check('freed-table-watch-retired',r['metadata'][1]['write_barrier']['retired_tables']==1 and r['metadata'][1]['write_barrier']['selected_fields']==1);check('new-object-new-lifetime',s[0]['metadata']['table']['lifetime']!=s[2]['metadata']['table']['lifetime'] and s[2]['fields'][0]['write_version']==0);check('upvalue-reference-write',cell(s[0],s[2])==1)
    elif kind=='churn':
        watched=[v for v in s if 'fields'in v];check('fresh-object-lifetimes',len({v['metadata']['table']['lifetime'] for v in watched[:-1]})==31);check('last-owner-retired',r['metadata'][1]['write_barrier']['selected_fields']==1 and r['metadata'][1]['write_barrier']['retired_tables']==30);check('new-cell-not-old-version',watched[-1]['fields'][0]['write_version']==1 and r['metadata'][1]['write_barrier']['active_cells']<=5)
    elif kind=='rollback':
        check('versions-rebuilt-after-refusal',s[0]['fields']==s[5]['fields'] and cell(s[1],s[6])==1);check('world-save-draw-restored',r['semantic']['world']['coins']==1 and len(r['semantic']['world']['effects'])==1 and r['semantic']['stores']==c['stores'] and bytes.fromhex(r['semantic']['draws'][1][0]['text_hex']).decode()=='count=2|amount=2')
    elif kind=='join':check('native-join-fails-closed','error'in s[1] and s[0]['metadata']['write_version']==s[2]['metadata']['write_version'])
    elif kind=='rejected':check('explicit-rejection','error'in s[0])
    return out
def protected():
    r=old.protected();prior=json.loads((ROOT/'reports/boundary-handoff-final.json').read_text(encoding='utf-8'))
    for p,h in prior['inputs'].items():
        r[p]=old.digest(ROOT/p);assert r[p]==h,'Preserved handoff input changed: '+p
    for p,h in prior['binary_sha256'].items():
        r['build-boundary/Release/'+p]=old.digest(ROOT/'build-boundary/Release'/p);assert r['build-boundary/Release/'+p]==h,'Preserved handoff binary changed: '+p
    return r
def invoke(exe,manifest,c,mode):
    started=time.perf_counter()
    try:p=subprocess.run([str(exe),'--write-suite',str(ROOT),str(manifest),c['id'],mode],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,stderr='5-second child timeout; child killed and reaped',wall_seconds=time.perf_counter()-started),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Report output cap')
    return dict(returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace'),wall_seconds=time.perf_counter()-started),json.loads(p.stdout) if p.returncode==0 else None
def run(out):
    spec=json.loads(MANIFEST.read_text(encoding='utf-8'));source=json.loads((ROOT/'third_party/lua533/SOURCE.json').read_text())
    assert spec['work_limit']==10000000 and spec['timeout_seconds']==5
    for f in source['files']:assert old.digest(ROOT/'third_party/lua533'/f['path'])==f['sha256']
    derived=json.loads((ROOT/'build-write-barrier/generated/derived_sha256.json').read_text())
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-write-barrier/generated'/name)==h
    for exe in [EXE,REF]:
        raw=exe.read_bytes();off=struct.unpack_from('<I',raw,0x3c)[0];assert raw[off:off+4]==b'PE\0\0' and struct.unpack_from('<H',raw,off+4)[0]==0x14c
    for c in spec['cases']:assert old.digest(ROOT/c['source'])==c['source_sha256']
    out.mkdir(parents=True,exist_ok=False);before=protected();saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');start=time.perf_counter();rows=[]
    for c in spec['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline reached')
        artifacts=[];reports=[];ref=None
        if not c.get('candidate_only') and not c.get('reference_step_difference'):
            a,ref=invoke(REF,MANIFEST,c,'reference');artifacts.append(dict(mode='stock-reference',**a))
        for mode in range(2):
            a,r=invoke(EXE,MANIFEST,c,'boundary');artifacts.append(dict(mode='candidate-'+str(mode+1),**a));reports.append(r)
        check=[]
        if c.get('process_error'):check=[dict(check='work-limit-explicit',passed=all(a['returncode']!=0 and c['process_error'] in a['stderr'] for a in artifacts))]
        elif all(r is not None for r in reports):
            r,repeat=reports;check=checks(c,r);check+=[dict(check='repeat-versions-and-output',passed=r['steps']==repeat['steps'] and r['metadata']==repeat['metadata'] and r['semantic']==repeat['semantic'])]
            if not c.get('candidate_only') and not c.get('reference_step_difference'):check.append(dict(check='stock-ordinary-behavior',passed=ref is not None and ordinary(r)==ordinary(ref)))
            for n,v in enumerate(reports):check.append(dict(check='budget-and-no-full-trace-'+str(n),passed=v['budget']['limit']==10000000 and v['budget']['used']==sum(v['budget']['categories'].values()) and v['budget']['used']<=10000000 and not v['full_trace_enabled'] and not v['personal_draws_publishable'] and not v['automatic_projection_implemented'] and all(m['full_value_graph_nodes']==m['normal_audit_bytes']==0 and m['write_barrier']['historical_records']==0 for m in v['metadata'])))
        else:check=[dict(check='child-completed',passed=False)]
        row=dict(id=c['id'],kind=c['kind'],passed=all(x['passed'] for x in check),checks=check,artifacts=artifacts,stock_reference=ref,candidate_runs=reports);rows.append(row)
        old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'])),flush=True)
        if not row['passed']:break
    regressions=[]
    if all(r['passed'] for r in rows) and len(rows)==len(spec['cases']):
        original=json.loads(old.MANIFEST.read_text(encoding='utf-8'))
        for c in original['cases']:
            if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline reached')
            a,ref=invoke(REF,old.MANIFEST,c,'reference');b,candidate=invoke(EXE,old.MANIFEST,c,'boundary')
            if c.get('process_error'):passed=all(v['returncode']!=0 and c['process_error'] in v['stderr'] for v in [a,b]);tests=[]
            else:
                tests=old.assertions(c,candidate) if candidate else [];passed=ref is not None and candidate is not None and old.canonical(ref)==old.canonical(candidate) and all(v['passed'] for v in tests)
            regressions.append(dict(id=c['id'],passed=passed,checks=tests,artifacts=[a,b]))
            if not passed:break
    after=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');result=dict(schema='boundary-writes-gate-1',passed=len(rows)==len(spec['cases']) and all(r['passed'] for r in rows) and len(regressions)==18 and all(r['passed'] for r in regressions) and before==protected() and saves['files']==after['files'],cases=rows,regressions=regressions,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,protected_files_unchanged=before==protected(),save_files_unchanged=saves['files']==after['files'],automatic_projection_passed=False,consumer_read_sets_implemented=False,game_started=False,full_trace_enabled=False,manifest_sha256=old.digest(MANIFEST),driver_sha256=old.digest(Path(__file__)),binary_sha256={p.name:old.digest(p) for p in [EXE,REF]},derived_manifest_sha256=old.digest(ROOT/'build-write-barrier/generated/derived_sha256.json'))
    old.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps(dict(passed=result['passed'],cases=len(rows),regressions=len(regressions),seconds=result['seconds'])));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output.resolve())['passed'] else 1)
