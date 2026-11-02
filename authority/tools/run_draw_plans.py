"""Actual API sites plus bounded syntactic recipes. No bound-value claim."""
import argparse,copy,json,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_compact_reads as compact
import run_boundary_handoff as old
import inspect_draw_plans as recipes
ROOT=old.ROOT;MANIFEST=ROOT/'research/draw_plans_v3.json'
def capture(**buttons):return dict(op='capture_plans',event=2,phase='presentation',input=buttons)
def freeze():
    cases=[]
    def case(name,file,check='symbolic',buttons=None,**extra):
        p=ROOT/'research/compact_reads'/file
        steps=[capture(**(buttons or{}))]
        if extra.get('error'):steps[0]['expect_error']=extra['error']
        cases.append(dict(id=name,source=p.relative_to(ROOT).as_posix(),source_sha256=old.digest(p),stores=[old.store(1,17,'en'),old.store(2,137,'zh')],steps=steps,check=check,**extra))
    case('ordered-operands-shared-producer','draw_templates.lua',check='operands')
    case('helper-parameters','draw_helper.lua',check='parameters')
    case('helper-result-unresolved','draw_return.lua',check='unresolved',reason='call-result')
    for value in [False,True]:case('branch-'+str(value).lower(),'draw_branch.lua',check='unresolved',buttons=dict(branch=value),reason='control-flow')
    case('loop-unresolved','draw_loop.lua',check='unresolved',reason='control-flow')
    case('C-trampoline-unresolved','draw_trampoline.lua',check='unresolved',reason='C-trampoline')
    case('tail-call-site','draw_tail.lua',check='tail')
    case('site-limit','draw_limit.lua',check='rejected',error='Draw plan site capacity exceeded')
    case('captured-local-write-unresolved','draw_captured_write.lua',check='unresolved',reason='captured-register')
    case('global-node-limit','draw_node_limit.lua',check='analysis-rejected',reason='global node capacity exceeded')
    spec=dict(schema='draw-plans-frozen-1',work_limit=10000000,timeout_seconds=5,batch_timeout_seconds=60,bindings_verified=False,projection_allowed=False,cases=cases)
    if MANIFEST.exists():assert json.loads(MANIFEST.read_text(encoding='utf-8'))==spec
    else:old.save(MANIFEST,spec)
    print(json.dumps(dict(frozen_cases=len(cases),manifest_sha256=old.digest(MANIFEST))))
def graph_nodes(plan,site):return plan['prototypes'][site['prototype']]['nodes']
def reachable(nodes,root):
    seen=set()
    def visit(n):
        if n in seen:return
        if not 0<=n<len(nodes):raise RuntimeError('Recipe edge outside node pool')
        seen.add(n);v=nodes[n];kind=v['kind'];edges=[]
        if kind=='binary':edges=[v['left'],v['right']]
        elif kind=='query':edges=[v['table'],v['key']]
        elif kind=='concat':edges=v['operands']
        elif kind=='unary':edges=[v['operand']]
        for e in edges:visit(e)
    visit(root);return seen
def query_keys(nodes,root):
    out={}
    for i in reachable(nodes,root):
        n=nodes[i]
        if n['kind']=='query':
            key=nodes[n['key']]
            if key['kind']=='constant'and key['value']['type']=='string':out[i]=bytes.fromhex(key['value']['hex']).decode('utf-8')
    return out
def check_plan(c,report,plan):
    tests=[]
    def check(name,v):tests.append(dict(check=name,passed=bool(v)))
    sites=plan['sites'];draws=report['steps'][0]['draws']
    check('actual-draws-have-sites',len(sites)==len(draws));check('no-bound-values-or-projection',not plan['bindings_verified']and not plan['projection_allowed']and all(not s['bindings_verified']and not s['projection_allowed']for s in sites))
    if c['check']=='unresolved':check('unresolved-diagnostic-only',all(s['status']=='unresolved'and c['reason']in s['reason']for s in sites))
    else:check('symbolic-structure-only',all(s['status']=='symbolic-only'for s in sites))
    if c['check']=='operands':
        a,b,raw=sites;nodes=graph_nodes(plan,a);x=nodes[a['roots']['x']];y=nodes[a['roots']['y']];reverse=nodes[b['roots']['y']]
        check('two-actual-sites-one-frozen-line',a['pc']!=b['pc']and a['prototype']==b['prototype'])
        check('text-use-sites-distinct',set(query_keys(nodes,a['roots']['text']).values())=={'amount'}and set(query_keys(nodes,b['roots']['text']).values())=={'amount','language'})
        check('shared-producer-preserved',bool(set(query_keys(nodes,a['roots']['text']))&set(query_keys(nodes,b['roots']['text']))))
        check('ordered-subtraction',y['operator']==reverse['operator']=='SUB'and nodes[y['left']]['value']=={'type':'integer','value':100}and nodes[reverse['right']]['value']=={'type':'integer','value':100})
        check('positions-not-text-heuristics',x['operator']=='ADD'and set(query_keys(nodes,a['roots']['x']).values())=={'x'})
        check('raw-literal-bytes',any(nodes[i].get('value',{}).get('hex')=='72617700ff'for i in reachable(nodes,raw['roots']['text'])))
        check('ordinary-personal-draws',[(v['text_hex'],v['x'],v['y'])for v in draws]==[('417c32',140,98),('427c322f7a68',274,37),('72617700ff7a68',0,1)])
    if c['check']=='parameters':
        nodes=graph_nodes(plan,sites[0]);check('caller-bindings-left-unproven',[nodes[sites[0]['roots'][n]]['kind']for n in ['text','x','y']]==['parameter']*3)
    if c['check']=='tail':check('actual-tail-instruction',report['steps'][0]['metadata']['sites'][0]['opcode']==37)
    expected={'captured-local-write-unresolved':('actual=7',137,0),'helper-result-unresolved':('N9',137,0),'branch-false':('branch',127,0),'branch-true':('branch',147,0),'loop-unresolved':('T3',137,0),'C-trampoline-unresolved':('P',137,0)}
    if c['id']in expected:
        text,x,y=expected[c['id']];check('counterexample-preserves-actual-output',[(v['text_hex'],v['x'],v['y'])for v in draws]==[(text.encode().hex(),x,y)])
    return tests
def ordinary(r):return dict(semantic=r['semantic'],steps=[{k:v for k,v in s.items()if k!='metadata'}for s in r['steps']])
def run(out):
    spec=json.loads(MANIFEST.read_text(encoding='utf-8'));before=compact.protected();exe_hash=old.digest(compact.EXE)
    for c in spec['cases']:assert old.digest(ROOT/c['source'])==c['source_sha256']
    out.mkdir(parents=True,exist_ok=False);baseline=copy.deepcopy(spec)
    for c in baseline['cases']:
        for s in c['steps']:s['op']='capture_reads'
    old.save(out/'baseline-manifest.json',baseline);start=time.perf_counter();rows=[]
    for c in spec['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short draw-plan batch deadline')
        artifacts=[];reports=[]
        for exe,m,mode in [(compact.REF,out/'baseline-manifest.json','reference'),(compact.BASE,out/'baseline-manifest.json','boundary'),(compact.EXE,MANIFEST,'boundary'),(compact.EXE,MANIFEST,'boundary')]:
            if c['check']=='rejected'and exe!=compact.EXE:reports.append(None);artifacts.append(dict(executable=exe.name,skipped='New optional prototype/site capacity'));continue
            a,r=compact.invoke(exe,m,c,mode);artifacts.append(dict(executable=exe.name,**a));reports.append(r)
        ref,base,first,second=reports;tests=[];plans=[]
        if first is not None and second is not None:
            if c['check']=='rejected':tests=[dict(check='site-limit-recovers',passed='error'in first['steps'][0]and first['semantic']['draws'][1]==[]and first['metadata'][1]['consumer_reads']['active_consumers']==0)]
            elif c['check']=='analysis-rejected':
                for r in [first,second]:
                    try:recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']);tests.append(dict(check='global-analysis-limit',passed=False))
                    except RuntimeError as e:tests.append(dict(check='global-analysis-limit',passed=c['reason']in str(e)))
                tests.append(dict(check='native-world-and-draws-unchanged',passed=ref is not None and base is not None and ordinary(first)==ordinary(base)==ordinary(ref)))
            else:
                for r in [first,second]:plans.append(recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']))
                tests=check_plan(c,first,plans[0]);tests.append(dict(check='ordinary-Lua-and-prior-equal',passed=ref is not None and base is not None and ordinary(first)==ordinary(base)==ordinary(ref)))
                tests.append(dict(check='repeat-recipes',passed=plans[0]==plans[1]and first['steps']==second['steps']))
                tests.append(dict(check='runtime-plus-analysis-budget',passed=all(r['budget']['used']+p['analysis_work']<=10000000 for r,p in zip([first,second],plans))))
                sample=first['steps'][0]['metadata']
                try:recipes.inspect(sample,0);raise AssertionError('Missing analysis budget rejection')
                except RuntimeError as e:tests.append(dict(check='analysis-zero-budget-rejects',passed='work limit'in str(e)))
                corrupted=copy.deepcopy(sample);fingerprint=next(iter(corrupted['prototypes']));raw=corrupted['prototypes'][fingerprint];corrupted['prototypes'][fingerprint]=('00'if raw[:2]!='00'else'01')+raw[2:]
                try:recipes.inspect(corrupted,10000000-first['budget']['used']);raise AssertionError('Missing immutable-image rejection')
                except RuntimeError as e:tests.append(dict(check='altered-image-rejected',passed='hash mismatch'in str(e)))
            tests.append(dict(check='projection-remains-closed',passed=all(not r['automatic_projection_implemented']and not r['personal_draws_publishable']and not r['full_trace_enabled']for r in [first,second])))
        else:tests=[dict(check='native-completed',passed=False)]
        row=dict(id=c['id'],kind=c['check'],passed=all(t['passed']for t in tests),checks=tests,artifacts=artifacts,native_reports=reports,recipes=plans);rows.append(row);old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'])),flush=True)
        if not row['passed']:break
    result=dict(schema='draw-plan-structure-gate-1',passed=len(rows)==len(spec['cases'])and all(v['passed']for v in rows)and before==compact.protected()and exe_hash==old.digest(compact.EXE),scope='API sites and symbolic bytecode recipes only',bindings_verified=False,automatic_projection_passed=False,consumer_cache_enabled=False,cases=rows,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,manifest_sha256=old.digest(MANIFEST),driver_sha256=old.digest(Path(__file__)),inspector_sha256=old.digest(Path(recipes.__file__)),binary_sha256=exe_hash,protected_files_unchanged=before==compact.protected())
    old.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps(dict(passed=result['passed'],cases=len(rows),seconds=result['seconds'])));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:
        target=a.output.resolve();existed=target.exists()
        try:sys.exit(0 if run(target)['passed']else 1)
        except Exception as error:
            if not existed and target.is_dir():old.save(target/'failure.json',dict(classification='interrupted-analysis',error=type(error).__name__+': '+str(error),driver_sha256=old.digest(Path(__file__)),inspector_sha256=old.digest(Path(recipes.__file__)),binary_sha256=old.digest(compact.EXE),bindings_verified=False))
            raise
