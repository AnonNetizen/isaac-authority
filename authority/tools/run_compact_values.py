"""Typed observation gate and bounded paired CPU benchmarks. No projection."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_bound_values as b
import verify_bound_values
ROOT=b.ROOT;EXE=ROOT/'build-compact-value/Release/authority-compact-values.exe';MANIFEST=ROOT/'research/compact_values_v1.json';BENCH=ROOT/'research/compact_values_bench_v1.json'

def freeze():
    folder=ROOT/'research/compact_values';folder.mkdir(exist_ok=True)
    sources={
      'cow.lua':"local m=RegisterMod('Copy On Write Versions',1)\nlocal cfg=require('json').decode(m:LoadData())\nm:AddCallback(2,function()for i=1,3 do local a=cfg.amount;Isaac.RenderText('amount='..a,cfg.x,0);cfg.amount=cfg.amount+1 end end)\n",
      'owned_strings.lua':"local m=RegisterMod('Owned Observation Strings',1)\nlocal cfg=require('json').decode(m:LoadData())\nm:AddCallback(2,function()for i=1,3 do cfg.text=string.rep(string.char(96+i),2048);Isaac.RenderText(cfg.text,cfg.x,0)end;cfg.text=nil;collectgarbage('collect')end)\n"}
    spec=copy.deepcopy(json.loads(b.MANIFEST.read_text(encoding='utf-8')))
    for name,source in sources.items():
        p=folder/name
        if p.exists():assert p.read_text(encoding='utf-8')==source
        else:p.write_text(source,encoding='utf-8')
        spec['cases'].append(dict(id=name[:-4],source=p.relative_to(ROOT).as_posix(),source_sha256=b.old.digest(p),stores=[b.old.store(1,17,'en'),b.old.store()],steps=[b.cap()],kind='unresolved',reason='control-flow'))
    c=copy.deepcopy(spec['cases'][0]);c.update(id='wire-encoding',steps=[dict(op='source_wire_probe')],kind='encoding-probe');spec['cases'].append(c);spec['schema']='compact-value-frozen-1'
    if MANIFEST.exists():assert json.loads(MANIFEST.read_text(encoding='utf-8'))==spec
    else:b.old.save(MANIFEST,spec)
    original=ROOT/'build-bound-measurement/source/million-reads.lua';text=original.read_text(encoding='utf-8');assert text.count('1000000')==1
    cases=[]
    for count in [20000,200000]:
        p=folder/f'reads_{count}.lua';source=text.replace('1000000',str(count))
        if p.exists():assert p.read_text(encoding='utf-8')==source
        else:p.write_text(source,encoding='utf-8')
        for bindings in [False,True]:cases.append(dict(id=f'reads-{count}-'+('on'if bindings else'off'),source=p.relative_to(ROOT).as_posix(),source_sha256=b.old.digest(p),count=count,bindings=bindings,stores=[b.old.store(1,17,'en'),b.old.store()],steps=[b.cap()if bindings else dict(op='capture_reads',event=2,phase='presentation',input={})]))
    bench=dict(schema='compact-value-benchmark-1',work_limit=10000000,timeout_seconds=5,derived_from=original.relative_to(ROOT).as_posix(),derived_source_sha256=b.old.digest(original),cases=cases)
    if BENCH.exists():assert json.loads(BENCH.read_text(encoding='utf-8'))==bench
    else:b.old.save(BENCH,bench)
    print(json.dumps(dict(cases=len(spec['cases']),benchmark_cases=len(cases))))

def invoke(manifest,c,exe=EXE):
    if exe!=EXE:return b.invoke(exe,manifest,c)
    start=time.perf_counter()
    try:p=subprocess.run([str(exe),'--compact-value-suite',str(ROOT),str(manifest),c['id'],'boundary'],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,stderr='5-second timeout; killed and reaped',wall_seconds=time.perf_counter()-start),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Model output capacity')
    return dict(returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace'),wall_seconds=time.perf_counter()-start),json.loads(p.stdout)if p.returncode==0 else None

def protected():
    verify_bound_values.main();r=b.protected();v=json.loads((ROOT/'reports/bound-values-final.json').read_text(encoding='utf-8'))
    for group in ['inputs','binaries']:
        for p,h in v[group].items():assert b.old.digest(ROOT/p)==h;r[p]=h
    return r
def proof(capture,draws,path,remaining):
    plan=b.recipes.inspect(capture,remaining);remaining-=plan['analysis_work'];artifact,v=b.verify(dict(capture=capture,recipes=plan,draws=draws),path,remaining)
    if v is None:raise RuntimeError('Independent value verifier failed: '+artifact['stderr'])
    return v,plan,artifact

def run(out):
    before=protected();out.mkdir(exist_ok=False,parents=True);spec=json.loads(MANIFEST.read_text(encoding='utf-8'));rows=[];start=time.perf_counter();saved=b.old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    for c in spec['cases']:
        assert b.old.digest(ROOT/c['source'])==c['source_sha256'];artifacts=[];reports=[]
        for exe in [b.EXE,EXE,EXE]:
            if c['kind']=='encoding-probe'and exe==b.EXE:a,r=dict(skipped='new encoding probe'),None
            else:a,r=invoke(MANIFEST,c,exe)
            artifacts.append(a);reports.append(r)
        old,first,second=reports;checks=[];proofs=[];plans=[]
        if first is None or second is None:checks=[dict(check='completed',passed=False)]
        elif c['kind']=='encoding-probe':checks=[dict(check='wire-count-versus-real-json',passed=first['steps'][0]['wire_bytes_equal_json']and first['steps'][0]['checked']==252 and first['steps']==second['steps'])]
        else:
            for r in [first,second]:
                remaining=10000000-r['budget']['used'];values=[];templates=[]
                for step in r['steps']:
                    if step.get('metadata',{}).get('observed_sources'):
                        v,p,_=proof(step['metadata'],step['draws'],out/'verification-request.json',remaining);remaining-=p['analysis_work']+v['used_work'];values.append(v);templates.append(p)
                assert remaining>=0;proofs.append(values);plans.append(templates)
            checks=b.checks(c,first,proofs[0]);checks+=[dict(check='prior-ordinary-and-observations-equal',passed=old is not None and b.draws.ordinary(old)==b.draws.ordinary(first)and old['steps']==first['steps']),dict(check='repeat-observations',passed=first['steps']==second['steps']),dict(check='repeat-independent-verification',passed=[{k:v for k,v in p.items()if k!='seconds'}for p in proofs[0]]==[{k:v for k,v in p.items()if k!='seconds'}for p in proofs[1]])]
            metric=first['metadata'][1]['source_capture'];checks.append(dict(check='json-only-at-export',passed=metric['hot_path_json_objects']==metric['hot_path_serializations']==0))
            if c['id']=='cow':checks.append(dict(check='snapshots-preserve-old-versions',passed=metric['copy_on_write']>0 and [bytes.fromhex(d['text_hex']).decode()for d in first['steps'][0]['draws']]==['amount=2','amount=3','amount=4']))
            if c['id']=='owned_strings':checks.append(dict(check='strings-survive-replacement-and-gc',passed=[bytes.fromhex(d['text_hex'])for d in first['steps'][0]['draws']]==[bytes([n])*2048 for n in [97,98,99]]))
        if first is not None:checks.append(dict(check='formal-limits-and-closed-gates',passed=first['abi']=='ia-lua533-compact-values-1'and first['budget']['limit']==10000000 and first['budget']['used']==sum(first['budget']['categories'].values())and not first['full_trace_enabled']and not first['automatic_projection_implemented']and not first['personal_draws_publishable']))
        row=dict(id=c['id'],kind=c['kind'],passed=all(x['passed']for x in checks),checks=checks,artifacts=artifacts,reports=reports,verification=proofs,plans=plans);rows.append(row);b.old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'])),flush=True)
        if not row['passed']:break
    faults=[]
    if len(rows)==24 and all(r['passed']for r in rows):
        seed=rows[0]['reports'][1]['steps'][0];request0=dict(capture=seed['metadata'],recipes=rows[0]['plans'][0][0],draws=seed['draws'])
        for kind in ['capture-hash','query-key','source-value','source-namespace','missing-version','operand-order','constant-payload','zero-budget']:
            request=copy.deepcopy(request0);expected=None;available=10000000-rows[0]['reports'][1]['budget']['used'];records=request['capture']['sites'][0]['source_snapshot']['records'];field=next(r for r in records if r['kind']=='query'and r['key'].get('hex')=='616d6f756e74');nodes=request['recipes']['prototypes'][request['recipes']['sites'][0]['prototype']]['nodes']
            if kind=='capture-hash':expected=b.fingerprint(request['capture']);field['value']['value']=3
            elif kind=='query-key':field['key']['hex']='78'
            elif kind=='source-value':field['value']['value']=3
            elif kind=='source-namespace':field['capture']+=1
            elif kind=='missing-version':field.pop('version')
            elif kind=='operand-order':n=next(n for n in nodes if n.get('operator')=='ADD');n['left'],n['right']=n['right'],n['left']
            elif kind=='constant-payload':next(n for n in nodes if n.get('value')=={'type':'integer','value':100})['value']['value']=99
            else:available=0
            artifact,v=b.verify(request,out/'fault-request.json',available,expected);rejected=v is None if kind in ['capture-hash','zero-budget']else v is not None and not v['all_frame_values_verified'];faults.append(dict(id=kind,passed=rejected,artifact=artifact,verification=v))
    regressions=[]
    if len(rows)==24 and all(r['passed']for r in rows):
        for path,kind in [(b.reads.MANIFEST,'reads'),(b.writes.MANIFEST,'writes'),(b.old.MANIFEST,'handoff'),(b.compact.MANIFEST,'compact'),(b.draws.MANIFEST,'draw-plans')]:
            for c in json.loads(path.read_text(encoding='utf-8'))['cases']:
                if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline')
                a,r=invoke(path,c)
                if c.get('process_error'):checks=[dict(check='work-rejection',passed=r is None and c['process_error']in a['stderr'])]
                elif r is None:checks=[dict(check='completed',passed=False)]
                elif kind=='draw-plans':
                    if c['check']=='rejected':checks=[dict(check='site-capacity',passed=c['error']in r['steps'][0].get('error',''))]
                    elif c['check']=='analysis-rejected':
                        try:b.recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']);checks=[dict(check='node-capacity',passed=False)]
                        except RuntimeError as e:checks=[dict(check='node-capacity',passed=c['reason']in str(e))]
                    else:checks=b.draws.check_plan(c,r,b.recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']))
                else:checks=b.reads.checks(c,r)if kind=='reads'else b.writes.checks(c,r)if kind=='writes'else b.old.assertions(c,r)if kind=='handoff'else b.compact.checks(c,r)
                regressions.append(dict(id=c['id'],suite=kind,passed=all(x['passed']for x in checks),checks=checks,artifact=a))
                if not regressions[-1]['passed']:break
            if not regressions[-1]['passed']:break
    result=dict(schema='compact-value-gate-1',passed=len(rows)==24 and all(r['passed']for r in rows)and len(faults)==8 and all(f['passed']for f in faults)and len(regressions)==129 and all(r['passed']for r in regressions),cases=rows,faults=faults,regressions=regressions,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,full_trace_enabled=False,consumer_cache_enabled=False,authority_projection_passed=False,game_started=False,protected_files_unchanged=before==protected(),save_files_unchanged=saved['files']==b.old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')['files'],binary_sha256=b.old.digest(EXE),driver_sha256=b.old.digest(Path(__file__)),manifest_sha256=b.old.digest(MANIFEST))
    result['passed']=result['passed']and result['protected_files_unchanged']and result['save_files_unchanged'];b.old.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps(dict(passed=result['passed'],cases=len(rows),regressions=len(regressions),seconds=result['seconds'])));return result

def bench(out):
    before=protected();out.mkdir(exist_ok=False,parents=True);spec=json.loads(BENCH.read_text(encoding='utf-8'));rows=[]
    for c in spec['cases']:
        assert b.old.digest(ROOT/c['source'])==c['source_sha256'];reports=[];artifacts=[]
        # The old observer's known-slow 200k sample is deliberately not run.
        targets=([b.EXE]*2 if c['count']==20000 else[])+[EXE]*3
        for exe in targets:
            a,r=invoke(BENCH,c,exe);reports.append(r);artifacts.append(dict(executable=exe.name,**a))
        completed=all(r is not None for r in reports);checks=[]
        if completed:
            checks=[dict(check='ordinary-equal',passed=all(r['semantic']==reports[0]['semantic']for r in reports)),dict(check='original-charges-preserved',passed=all(r['budget']['used']==reports[0]['budget']['used']for r in reports)),dict(check='under-formal-limits',passed=all(r['budget']['used']<=10000000 and r['budget']['limit']==10000000 for r in reports))]
            if c['bindings']:checks.append(dict(check='bounded-inplace-records',passed=all(r['metadata'][1]['source_capture']['created']<32 and r['metadata'][1]['source_capture']['inplace_updates']>=c['count']-1 and r['metadata'][1]['source_capture']['hot_path_serializations']==0 for r in reports[-3:])))
        else:checks=[dict(check='completed-within-5-seconds',passed=False)]
        row=dict(id=c['id'],passed=all(x['passed']for x in checks),checks=checks,artifacts=artifacts,reports=reports);rows.append(row);print(json.dumps(dict(id=c['id'],passed=row['passed'],native_seconds=[r['seconds']if r else None for r in reports])),flush=True)
        if not row['passed']:break
    result=dict(schema='compact-value-short-benchmark-1',passed=len(rows)==4 and all(r['passed']for r in rows)and before==protected(),cases=rows,work_limit=10000000,child_timeout_seconds=5,unbounded_retry=False,binary_sha256=b.old.digest(EXE),driver_sha256=b.old.digest(Path(__file__)),manifest_sha256=b.old.digest(BENCH));b.old.save(out/'result.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','bench']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if(run if a.phase=='run'else bench)(a.output.resolve())['passed']else 1)
