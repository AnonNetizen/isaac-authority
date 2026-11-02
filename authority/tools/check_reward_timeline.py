"""Bounded RNG authority contracts; reference Lua shares only the explicit model backend."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as world
import bounded_font_process
ROOT=world.ROOT;DIR=ROOT/'research/reward_timeline';MANIFEST=DIR/'suite-v5.json';CONTROLS=DIR/'controls-v5.json'
EXE=ROOT/'build-reward-timeline/Release/authority-reward.exe';REF=EXE.with_name('authority-reward-reference.exe')
OWNER='mods/reward-timeline-fixture'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--reward-timeline-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'])
    raw=a.pop('stdout');err=a.pop('stderr');a.update(stderr_hex=err.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest())
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def freeze():
    source=ROOT/'reward_timeline_runtime/fixture.lua';frozen=DIR/'main-v2.lua';world.parent.f.parent.frozen(frozen,source.read_bytes())
    base=copy.deepcopy(world.parent.f.load(ROOT/'research/authority_timeline/suite-v8.json')['cases'][2])
    for k in ['id','steps','authority_timeline','custom','settings','expected_world_refs','values','owner']:base.pop(k,None)
    base.update(source=frozen.relative_to(ROOT).as_posix(),source_sha256=sha(frozen),modules=dict(entry=0,roots=[dict(root=DIR.relative_to(ROOT).as_posix(),display=OWNER,sha256={'main.lua':sha(frozen)},source_paths={'main.lua':frozen.relative_to(ROOT).as_posix()})]))
    settings=[dict(amount=1,x=17,language='en',low=1,high=9,seed=123,draw=False),dict(amount=2,x=137,language='zh',low=21,high=29,seed=999,draw=True)]
    base['mod_sdk']['stores']=[{OWNER:json.dumps(v,separators=(',',':'))}for v in settings]
    cases=[];controls=[]
    def host(e,f=1,**kw):return dict(world.dispatch(f,e,'host',**kw),phase='authority')
    def personal(e,f=1,**kw):return dict(world.dispatch(f,e,**kw),phase='presentation')
    def link(e,ae=None,view='replay',f=1):return {f'personal:presentation:{e}:{f}':dict(authority=f'host:authority:{ae or e}:{f}',view=view,project_hud=True)}
    def observe(role='host'):return world.ev('return RewardValue,RewardSecond,SeedReturns,UIState,TimelinePlayer:GetData().counter,tostring(RewardValue),InspectReward()',role=role)
    def case(name,e,extra=None,**kw):
        steps=[host(e),personal(e),personal(102),observe('personal')];links=dict(link(e),**link(102,e,'end'))
        if extra:steps,links=extra
        c=copy.deepcopy(base);c.update(id=name,steps=steps,authority_timeline=dict(schema='authority-state-timeline-1',links=links),settings=copy.deepcopy(settings[1]),event=e,**kw);cases.append(c)
        return c
    case('seeded-integer-host-bounds-personal-settings-independent',101,expected_draw_calls=1,expected_seed_calls=1,expected_refs=1,expected_seed_refs=1)
    case('zero-argument-float-preserves-host-result',103,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0,float_result=True)
    case('one-argument-cached-random-preserves-host-result',104,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0)
    case('same-line-two-results-keep-distinct-identities',105,expected_draw_calls=2,expected_seed_calls=0,expected_refs=2,expected_seed_refs=0)
    case('one-result-two-world-consumers-is-one-random-value',106,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0)
    case('resolved-random-comparison-has-same-hud-path',107,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0,branch_proof=True)
    case('different-config-operands-same-boolean-path-proven',108,expected_draw_calls=0,expected_seed_calls=0,expected_refs=0,expected_seed_refs=0,branch_proof=True,amount_world=True)
    case('divergent-game-view-branch-still-explicitly-rejected',109,([host(109),personal(109,expect_error='HUD control flow requires dual-view branch resolution'),observe('personal')],link(109)),boundary=True,rollback_private=True)
    case('failed-host-restores-rng-world-and-save',110,([host(110,expect_error='reward-host-injected'),observe('host')],{}),boundary=True,rollback_host=True,expected_draw_calls=0,expected_seed_calls=0)
    case('failed-personal-after-save-private-and-draw-restores-all',111,([host(111),personal(111,expect_error='reward-personal-injected'),observe('personal')],link(111)),boundary=True,rollback_private=True,expected_draw_calls=1,expected_seed_calls=0)
    case('reset-seed-two-equal-values-distinct-operations',112,expected_draw_calls=2,expected_seed_calls=2,expected_refs=2,expected_seed_refs=2,equal_rewards=True)
    case('personal-added-random-has-no-authority-operation',113,([host(113),personal(113,expect_error='Timeline world operation correspondence not unique'),observe('personal')],link(113)),boundary=True,rollback_private=True,expected_draw_calls=1,expected_seed_calls=0)
    case('unregistered-time-source-remains-rejected',114,([host(114,expect_error='Unregistered timeline random or time source')],{}),boundary=True,expected_draw_calls=0,expected_seed_calls=0)
    case('empty-random-interval-restores-frame',115,([host(115,expect_error='Random interval unsupported')],{}),boundary=True,expected_draw_calls=0,expected_seed_calls=0)
    case('one-result-multiple-hud-reads-never-draws-again',116,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0)
    case('seed-has-zero-native-returns',117,expected_draw_calls=0,expected_seed_calls=1,expected_refs=0,expected_seed_refs=1)
    case('noninteger-random-bound-rejected',118,([host(118,expect_error='Expected integer')],{}),boundary=True,expected_draw_calls=0,expected_seed_calls=0)
    case('excess-random-arity-rejected',119,([host(119,expect_error='Random interval arity unsupported')],{}),boundary=True,expected_draw_calls=0,expected_seed_calls=0)
    case('duplicate-replay-and-hud-return-cached-results',101,([host(101),personal(101),personal(101),personal(102),personal(102),observe('personal')],dict(link(101),**link(102,101,'end'))),expected_draw_calls=1,expected_seed_calls=1,expected_refs=1,expected_seed_refs=1)
    case('reconstruction-recreates-authority-values',101,([host(101),personal(101),dict(op='rebuild'),personal(102),observe('personal')],dict(link(101),**link(102,101,'end'))),expected_draw_calls=1,expected_seed_calls=1,expected_refs=1,expected_seed_refs=1)
    c=case('host-personal-settings-swapped-not-fixed-value',101,expected_draw_calls=1,expected_seed_calls=1,expected_refs=1,expected_seed_refs=1)
    swapped=[dict(settings[0],amount=2,seed=999,low=21,high=29),dict(settings[1],amount=1,seed=123,low=1,high=9)];c['mod_sdk']['stores']=[{OWNER:json.dumps(v,separators=(',',':'))}for v in swapped];c['settings']=swapped[1]
    case('integral-float-bounds-follow-lua-integer-conversion',120,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0)
    case('numeric-string-bounds-follow-lua-integer-conversion',121,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0)
    case('reward-times-personal-setting-projects-host-game-view',122,expected_draw_calls=1,expected_seed_calls=0,expected_refs=1,expected_seed_refs=0,personal_arithmetic=True)
    case('old-frame-random-reference-does-not-rewind-new-generator',101,([host(101),host(105,2),dict(op='timeline_state',frame_key='host:authority:101:1'),personal(101),personal(102),observe('personal')],dict(link(101),**link(102,101,'end'))),expected_draw_calls=3,expected_seed_calls=1,expected_refs=1,expected_seed_refs=1,old_frame='host:authority:101:1')
    case('same-frame-different-payload-refuses-without-new-random',101,([host(101),personal(101),personal(101,input=world.device(76),expect_error='Menu frame identity reused with different payload'),personal(102),observe('personal')],dict(link(101),**link(102,101,'end'))),expected_draw_calls=1,expected_seed_calls=1,expected_refs=1,expected_seed_refs=1)
    for c in cases:
        instrumented=[]
        for s in c['steps']:
            instrumented.append(s)
            if s.get('role')=='personal'and s.get('op')=='dispatch'and'expect_error'not in s:instrumented.append(dict(op='reward_state',role='personal'))
        c['steps']=instrumented
        control=copy.deepcopy(c);control.pop('authority_timeline');control['steps']=[s for s in c['steps']if s.get('role')=='host'and s.get('phase')=='authority'and'expect_error'not in s]+[observe('host')];controls.append(control)
    world.parent.f.freeze_json(MANIFEST,dict(schema='reward-timeline-suite-1',work_limit=10000000,timeout_seconds=5,cases=cases));world.parent.f.freeze_json(CONTROLS,dict(schema='reward-timeline-controls-1',work_limit=10000000,timeout_seconds=5,cases=controls));print(json.dumps(dict(frozen=True,cases=len(cases))))
    original=copy.deepcopy(world.parent.f.load(ROOT/'research/authority_timeline/suite-v8.json'));original['cases']=original['cases'][:2];world.parent.f.freeze_json(DIR/'original-gates-v1.json',original)
def returns(r):return [s['values']for s in r['steps']if'values'in s][-1]
def draw_text(r):return [bytes.fromhex(d['text_hex']).decode('utf-8')for s in r['steps']for d in s.get('draws',[])]
def run(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(MANIFEST)['cases']:
        a,control=invoke(CONTROLS,c,True);pairs=[invoke(MANIFEST,c)for _ in range(2)];reports=[r for _,r in pairs];r=reports[0];checks={}
        checks['bounded-completed']=all(x['returncode']==0 and not x['timed_out']and not x['output_limit_exceeded']and not x['reader_failures']and p is not None and'semantic'in p for x,p in [(a,control),*pairs])
        if checks['bounded-completed']:
            checks['host-world-rng-and-effects-once']=r['semantic']['world']==control['semantic']['world']and r['semantic']['menu_snapshot']==control['semantic']['menu_snapshot']
            settings=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][OWNER]['data_hex']));checks['personal-config-unchanged']=settings==c['settings']
            checks['repeat-state-and-proof-identities']=all(r[k]==reports[1][k]for k in ['semantic','steps','authority_timeline','timeline_proofs','reward_proofs'])
            for key in ['draw','seed']:
                if f'expected_{key}_calls'in c:checks[f'{key}-logical-call-count']=r['semantic']['world'][f'rng_{key}_calls']==c[f'expected_{key}_calls']
            proofs=[p for s in r['steps']if'timeline'in s for p in s['timeline']['proofs']]
            if not c.get('boundary'):
                pv,hv=returns(r),returns(control)
                if c.get('old_frame'):
                    old=next(s for s in r['steps']if s.get('key')==c['old_frame']);actual=next(o['actual']['result']for o in old['operations']if o['signature']['api']=='math.random');hv=[actual,*world.values(None,0)]
                if c.get('personal_arithmetic'):checks['ordinary-personal-computation-preserved']=pv[0]['value']==hv[0]['value']*c['settings']['amount']
                else:checks['personal-reward-is-host-value']=pv[:3]==hv[:3]
                rp=r['reward_proofs'][1];checks['exact-rng-reference-counts']=rp['random_result_references']==c['expected_refs']and rp['seed_references']==c['expected_seed_refs']
                reward=hv[0].get('value',0);second=hv[1].get('value',0);coins=old['states'][-1]['coins']if c.get('old_frame')else control['semantic']['world']['coins'];texts=draw_text(r)
                if c.get('float_result'):
                    expected_float=bytes.fromhex(hv[5]['hex']).decode('utf-8');checks['host-float-display-exact']=bool(texts)and all(t==f'zh|reward={expected_float}|second=0|coins={coins}|state=initial'for t in texts)
                else:checks['hud-exact-reward-layout-and-language']=texts and all(t.startswith(f'zh|reward={reward}|second={second}|coins={coins}|state=')for t in texts)and all(d['x']==137 for s in r['steps']for d in s.get('draws',[]))
                if c.get('equal_rewards'):checks['seed-reset-values-equal-distinct-producers']=hv[0]==hv[1]and len({p['authority_operation']for p in proofs if p['kind']=='random-result-reference'})==2
                if c.get('branch_proof'):
                    checks['comparison-path-proof-present']=any(p['kind']=='reward-branch-proof'and p['same_path_proven']for p in proofs)
                    state='positive'if c.get('amount_world')else'big'if reward>4 else'small';checks['exact-branch-content']=bool(texts)and all(t.endswith('|state='+state)for t in texts)
                refs=[p for p in proofs if p['kind']=='random-result-reference'];checks['replay-never-generates-random']=len({p['authority_operation']for p in refs})==c['expected_refs']and all(not p['generator_executed']for p in refs)
                states=[s['rng_sha256']for s in r['steps']if'reward'in s];checks['personal-references-leave-generator-unchanged']=all(h==control['semantic']['world']['rng_sha256']for h in states)
            if c.get('rollback_private'):checks['private-save-and-state-restored']=returns(r)[3:5]==world.values(None,None)and returns(r)[6:]==world.values(0,0,'initial')and not draw_text(r)
            if c.get('rollback_host'):checks['failed-host-save-restored']=r['semantic']['mod_stores'][0]==control['semantic']['mod_stores'][0]and returns(r)[:5]==world.values(None,None,None,None,None)and returns(r)[6:]==world.values(0,0,'initial')
            checks['formal-resource-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for p in [control,*reports])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,boundary_diagnostic=c.get('boundary',False),checks=checks,reports=reports,artifacts=[x for x,_ in pairs],stock_control=control,stock_artifact=a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection();result=dict(schema='reward-timeline-results-1',passed=all(c['passed']for c in rows),functional_cases=sum(not c['boundary_diagnostic']for c in rows),boundary_diagnostic_cases=sum(c['boundary_diagnostic']for c in rows),cases=rows,manifest_sha256=sha(MANIFEST),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,playable=False,general_mod_compatibility_gate_passed=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','regressions','real-init','original-gates']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':sys.exit(0 if run(a.output)else 1)
    elif a.phase=='original-gates':
        import check_authority_timeline as original
        original.MANIFEST=DIR/'original-gates-v1.json';original.EXE=EXE;original.REF=REF;original.invoke=invoke;sys.exit(0 if original.run(a.output)else 1)
    else:
        world.EXE=EXE;world.REF=REF;world.invoke=invoke;path=ROOT/'research/sparse_value/real-init-v1.json'if a.phase=='real-init'else world.MANIFEST
        sys.exit(0 if world.run(path,a.output)else 1)
