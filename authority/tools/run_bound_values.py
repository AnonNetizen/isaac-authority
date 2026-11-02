"""Captured read-time values + independent stock Lua verification. No projection."""
import argparse,copy,hashlib,json,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_compact_reads as compact
import run_draw_plans as draws
import run_boundary_reads as reads
import run_boundary_writes as writes
import run_boundary_handoff as old
import inspect_draw_plans as recipes
import verify_compact_reads
ROOT=old.ROOT;MANIFEST=ROOT/'research/bound_values_v2.json';EXE=ROOT/'build-bound-value/Release/authority-bound-values.exe';VERIFY=EXE.with_name('authority-verify-values.exe')
def cap(**buttons):return dict(op='capture_bindings',event=2,phase='presentation',input=buttons)
def freeze():
    cases=[]
    def case(name,source,steps=None,kind='verified',**extra):
        p=ROOT/source;cases.append(dict(id=name,source=source,source_sha256=old.digest(p),stores=[old.store(1,17,'en'),old.store()],steps=steps or[cap()],kind=kind,**extra))
    case('operands-and-bytes','research/compact_reads/draw_templates.lua')
    case('unicode-personal','research/compact_reads/draw_templates.lua',language='中文')
    case('observed-helper-parameters','research/compact_reads/draw_helper.lua')
    case('tail-C-draw','research/compact_reads/draw_tail.lua')
    for name in ['temporal','aba','nested','activations','arithmetic']:case(name,'research/bound_values/'+name+'.lua')
    case('cached-across-frames','research/bound_values/cached.lua',[cap(),old.dispatch(event=3),cap()])
    for name,file,reason in [('helper-result','draw_return.lua','call-result'),('branch','draw_branch.lua','control-flow'),('loop','draw_loop.lua','control-flow'),('C-trampoline','draw_trampoline.lua','C-trampoline'),('captured-writer','draw_captured_write.lua','captured-register')]:case(name,'research/compact_reads/'+file,kind='unresolved',reason=reason)
    case('metamethod-result','research/bound_values/metamethod.lua',kind='unresolved',reason='Metamethod result proof')
    case('rollback-after-save-draw','research/bound_values/rollback.lua',[cap(),dict(cap(fail=True),expect_error='bound-injected'),cap()],kind='rollback')
    case('payload-capacity','research/bound_values/capacity.lua',[dict(cap(),expect_error='Source observation capacity exceeded')],kind='native-rejection')
    case('returned-records-and-gc','research/bound_values/release.lua',kind='unresolved',reason='control-flow')
    case('caught-error-frame-pruning','research/bound_values/caught_error.lua')
    case('repeated-capture-release','research/bound_values/cached.lua',[cap()for _ in range(24)])
    for c in cases:
        if c.get('language'):
            cfg=json.loads(c['stores'][1]);cfg['language']=c['language'];c['stores'][1]=json.dumps(cfg,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    spec=dict(schema='observed-values-frozen-1',work_limit=10000000,timeout_seconds=5,batch_timeout_seconds=60,origins_verified=False,authority_projection_allowed=False,cases=cases)
    if MANIFEST.exists():assert json.loads(MANIFEST.read_text(encoding='utf-8'))==spec
    else:old.save(MANIFEST,spec)
    print(json.dumps(dict(frozen_cases=len(cases),manifest_sha256=old.digest(MANIFEST))))
def invoke(exe,manifest,c,mode='boundary'):
    start=time.perf_counter();cli='--bound-value-suite'if exe==EXE else '--compact-read-suite'if exe==compact.EXE else '--read-suite'
    try:p=subprocess.run([str(exe),cli,str(ROOT),str(manifest),c['id'],mode],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,stderr='5-second native timeout; killed and reaped',wall_seconds=time.perf_counter()-start),None
    except OSError as e:return dict(returncode=-10,stderr=str(e),wall_seconds=time.perf_counter()-start),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Native output capacity')
    return dict(returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace'),wall_seconds=time.perf_counter()-start),json.loads(p.stdout)if p.returncode==0 else None
def fingerprint(capture):return hashlib.sha256(json.dumps(capture,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def repeat_metadata(rows):
    rows=copy.deepcopy(rows)
    for row in rows:
        # Lua's incremental collector can run at different allocation points.
        # Keep actual identities, versions, live sets and snapshots byte-equal;
        # only these storage high-water statistics are allocator observations.
        if isinstance(row.get('write_barrier'),dict):row['write_barrier'].pop('peak_fields',None)
        if isinstance(row.get('compact_storage'),dict):row['compact_storage'].pop('peak_owned_key_bytes',None)
    return rows
def verify(request,path,available,expected=None):
    old.save(path,request);start=time.perf_counter()
    try:p=subprocess.run([str(VERIFY),str(path),str(available),expected or fingerprint(request['capture'])],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,stderr='5-second verification timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Verifier output capacity')
    return dict(returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace'),wall_seconds=time.perf_counter()-start),json.loads(p.stdout)if p.returncode==0 else None
def checks(c,native,proofs):
    out=[]
    def check(name,v):out.append(dict(check=name,passed=bool(v)))
    if c['kind']=='native-rejection':check('capture-capacity-rolls-back',native['steps'][0].get('error')=='Source observation capacity exceeded'and native['semantic']['stores']==c['stores']and native['semantic']['draws'][1]==[]and native['metadata'][1]['source_capture']['live_records']==0);return out
    if c['kind']=='verified':check('observed-frame-values-equal',all(p['all_frame_values_verified']for p in proofs))
    else:
        # Rollback is a native restoration test. Its unchanged source contains an
        # input branch, so it must not be counted as a verified expression.
        reason='control-flow'if c['kind']=='rollback'else c['reason']
        check('missing-proof-stays-unresolved',all(not p['all_frame_values_verified']and any(reason in s.get('error','')for s in p['sites'])for p in proofs))
    for p in proofs:check('no-authority-or-reuse-claim',not p['origins_verified']and not p['authority_projection_allowed']and not p['cache_reuse_allowed']and all(not s['origins_verified']and not s['authority_projection_allowed']and not s['cache_reuse_allowed']for s in p['sites']))
    if c['id']=='temporal':
        refs=[s['source_references']for s in proofs[0]['sites']];amount=lambda r:r.get('kind')=='query'and r['key'].get('hex')=='616d6f756e74'
        check('read-time-versions-not-final-state',any(amount(r)and r['version']==0 and r['value'].get('value')==2 for r in refs[0])and any(amount(r)and r['version']==1 and r['value'].get('value')==3 for r in refs[1]))
    if c['id']=='aba':
        rows=[r for s in proofs[0]['sites']for r in s['source_references']if r.get('kind')=='query'and r['key'].get('hex')=='616d6f756e74'];check('equal-values-different-write-versions',{r['version']for r in rows}=={0,2}and{r['value']['value']for r in rows}=={2})
    if c['id']=='activations':
        sites=native['steps'][0]['metadata']['sites'];check('same-helper-distinct-activations',len({s['prototype']for s in sites})==1 and len({s['source_snapshot']['activation']for s in sites})==2)
    if c['id']=='cached-across-frames':
        first,last=native['steps'][0],native['steps'][2];check('cached-value-not-recomputed-from-later-setting',first['draws'][0]['text_hex']==last['draws'][0]['text_hex']=='736565647c32'and last['draws'][0]['x']==147)
        check('capture-namespace-advances',first['metadata']['sites'][0]['source_snapshot']['capture']!=last['metadata']['sites'][0]['source_snapshot']['capture'])
    if c['kind']=='rollback':check('private-state-save-and-draw-restored',native['semantic']['stores']==c['stores']and bytes.fromhex(native['steps'][2]['draws'][0]['text_hex']).decode()=='count=2|amount=2')
    metrics=native['metadata'][1]['source_capture'];check('bounded-live-state-after-return',not metrics['active']and metrics['active_frames']==0 and metrics['live_records']<=4096 and metrics['live_bytes']<=262144 and metrics['snapshot_entries']<=16384)
    if c['id']=='returned-records-and-gc':check('unconsumed-returned-records-released',metrics['created']>=256 and metrics['peak_records']<32 and metrics['live_records']<16)
    if c['id']=='caught-error-frame-pruning':check('caught-error-not-escaped-or-retained',metrics['created']>metrics['live_records']and metrics['active_frames']==0 and native['steps'][0]['draws'][0]['text_hex']=='636175676874')
    if c['id']=='repeated-capture-release':check('latest-frame-only',metrics['capture']==24 and metrics['created']==metrics['peak_records']==metrics['live_records']and metrics['draw_snapshots']==1 and len(native['steps'])==24)
    return out
def protected():
    result=compact.protected();sealed=json.loads((ROOT/'reports/compact-read-final.json').read_text(encoding='utf-8'))
    for group in ['inputs','binaries']:
        for p,h in sealed[group].items():assert old.digest(ROOT/p)==h;result[p]=h
    return result
def run(out):
    verify_compact_reads.main();spec=json.loads(MANIFEST.read_text(encoding='utf-8'))
    derived=json.loads((ROOT/'build-bound-value/generated/derived_sha256.json').read_text());assert old.digest(ROOT/'reports/compact-read-final.json')==derived['compact_final_sha256']
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-bound-value/generated'/name)==h
    for c in spec['cases']:assert old.digest(ROOT/c['source'])==c['source_sha256']
    for exe in [EXE,VERIFY]:
        raw=exe.read_bytes();off=struct.unpack_from('<I',raw,0x3c)[0];assert raw[off:off+4]==b'PE\0\0'and struct.unpack_from('<H',raw,off+4)[0]==0x14c
    out.mkdir(parents=True,exist_ok=False);before=protected();saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');binary_before={p.name:old.digest(p)for p in [EXE,VERIFY]};baseline=copy.deepcopy(spec)
    for c in baseline['cases']:
        for s in c['steps']:
            if s['op']=='capture_bindings':s['op']='capture_reads'
    old.save(out/'baseline-manifest.json',baseline);start=time.perf_counter();rows=[];faults=[];first_request=None;first_native=None
    for c in spec['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline')
        artifacts=[];reports=[]
        for exe,m,mode in [(compact.REF,out/'baseline-manifest.json','reference'),(compact.EXE,out/'baseline-manifest.json','boundary'),(EXE,MANIFEST,'boundary'),(EXE,MANIFEST,'boundary')]:
            if c['kind']=='native-rejection'and exe!=EXE:artifacts.append(dict(executable=exe.name,skipped='New source-payload cap'));reports.append(None);continue
            a,r=invoke(exe,m,c,mode);artifacts.append(dict(executable=exe.name,**a));reports.append(r)
        ref,base,first,second=reports;tests=[];all_proofs=[];all_plans=[];verification_artifacts=[]
        if first is not None and second is not None:
            for r in [first,second]:
                proofs=[];plans=[];remaining=10000000-r['budget']['used']
                for step in r['steps']:
                    if not step.get('metadata',{}).get('observed_sources'):continue
                    p=recipes.inspect(step['metadata'],remaining);remaining-=p['analysis_work'];request=dict(capture=step['metadata'],recipes=p,draws=step['draws']);a,proof=verify(request,out/'verification-request.json',remaining);verification_artifacts.append(a)
                    if proof is None:raise RuntimeError('Verifier failed: '+a['stderr'])
                    remaining-=proof['used_work'];proofs.append(proof);plans.append(p)
                    if first_request is None and proof['all_frame_values_verified']:first_request=copy.deepcopy(request);first_native=r
                assert remaining>=0;all_proofs.append(proofs);all_plans.append(plans)
            tests=checks(c,first,all_proofs[0]);tests.append(dict(check='repeat-captured-versions',passed=first['steps']==second['steps']and first['semantic']==second['semantic']and repeat_metadata(first['metadata'])==repeat_metadata(second['metadata'])))
            tests.append(dict(check='repeat-verified-results',passed=[{k:v for k,v in p.items()if k!='seconds'}for p in all_proofs[0]]==[{k:v for k,v in p.items()if k!='seconds'}for p in all_proofs[1]]))
            if ref is not None:tests.append(dict(check='stock-and-prior-ordinary-behavior',passed=draws.ordinary(first)==draws.ordinary(ref)==draws.ordinary(base)))
            tests.append(dict(check='formal-limit-and-gates',passed=first['abi']=='ia-lua533-bound-values-1'and first['budget']['limit']==10000000 and first['budget']['used']==sum(first['budget']['categories'].values())and not first['full_trace_enabled']and not first['automatic_projection_implemented']and not first['personal_draws_publishable']))
        else:tests=[dict(check='native-completed',passed=False)]
        row=dict(id=c['id'],kind=c['kind'],passed=all(t['passed']for t in tests),checks=tests,artifacts=artifacts,native_reports=reports,plans=all_plans,verification=all_proofs,verification_artifacts=verification_artifacts);rows.append(row);old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'])),flush=True)
        if not row['passed']:break
    if len(rows)==len(spec['cases'])and all(r['passed']for r in rows):
        for kind in ['capture-hash','query-key','source-value','source-namespace','missing-version','operand-order','constant-payload','zero-budget']:
            request=copy.deepcopy(first_request);expected=None;available=10000000-first_native['budget']['used']
            records=request['capture']['sites'][0]['source_snapshot']['records'];pool=request['recipes']['prototypes'][request['recipes']['sites'][0]['prototype']]['nodes'];field=next(r for r in records if r['kind']=='query'and r['key'].get('hex')=='616d6f756e74')
            if kind=='capture-hash':expected=fingerprint(request['capture']);field['value']['value']=3
            elif kind=='query-key':field['key']['hex']='78'
            elif kind=='source-value':field['value']['value']=3
            elif kind=='source-namespace':field['capture']+=1
            elif kind=='missing-version':field.pop('version')
            elif kind=='operand-order':n=next(n for n in pool if n.get('operator')=='ADD');n['left'],n['right']=n['right'],n['left']
            elif kind=='constant-payload':n=next(n for n in pool if n.get('value')=={'type':'integer','value':100});n['value']['value']=99
            elif kind=='zero-budget':available=0
            a,v=verify(request,out/'fault-request.json',available,expected);rejected=v is None if kind in ['capture-hash','zero-budget']else v is not None and not v['all_frame_values_verified'];faults.append(dict(id=kind,passed=rejected,artifact=a,verification=v))
            if not rejected:break
    regressions=[]
    if len(rows)==len(spec['cases'])and all(r['passed']for r in rows)and len(faults)==8 and all(f['passed']for f in faults):
        for manifest,kind in [(reads.MANIFEST,'reads'),(writes.MANIFEST,'writes'),(old.MANIFEST,'handoff'),(compact.MANIFEST,'compact'),(draws.MANIFEST,'draw-plans')]:
            for c in json.loads(manifest.read_text(encoding='utf-8'))['cases']:
                if time.perf_counter()-start>60:raise RuntimeError('Short batch deadline')
                a,r=invoke(EXE,manifest,c)
                if c.get('process_error'):tests=[dict(check='work-limit',passed=r is None and c['process_error']in a['stderr'])]
                elif r is None:tests=[dict(check='completed',passed=False)]
                elif kind=='draw-plans':
                    if c['check']=='rejected':tests=[dict(check='site-limit-recovers',passed=c['error']in r['steps'][0].get('error','')and r['semantic']['draws'][1]==[])]
                    elif c['check']=='analysis-rejected':
                        try:recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']);tests=[dict(check='analysis-capacity-rejects',passed=False)]
                        except RuntimeError as e:tests=[dict(check='analysis-capacity-rejects',passed=c['reason']in str(e))]
                    else:tests=draws.check_plan(c,r,recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']))
                else:tests=reads.checks(c,r)if kind=='reads'else writes.checks(c,r)if kind=='writes'else old.assertions(c,r)if kind=='handoff'else compact.checks(c,r)
                regressions.append(dict(id=c['id'],suite=kind,passed=all(v['passed']for v in tests),checks=tests,artifact=a))
                if not regressions[-1]['passed']:break
            if not regressions[-1]['passed']:break
    after=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');result=dict(schema='observed-binding-gate-1',passed=len(rows)==len(spec['cases'])and all(r['passed']for r in rows)and len(faults)==8 and all(f['passed']for f in faults)and len(regressions)==129 and all(r['passed']for r in regressions)and before==protected()and saves['files']==after['files']and binary_before=={p.name:old.digest(p)for p in [EXE,VERIFY]},cases=rows,faults=faults,regressions=regressions,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,origins_verified=False,authority_projection_allowed=False,consumer_cache_enabled=False,game_started=False,protected_files_unchanged=before==protected(),save_files_unchanged=saves['files']==after['files'],binary_sha256=binary_before,manifest_sha256=old.digest(MANIFEST),driver_sha256=old.digest(Path(__file__)),inspector_sha256=old.digest(Path(recipes.__file__)),derived_manifest_sha256=old.digest(ROOT/'build-bound-value/generated/derived_sha256.json'))
    old.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps(dict(passed=result['passed'],cases=len(rows),faults=len(faults),regressions=len(regressions),seconds=result['seconds'])));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:
        target=a.output.resolve();existed=target.exists()
        try:sys.exit(0 if run(target)['passed']else 1)
        except Exception as error:
            if not existed and target.is_dir():old.save(target/'failure.json',dict(classification='interrupted-observed-value-gate',error=type(error).__name__+': '+str(error),driver_sha256=old.digest(Path(__file__)),capture_binary_sha256=old.digest(EXE),verifier_binary_sha256=old.digest(VERIFY),authority_projection_allowed=False))
            raise
