"""Bounded numeric dependency handles; compare the sealed engine and stock Lua."""
import argparse,copy,json,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_reads as prior
import run_boundary_handoff as old
import run_boundary_writes as writes
import verify_boundary_reads
ROOT=old.ROOT;MANIFEST=ROOT/'research/compact_reads_v2.json';EXE=ROOT/'build-compact-read/Release/authority-compact-reads.exe'
BASE=prior.EXE;REF=prior.REF
def dictionary():return dict(op='field_dictionary')
def status(n=1):return dict(op='consumer_status',consumer=n,compact=True)
def freeze():
    cases=[]
    def case(name,steps,check='long',file='long_keys.lua',kind='functional',amounts=(1,2),**options):
        cfg=dict(keys=128,key_bytes=1024,consumers=12)|options.pop('configuration',{})
        p=ROOT/'research/compact_reads'/file
        cases.append(dict(id=name,source=p.relative_to(ROOT).as_posix(),source_sha256=old.digest(p),stores=[old.store(amounts[0],17,'en',**cfg),old.store(amounts[1],137,'zh',**cfg)],steps=steps,check=check,kind=kind,configuration=cfg,**options))
    for button,valid in [('sibling',True),('aba',False)]:
        case('shared-long-'+button,[prior.capture(),dictionary(),status(),status(12),old.dispatch(event=3,**{button:True}),status(),status(12)],expected_valid=valid)
    case('independent-swapped',[prior.capture(),dictionary(),status(),status(12)],amounts=(2,1),expected_valid=True)
    case('maximum-key',[prior.capture(),dictionary(),status(),status(12)],configuration=dict(keys=1,key_bytes=4096),expected_valid=True)
    case('key-limit-rejected',[dict(prior.capture(),expect_error='Read key capacity exceeded'),dictionary()],'rejected',kind='safety-rejection',configuration=dict(keys=1,key_bytes=4097,consumers=1))
    for count in [1,12]:
        case('replace-'+str(count),[prior.capture() for _ in range(20)]+[dictionary(),status()],'replacement',configuration=dict(consumers=count))
    case('rollback-index',[prior.capture(),dictionary(),status(),dict(prior.capture(fail=True),expect_error='compact-injected'),dictionary(),status()],'rollback',kind='safety-rejection')
    case('retired-and-recreated',[prior.capture(),dictionary(),status(),dict(op='gc'),dictionary(),status(),prior.capture(),dictionary(),status()],'retirement',file='ephemeral.lua')
    case('typed-and-nul',[prior.capture(),dictionary(),status(),old.dispatch(event=3),status()],'typed',file='typed.lua')
    case('rebuild-generation',[prior.capture(),dictionary(),status(),dict(op='rebuild'),dict(op='stale_handle',generation=2,expect_error='Stale context generation'),dictionary(),status()],'generation')
    case('execution-only-long',[prior.capture()],'measure')
    spec=dict(schema='compact-read-frozen-1',work_limit=10000000,timeout_seconds=5,batch_timeout_seconds=60,view_rule='personal-settings-authority-hud-v1',prior_manifest_sha256=old.digest(prior.MANIFEST),cases=cases)
    if MANIFEST.exists():assert json.loads(MANIFEST.read_text(encoding='utf-8'))==spec,'Frozen compact manifest differs'
    else:old.save(MANIFEST,spec)
    print(json.dumps(dict(frozen_cases=len(cases),manifest_sha256=old.digest(MANIFEST))))
def invoke(exe,manifest,c,mode='boundary'):
    started=time.perf_counter();cli='--compact-read-suite'if exe==EXE else '--read-suite'
    try:p=subprocess.run([str(exe),cli,str(ROOT),str(manifest),c['id'],mode],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,stderr='5-second timeout; killed and reaped',wall_seconds=time.perf_counter()-started),None
    except OSError as error:return dict(returncode=-10,stderr=str(error),wall_seconds=time.perf_counter()-started),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Child report exceeds 2 MiB')
    return dict(returncode=p.returncode,stderr=p.stderr.decode('utf-8',errors='replace'),wall_seconds=time.perf_counter()-started),json.loads(p.stdout)if p.returncode==0 else None
def comparable(report,case):
    rows=[]
    for s,v in zip(case['steps'],report['steps']):
        if s['op'] in ['field_dictionary','consumer_status']:continue
        v=copy.deepcopy(v);v.pop('metadata',None);rows.append(v)
    return dict(semantic=report['semantic'],steps=rows)
def normalized_statuses(report,case):
    keys={};result=[]
    for s,row in zip(case['steps'],report['steps']):
        if s['op']=='field_dictionary' and isinstance(row.get('metadata'),dict):
            keys={v['field']:v['key']for v in row['metadata']['fields']};continue
        if s['op']!='consumer_status' or not isinstance(row.get('metadata'),dict):continue
        m=copy.deepcopy(row['metadata'])
        for dep in m['dependencies']:
            field=dep.pop('field',None)
            if dep['kind']=='field':
                if not dep['live']:dep['key']=None
                elif field is not None:dep['key']=keys[field]
        m['dependencies'].sort(key=lambda d:json.dumps(d,sort_keys=True,ensure_ascii=False));result.append(m)
    return result
def checks(c,r):
    out=[];s=r['steps'];cfg=c['configuration'];metrics=r['metadata'][1];storage=metrics['compact_storage']
    def check(name,v):out.append(dict(check=name,passed=bool(v)))
    if c['check']=='measure':
        check('execution-only-no-expanded-diagnostics',len(s)==1 and len(s[0]['draws'])==cfg['consumers'])
        check('central-keys-without-consumer-copies',cfg['keys']*cfg['key_bytes']<=storage['owned_key_bytes']<=cfg['keys']*cfg['key_bytes']+256 and storage['consumer_key_bytes']==storage['identity_string_bytes']==0)
        check('live-index-matches-fields',storage['live_field_handles']==metrics['write_barrier']['selected_fields'])
        return out
    dictionaries=[v['metadata']for v in s if isinstance(v.get('metadata'),dict)and'fields'in v['metadata']]
    statuses=[v['metadata']for v in s if isinstance(v.get('metadata'),dict)and'dependencies'in v['metadata']]
    last=dictionaries[-1];entries=last['fields']
    check('live-handle-index-exact',storage['live_field_handles']==metrics['write_barrier']['selected_fields']==len(entries))
    check('one-owned-key-copy',storage['owned_key_bytes']==sum(len(v['key'].encode())for v in entries if isinstance(v['key'],str)))
    check('no-consumer-key-or-identity-strings',storage['consumer_key_bytes']==storage['identity_string_bytes']==0)
    ids={v['field']for v in entries};check('unique-current-handles',len(ids)==len(entries)and not storage['field_handle_reused'])
    for m in statuses:check('never-authorize-cache',m['reusable']is False)
    if c['check']in ['long','replacement','generation']:
        long=[v for v in entries if isinstance(v['key'],str)and len(v['key'])==cfg['key_bytes']]
        check('central-long-key-payload',len(long)==cfg['keys'] and sum(len(v['key'])for v in long)==cfg['keys']*cfg['key_bytes'])
        check('shared-owners',all(v['consumer_owners']==cfg['consumers']for v in long))
        amount=json.loads(c['stores'][1])['amount'];expected='sum='+str(cfg['keys']*(cfg['keys']+1)//2+cfg['keys']*amount)
        check('personal-output',all(bytes.fromhex(d['text_hex']).decode()==expected for d in r['steps'][0]['draws']) and len(r['steps'][0]['draws'])==cfg['consumers'])
        if c['check']=='long':check('exact-invalidation',all(m['versions_valid']for m in statuses[:2])and all(m['versions_valid']==c['expected_valid']for m in statuses[2:]))
        if c['check']=='replacement':check('latest-set-replaces-history',metrics['consumer_reads']['active_consumers']==cfg['consumers']and metrics['consumer_reads']['replaced_sets']==19*cfg['consumers']and statuses[-1]['versions_valid']);check('peak-key-payload-bounded',storage['peak_owned_key_bytes']==storage['owned_key_bytes'])
        if c['check']=='generation':check('generation-checked',dictionaries[0]['generation']!=last['generation']and'error'in s[4]and statuses[-1]['versions_valid'])
    elif c['check']=='rejected':check('capacity-restores-index','error'in s[0]and len(entries)==0 and metrics['consumer_reads']['active_consumers']==0)
    elif c['check']=='rollback':check('versions-restored',statuses[0]==statuses[1]and r['semantic']['stores']==c['stores']);check('new-generation-after-recovery',dictionaries[0]['generation']!=last['generation'])
    elif c['check']=='retirement':
        before,after,recreated=dictionaries
        oldid=next(v['field']for v in before['fields']if v['key']=='retired_value');newid=next(v['field']for v in recreated['fields']if v['key']=='retired_value')
        check('collected-handle-removed',oldid not in {v['field']for v in after['fields']}and not statuses[1]['versions_valid'])
        check('retired-handle-never-reused',newid>oldid and storage['retired_field_handles']>0 and statuses[-1]['versions_valid'])
    elif c['check']=='typed':
        check('typed-key-identities',len({(type(v['key']).__name__,str(v['key']))for v in entries})==len(entries)and any(v['key']=='nul\0key'for v in entries)and any(v['key']=='甲'for v in entries))
        check('numeric-only-invalidated',statuses[0]['versions_valid']and not statuses[1]['versions_valid']and sum(not d['valid']for d in statuses[1]['dependencies'])==1)
    return out
def protected():
    result=prior.protected();sealed=json.loads((ROOT/'reports/boundary-reads-final.json').read_text(encoding='utf-8'))
    for group in ['inputs','binaries']:
        for name,h in sealed[group].items():assert old.digest(ROOT/name)==h,'Sealed read file differs: '+name;result[name]=h
    return result
def run(out):
    verify_boundary_reads.main();spec=json.loads(MANIFEST.read_text(encoding='utf-8'));assert spec['work_limit']==10000000 and spec['timeout_seconds']==5
    derived=json.loads((ROOT/'build-compact-read/generated/derived_sha256.json').read_text())
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-compact-read/generated'/name)==h
    for c in spec['cases']:assert old.digest(ROOT/c['source'])==c['source_sha256']
    raw=EXE.read_bytes();off=struct.unpack_from('<I',raw,0x3c)[0];assert raw[off:off+4]==b'PE\0\0'and struct.unpack_from('<H',raw,off+4)[0]==0x14c
    binary_before=old.digest(EXE);before=protected();saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');out.mkdir(parents=True,exist_ok=False)
    baseline=copy.deepcopy(spec)
    for c in baseline['cases']:
        for i,s in enumerate(c['steps']):
            if s['op']=='field_dictionary':c['steps'][i]=dict(op='evaluate',code='return')
    old.save(out/'baseline-manifest.json',baseline);started=time.perf_counter();rows=[]
    layout=[]
    for name in ['compact-layout-probe-legacy.exe','compact-layout-probe.exe']:
        p=subprocess.run([str(EXE.with_name(name))],capture_output=True,timeout=5);assert p.returncode==0;layout.append(dict(executable_sha256=old.digest(EXE.with_name(name)),layout=json.loads(p.stdout)))
    assert layout[1]['layout']['dependency_bytes']<layout[0]['layout']['dependency_bytes']and layout[1]['layout']['map_value_bytes']<layout[0]['layout']['map_value_bytes']
    for c in spec['cases']:
        if time.perf_counter()-started>60:raise RuntimeError('Short batch deadline')
        artifacts=[];reports=[]
        for exe,m,mode in [(REF,out/'baseline-manifest.json','reference'),(BASE,out/'baseline-manifest.json','boundary'),(EXE,MANIFEST,'boundary'),(EXE,MANIFEST,'boundary')]:
            if exe==REF and c['check']=='rejected':artifacts.append(dict(executable=exe.name,skipped='The stock interpreter has no read-metadata capacity contract'));reports.append(None);continue
            a,v=invoke(exe,m,c,mode);artifacts.append(dict(executable=exe.name,**a));reports.append(v)
        ref,base,first,second=reports;tests=[]
        if all(v is not None for v in reports[1:])and(ref is not None or c['check']=='rejected'):
            tests=checks(c,first);tests+=[dict(check='prior-behavior-equal',passed=comparable(first,c)==comparable(base,c)),dict(check='same-read-validity-as-prior',passed=normalized_statuses(first,c)==normalized_statuses(base,c)),dict(check='repeat-handles-and-output',passed=all(first[k]==second[k]for k in ['steps','metadata','semantic']))]
            if ref is not None:tests.append(dict(check='stock-ordinary-behavior-equal',passed=comparable(first,c)==comparable(ref,c)))
            for v in [first,second]:tests.append(dict(check='limits-and-no-trace',passed=v['abi']=='ia-lua533-compact-reads-1'and v['compact_dependency_ids']and v['budget']['limit']==10000000 and v['budget']['used']<=10000000 and v['budget']['used']==sum(v['budget']['categories'].values())and not v['full_trace_enabled']and not v['cache_reuse_enabled']and not v['automatic_projection_implemented']and not v['personal_draws_publishable']))
        else:tests=[dict(check='children-completed',passed=False)]
        row=dict(id=c['id'],kind=c['kind'],passed=all(t['passed']for t in tests),checks=tests,artifacts=artifacts,reports=reports);rows.append(row);old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'])),flush=True)
        if not row['passed']:break
    regressions=[]
    if len(rows)==len(spec['cases'])and all(v['passed']for v in rows):
        for manifest,kind in [(prior.MANIFEST,'reads'),(writes.MANIFEST,'writes'),(old.MANIFEST,'handoff')]:
            for c in json.loads(manifest.read_text(encoding='utf-8'))['cases']:
                if time.perf_counter()-started>60:raise RuntimeError('Short batch deadline')
                a,v=invoke(EXE,manifest,c);tests=[]
                if c.get('process_error'):tests=[dict(check='work-rejected',passed=v is None and c['process_error']in a['stderr'])]
                elif v is None:tests=[dict(check='completed',passed=False)]
                else:tests=prior.checks(c,v)if kind=='reads'else writes.checks(c,v)if kind=='writes'else old.assertions(c,v)
                regressions.append(dict(id=c['id'],suite=kind,passed=all(t['passed']for t in tests),checks=tests,artifact=a))
                if not regressions[-1]['passed']:break
            if not regressions[-1]['passed']:break
    unchanged=before==protected();after_saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    result=dict(schema='compact-read-gate-1',passed=len(rows)==len(spec['cases'])and all(v['passed']for v in rows)and len(regressions)==106 and all(v['passed']for v in regressions)and unchanged and saves['files']==after_saves['files']and binary_before==old.digest(EXE),cases=rows,regressions=regressions,layout_probes=layout,seconds=time.perf_counter()-started,work_limit=10000000,child_timeout_seconds=5,protected_files_unchanged=unchanged,save_files_unchanged=saves['files']==after_saves['files'],binary_sha256=binary_before,manifest_sha256=old.digest(MANIFEST),driver_sha256=old.digest(Path(__file__)),derived_manifest_sha256=old.digest(ROOT/'build-compact-read/generated/derived_sha256.json'),automatic_projection_passed=False,consumer_cache_enabled=False,game_started=False)
    old.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps(dict(passed=result['passed'],cases=len(rows),regressions=len(regressions),seconds=result['seconds'])));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output.resolve())['passed']else 1)
