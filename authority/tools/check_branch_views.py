"""Isolated persistent presentation branch execution, with unchanged frozen source controls."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as world
import bounded_font_process
ROOT=world.ROOT;DIR=ROOT/'research/branch_views';MANIFEST=DIR/'suite-v2.json';CONTROLS=DIR/'controls-v2.json'
EXE=ROOT/'build-branch-views/Release/authority-branch-views.exe';REF=EXE.with_name('authority-branch-views-reference.exe');OWNER='mods/branch-views-fixture'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--branch-views-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary']);raw=a.pop('stdout');err=a.pop('stderr');a.update(stderr_hex=err.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest())
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def freeze():
    source=ROOT/'branch_views_runtime/fixture.lua';frozen=DIR/'main.lua';world.parent.f.parent.frozen(frozen,source.read_bytes())
    parent=world.parent.f.load(ROOT/'research/authority_timeline/suite-v8.json');original=copy.deepcopy(next(c for c in parent['cases']if c['id']=='reward-controlled-hud-needs-branch-resolution'))
    cases=[];controls=[]
    original['id']='original-reward-controlled-hud-source-now-selects-host-one';original['authority_timeline']['branch_views']=True
    for s in original['steps']:s.pop('expect_error',None)
    original.update(expected_frames=[['one']],branch_source_unchanged=True);original.pop('boundary_rejection',None);original.pop('required_compatibility',None);cases.append(original)
    swapped=copy.deepcopy(original);swapped['id']='original-source-settings-swapped-select-host-other';swapped['expected_frames']=[['other']]
    owner='mods/authority-timeline-fixture';hostsettings=json.loads(swapped['mod_sdk']['stores'][0][owner]);hostsettings['amount']=2;swapped['mod_sdk']['stores'][0][owner]=json.dumps(hostsettings,separators=(',',':'));swapped['settings']['amount']=1;private=json.loads(swapped['mod_sdk']['stores'][1][owner]);private['amount']=1;swapped['mod_sdk']['stores'][1][owner]=json.dumps(private,separators=(',',':'));cases.append(swapped)
    base=copy.deepcopy(original)
    for k in ['id','steps','authority_timeline','custom','settings','expected_frames','owner','branch_source_unchanged']:base.pop(k,None)
    base.update(source=frozen.relative_to(ROOT).as_posix(),source_sha256=sha(frozen),modules=dict(entry=0,roots=[dict(root=DIR.relative_to(ROOT).as_posix(),display=OWNER,sha256={'main.lua':sha(frozen)})]))
    settings=[dict(amount=1,x=17,language='en'),dict(amount=2,x=137,language='zh')];base['mod_sdk']['stores']=[{OWNER:json.dumps(s,separators=(',',':'))}for s in settings]
    def host(e=201,f=1,**kw):return dict(world.dispatch(f,e,'host',**kw),phase='authority')
    def personal(e=202,f=1,**kw):return dict(world.dispatch(f,e,**kw),phase='presentation')
    def links(steps,event=201):return {f'personal:presentation:{s["event"]}:{s["frame_id"]}':dict(authority=f'host:authority:{event}:1',view='end',project_hud=True)for s in steps if s.get('role')=='personal'and s['op']=='dispatch'}
    def case(name,steps,texts,ordinary=None,present=None,**kw):
        c=copy.deepcopy(base);c.update(id=name,steps=steps+[world.ev('return Inspect()'),dict(op='branch_observe',code='return Inspect()')],authority_timeline=dict(schema='authority-state-timeline-1',links=links(steps,kw.pop('authority_event',201)),branch_views=True),owner=OWNER,settings=copy.deepcopy(settings[1]),expected_frames=texts,ordinary_values=world.values(*ordinary)if ordinary is not None else None,presentation_values=world.values(*present)if present is not None else None,**kw);cases.append(c);return c
    def text(ui='one',hits=1,count=1,amount=1,language='zh'):return f'{language}|amount={amount}|ui={ui}|hits={hits}|count={count}'
    case('divergent-ui-branch-keeps-personal-state-and-config',[host(),personal()],[[text()]],ordinary=[2,137,'zh',1,'other',2,1],present=[2,137,'zh',1,'one',1,1],expected_x=[137])
    case('personal-input-and-save-survive-display-branch-selection',[host(),personal(input=world.device(76))],[[text()]],ordinary=[2,147,'zh',1,'other',2,1],present=[2,147,'zh',1,'one',1,1],saved=dict(amount=2,x=147,language='zh'),expected_x=[147])
    case('two-persistent-private-views-survive-next-callback',[host(),personal(),personal(203)],[[text()],[text()]],ordinary=[2,137,'zh',1,'other',2,1],present=[2,137,'zh',1,'one',1,1],expected_x=[137,137])
    case('cross-frame-display-state-and-personal-input-remain-independent',[host(),personal(),personal(f=2,input=world.device(76)),personal(203)],[[text()],[text(hits=2,count=2)],[text(hits=2,count=2)]],ordinary=[2,147,'zh',2,'other',4,2],present=[2,147,'zh',2,'one',2,2],saved=dict(amount=2,x=147,language='zh'),expected_x=[137,147,147])
    case('reward-controls-layout-with-personal-coordinate-base',[host(),personal(204)],[[text(hits=0,count=0)]],ordinary=[2,139,'zh',0,'other',0,None],present=[2,138,'zh',0,'one',0,None],saved=dict(amount=2,x=139,language='zh'),expected_x=[138])
    case('branch-local-setting-writes-never-publish-shadow-save',[host(),personal(205)],[[text(hits=0,count=0)]],ordinary=[202,137,'zh',0,'other',0,None],present=[102,137,'zh',0,'one',0,None],saved=dict(amount=202,x=137,language='zh'),expected_x=[137])
    case('aliased-table-helper-return-selects-game-view',[host(),personal(206)],[[text(hits=0,count=0)]],ordinary=[2,137,'zh',0,'other',0,None],present=[2,137,'zh',0,'one',0,None],expected_x=[137])
    case('ordinary-language-input-is-not-overwritten-by-game-view',[host(),personal(212,input=world.device(76))],[[text(hits=0,count=0,language='custom')]],ordinary=[2,147,'custom',0,'other',0,None],present=[2,147,'custom',0,'one',0,None],saved=dict(amount=2,x=147,language='custom'),expected_x=[147])
    case('duplicate-frame-caches-both-view-results',[host(),personal(input=world.device(76)),personal(input=world.device(76))],[[text()],[text()]],ordinary=[2,147,'zh',1,'other',2,1],present=[2,147,'zh',1,'one',1,1],saved=dict(amount=2,x=147,language='zh'),expected_x=[147,147])
    case('history-rebuild-restores-both-private-views',[host(),personal(),dict(op='rebuild'),personal(203)],[[text()],[text()]],ordinary=[2,137,'zh',1,'other',2,1],present=[2,137,'zh',1,'one',1,1],expected_x=[137,137])
    case('configuration-reload-without-sidecar-remains-rejected',[host(),personal(input=world.device(76)),dict(op='reload_saved',expect_error='Branch view configuration reload requires sidecar reconstruction'),personal(203)],[[text()],[text()]],ordinary=[2,147,'zh',1,'other',2,1],present=[2,147,'zh',1,'one',1,1],saved=dict(amount=2,x=147,language='zh'),expected_x=[147,147],boundary=True)
    for name,event,error,authority_event in [
        ('presentation-failure-restores-both-lanes-and-save',207,'presentation-only-injected',201),
        ('ambiguous-world-contributions-do-not-select-a-branch',202,'HUD authority contribution not unique',208),
        ('unknown-branch-operand-is-not-assumed-a-constant',209,'Branch game operand literal provenance unavailable',201),
        ('changed-branch-budget-restores-all-pending-effects',210,'Presentation changed-branch budget exceeded',201),
        ('lua-pcall-cannot-hide-projection-evidence-failure',211,'Branch game operand literal provenance unavailable',201),
    ]:
        followup=personal(203,expect_error='HUD authority contribution not unique')if authority_event==208 else personal(203)
        case(name,[host(authority_event),personal(event,expect_error=error),followup],[]if authority_event==208 else[[text(ui='initial',hits=0,count=0)]],ordinary=[2,137,'zh',0,'initial',0,None],present=[2,137,'zh',0,'initial',0,None],expected_x=[]if authority_event==208 else[137],boundary=True,authority_event=authority_event,allow_no_choice=True)
    rewards=world.parent.f.load(ROOT/'research/reward_timeline/suite-v5.json')['cases']
    for id in ['seeded-integer-host-bounds-personal-settings-independent','resolved-random-comparison-has-same-hud-path']:
        c=copy.deepcopy(next(c for c in rewards if c['id']==id));c.update(id='three-lane-'+id,reward_model=True,allow_no_choice=True);c['authority_timeline']['branch_views']=True;c['steps'].append(dict(op='branch_observe',code='return InspectReward()'));cases.append(c)
    for c in cases:
        control=copy.deepcopy(c);control.pop('authority_timeline');control['steps']=[s for s in c['steps']if s.get('role')=='host'and s.get('phase')=='authority']
        if c.get('reward_model'):control['steps'].append(world.ev('return RewardValue,RewardSecond,SeedReturns',role='host'))
        controls.append(control)
    world.parent.f.freeze_json(MANIFEST,dict(schema='branch-views-suite-1',work_limit=10000000,timeout_seconds=5,cases=cases));world.parent.f.freeze_json(CONTROLS,dict(schema='branch-views-controls-1',work_limit=10000000,timeout_seconds=5,cases=controls));print(json.dumps(dict(frozen=True,cases=len(cases))))
    init=copy.deepcopy(world.parent.f.load(ROOT/'research/sparse_value/real-init-v1.json'));init_control=copy.deepcopy(init)
    for c in init['cases']:c['authority_timeline']=dict(schema='authority-state-timeline-1',links={},branch_views=True)
    world.parent.f.freeze_json(DIR/'init-v1.json',init);world.parent.f.freeze_json(DIR/'init-controls-v1.json',init_control)
    original=copy.deepcopy(parent);original['cases']=original['cases'][:2]
    for c in original['cases']:c['authority_timeline']['branch_views']=True
    world.parent.f.freeze_json(DIR/'original-gates-v1.json',original)
def run(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(MANIFEST)['cases']:
        a,control=invoke(CONTROLS,c,True);pairs=[invoke(MANIFEST,c)for _ in range(2)];reports=[r for _,r in pairs];r=reports[0];checks={}
        checks['bounded-completed']=all(x['returncode']==0 and not x['timed_out']and not x['output_limit_exceeded']and not x['reader_failures']and p is not None and'semantic'in p for x,p in [(a,control),*pairs])
        if checks['bounded-completed']:
            checks['world-rng-effects-host-only']=r['semantic']['world']==control['semantic']['world']and r['semantic']['menu_snapshot']==control['semantic']['menu_snapshot']and r['branch_views']['game_world_unchanged_by_projection']
            frames=[s['draws']for s in r['steps']if'draws'in s];texts=[[bytes.fromhex(d['text_hex']).decode('utf-8')for d in frame]for frame in frames]
            if c.get('reward_model'):
                values=[s['values']for s in control['steps']if'values'in s][-1];reward=values[0]['value'];state='big'if reward>4 else'small';state=state if c['event']==107 else'initial';coins=control['semantic']['world']['coins'];expected=f'zh|reward={reward}|second=0|coins={coins}|state={state}'
                checks['exact-hud-branch-content']=bool(texts)and all(t==expected for f in texts for t in f)
                checks['personal-and-presentation-both-reference-host-rng']=r['reward_proofs'][1]['random_result_references']==1 and r['branch_views']['presentation_rng']['random_result_references']==1 and r['semantic']['world']['rng_draw_calls']==1
                checks['presentation-random-private-state']=[s['presentation_values']for s in r['steps']if'presentation_values'in s][-1]==world.values(reward,0,state)
            else:checks['exact-hud-branch-content']=texts==c['expected_frames']
            if c.get('expected_x'):checks['exact-personal-layout']=[d['x']for frame in frames for d in frame]==c['expected_x']
            owner=c.get('owner')or next(iter(c['mod_sdk']['stores'][1]));saved=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][owner]['data_hex']));checks['only-personal-settings-published']=saved==c.get('saved',c['settings'])
            if c.get('ordinary_values')is not None:checks['ordinary-private-view-retained']=[s['values']for s in r['steps']if'values'in s][-1]==c['ordinary_values']
            if c.get('presentation_values')is not None:checks['presentation-private-view-retained']=[s['presentation_values']for s in r['steps']if'presentation_values'in s][-1]==c['presentation_values']
            projected=[s['branch_views']for s in r['steps']if'branch_views'in s];proofs=[p for s in projected for p in s['proof']['proofs']]
            if not c.get('allow_no_choice'):checks['changed-view-branch-proven']=any(p['selected_decision']!=p['ordinary_decision']and p['authority_operations']for p in proofs)
            checks['shadow-saves-never-published']=all(not p['shadow_saves_published']for p in projected)
            checks['repeat-both-view-state-and-proofs']=all(r[k]==reports[1][k]for k in ['semantic','steps','branch_views','authority_timeline','timeline_proofs'])
            checks['formal-resource-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for p in [control,*reports])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,boundary_diagnostic=c.get('boundary',False),checks=checks,reports=reports,artifacts=[x for x,_ in pairs],stock_control=control,stock_artifact=a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection();result=dict(schema='branch-views-results-1',passed=all(c['passed']for c in rows),functional_or_recovery_cases=sum(not c['boundary_diagnostic']for c in rows),boundary_diagnostics=sum(c['boundary_diagnostic']for c in rows),cases=rows,manifest_sha256=sha(MANIFEST),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,general_mod_compatibility_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
def original_gates(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(DIR/'original-gates-v1.json')['cases']:
        a,control=invoke(ROOT/'research/authority_timeline/controls-v8.json',c,True);pairs=[invoke(DIR/'original-gates-v1.json',c)for _ in range(2)];reports=[r for _,r in pairs];r=reports[0]
        checks={'bounded-completed':all(x['returncode']==0 and not x['timed_out']and not x['output_limit_exceeded']and not x['reader_failures']and p is not None and'semantic'in p for x,p in [(a,control),*pairs])}
        if checks['bounded-completed']:
            checks['world-only-host-commits']=r['semantic']['world']==control['semantic']['world']and r['semantic']['menu_snapshot']==control['semantic']['menu_snapshot']and r['branch_views']['game_world_unchanged_by_projection']
            if'values'in c:checks['original-query-timepoints']=[s['values']for s in r['steps']if'values'in s][-1]==c['values']
            if'frames'in c:
                frames=[s['draws']for s in r['steps']if'draws'in s];checks['original-hud-expectation']=[[bytes.fromhex(d['text_hex']).decode('utf-8')for d in f]for f in frames]==c['frames']and[d['x']for f in frames for d in f]==c['positions']
                saved=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1]['mods/world-view-fixture']['data_hex']));checks['original-personal-save']=saved==dict(amount=2,x=c['saved_x'],language='zh')
                checks['game-view-projection-is-in-presentation-lane']=any(p['kind']=='hud-reference'and p['selected']!=p['original']for s in r['steps']if'branch_views'in s for p in s['branch_views']['timeline']['proofs'])
            checks['repeat-evidence']=all(r[k]==reports[1][k]for k in ['semantic','steps','branch_views','authority_timeline'])
            checks['formal-resource-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']<=10000000 and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for p in [control,*reports])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,reports=reports,artifacts=[x for x,_ in pairs],stock_control=control,stock_artifact=a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection();result=dict(schema='branch-views-original-gates-1',passed=all(c['passed']for c in rows),cases=rows,binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,general_mod_compatibility_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
def init(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(DIR/'init-v1.json')['cases']:
        a,control=invoke(DIR/'init-controls-v1.json',c,True);pairs=[invoke(DIR/'init-v1.json',c)for _ in range(2)];reports=[r for _,r in pairs];r=reports[0]
        checks={'bounded-completed':all(x['returncode']==0 and not x['timed_out']and not x['output_limit_exceeded']and not x['reader_failures']and p is not None and'semantic'in p for x,p in [(a,control),*pairs])}
        if checks['bounded-completed']:
            checks['ordinary-initialization-equivalence']=r['semantic']==control['semantic'];checks['third-context-created']=r['branch_views']['enabled']and r['branch_views']['presentation']['lane']==2
            checks['repeated-initialization-and-evidence']=r['semantic']==reports[1]['semantic']and r['branch_views']==reports[1]['branch_views']
            checks['formal-resource-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']<=10000000 and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for p in [control,*reports])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,reports=reports,artifacts=[x for x,_ in pairs],stock_control=control,stock_artifact=a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection();result=dict(schema='branch-views-init-1',passed=all(c['passed']for c in rows),cases=rows,binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,full_ui_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','regressions','real-init','reward-regressions','original-gates']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':sys.exit(0 if run(a.output)else 1)
    elif a.phase=='real-init':sys.exit(0 if init(a.output)else 1)
    elif a.phase=='original-gates':sys.exit(0 if original_gates(a.output)else 1)
    elif a.phase=='reward-regressions':
        import check_reward_timeline as reward
        reward.EXE=EXE;reward.REF=REF;reward.invoke=invoke;sys.exit(0 if reward.run(a.output)else 1)
    else:
        world.EXE=EXE;world.REF=REF;world.invoke=invoke;path=ROOT/'research/sparse_value/real-init-v1.json'if a.phase=='real-init'else world.MANIFEST
        sys.exit(0 if world.run(path,a.output)else 1)
