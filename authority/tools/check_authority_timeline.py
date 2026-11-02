"""Explicit session-frame links, immutable snapshots and original model sources."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as world
import bounded_font_process
ROOT=world.ROOT;DIR=ROOT/'research/authority_timeline';MANIFEST=DIR/'suite-v8.json'
EXE=ROOT/'build-authority-timeline/Release/authority-timeline.exe';REF=EXE.with_name('authority-timeline-reference.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--authority-timeline-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'])
    raw=a.pop('stdout');err=a.pop('stderr');a.update(stderr_hex=err.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest())
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def freeze():
    DIR.mkdir(exist_ok=True);legacy=world.parent.f.load(ROOT/'research/world_view_required_mixed_v1.json')['cases'][0];c=copy.deepcopy(legacy)
    c['id']='original-mixed-callback-bound-to-authority-frame';c['authority_timeline']=dict(schema='authority-state-timeline-1',links={'personal:presentation:1:1':dict(authority='host:authority:1:1',view='replay')})
    hud=copy.deepcopy(world.parent.f.load(world.PROJECTION)['cases'][0]);hud['id']='original-authority-hud-keeps-personal-save';hud['authority_timeline']=dict(schema='authority-state-timeline-1',links={'personal:presentation:2:1':dict(authority='host:authority:1:1',view='end',project_hud=True)})
    cases=[c,hud];controls=[]
    code="""local m=RegisterMod('Authority Timeline Fixture',1)
local cfg=require('json').decode(m:LoadData())
local p=Isaac.GetPlayer(0)
TimelinePlayer=p
local add=p.AddCoins
local function give(n)add(p,n)end
local function render(prefix)Isaac.RenderText((prefix or cfg.language)..'|setting='..cfg.amount..'|coins='..p:GetNumCoins(),cfg.x,0)end
m:AddCallback(41,function()Before=p:GetNumCoins();give(cfg.amount);After=p:GetNumCoins()end)
m:AddCallback(42,function()render()end)
m:AddCallback(43,function()give(cfg.amount);give(cfg.amount)end)
m:AddCallback(44,function()cfg.x=cfg.x+1;m:SaveData(require('json').encode(cfg));UIState=(UIState or 0)+1;p:GetData().counter=UIState;render()end)
m:AddCallback(45,function()for i=1,2 do give(cfg.amount)end end)
m:AddCallback(46,function()if cfg.extra then Extra=p:GetNumCoins()end;give(cfg.amount)end)
m:AddCallback(47,function()give(cfg.amount+1)end)
m:AddCallback(49,function()if cfg.amount==1 then Isaac.RenderText('one',cfg.x,0)else Isaac.RenderText('other',cfg.x,0)end end)
m:AddCallback(50,function()cfg.x=cfg.x+5;m:SaveData(require('json').encode(cfg));UIState=99;p:GetData().counter=99;render();error('timeline-injected')end)
m:AddCallback(51,function()local r=math.random(1,99);give(r)end)
m:AddCallback(52,function()add(p,1)end)
m:AddCallback(53,function()if cfg.language=='zh' then render('中文')else render('English')end end)
m:AddCallback(54,function()Isaac.RenderText('x='..cfg.x,cfg.x,0)end)
m:AddCallback(55,function()if cfg.extra then give(cfg.amount)else give(cfg.amount)end end)
m:AddCallback(56,function()local v=Vector(cfg.x,20);v.X=7;p.Position=v end)
m:AddCallback(57,function()Isaac.RenderText('reward='..cfg.cosmetic,cfg.x,0)end)
local hidden=1
m:AddCallback(58,function()add(p,hidden)end)
m:AddCallback(59,function()give(cfg.amount+hidden)end)
m:AddCallback(60,function()Isaac.RenderText('p0='..p:GetNumCoins()..'|p1='..Isaac.GetPlayer(1):GetNumCoins(),0,0)end)
m:AddCallback(61,function()Isaac.RenderText('frame='..Game():GetFrameCount()..'|players='..Game():GetNumPlayers(),0,0)end)
m:AddCallback(62,function()give(cfg.amount);if cfg.extra then Isaac.RenderText('only|'..cfg.amount,cfg.x,0)end end)
"""
    source=DIR/'main-v4.lua';world.parent.f.parent.frozen(source,code.encode());owner='mods/authority-timeline-fixture'
    base=copy.deepcopy(hud)
    for k in ['frames','positions','coins','epoch','intents','saved_x','authority_timeline','steps','id','kind']:base.pop(k,None)
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=sha(source),modules=dict(entry=0,roots=[dict(root=DIR.relative_to(ROOT).as_posix(),display=owner,sha256={'main.lua':sha(source)},source_paths={'main.lua':source.relative_to(ROOT).as_posix()})]))
    settings=[dict(amount=1,x=17,language='en',extra=False,cosmetic=1),dict(amount=2,x=137,language='zh',extra=True,cosmetic=2)]
    base['mod_sdk']['stores']=[{owner:json.dumps(v,separators=(',',':'))}for v in settings]
    def host(event=41,frame=1,**kw):return dict(world.dispatch(frame,event,'host',**kw),phase='authority')
    def personal(event=42,frame=1,**kw):return dict(world.dispatch(frame,event,**kw),phase='presentation')
    def case(id,steps,links,frames=None,**kw):
        x=copy.deepcopy(base);x.update(id=id,steps=steps,authority_timeline=dict(schema='authority-state-timeline-1',links=links),custom=True,owner=owner,settings=copy.deepcopy(settings[1]),**kw)
        if frames is not None:x['expected_frames']=frames
        cases.append(x);return x
    def link(personal_event=42,authority_event=41,view='end',authority_frame=1):return {f'personal:presentation:{personal_event}:1':dict(authority=f'host:authority:{authority_event}:{authority_frame}',view=view,project_hud=True)}
    case('cached-helper-replay-query-before-and-after',[host(),personal(41),world.ev('return Before,After')],link(41,41,'replay'),values=world.values(0,1),expected_world_refs=1)
    case('hud-can-add-query-at-explicit-frame-end',[host(),personal()],link(),[['zh|setting=1|coins=1']])
    swapped=case('authority-values-swapped-not-fixed-result',[host(),personal()],link(),[['zh|setting=2|coins=2']]);swapped['mod_sdk']['stores'][0][owner]=json.dumps(dict(settings[0],amount=2),separators=(',',':'));swapped['mod_sdk']['stores'][1][owner]=json.dumps(dict(settings[1],amount=1),separators=(',',':'));swapped['settings']['amount']=1
    case('game-expression-contributes-leaf-values',[host(47),personal()],link(42,47),[['zh|setting=1|coins=2']])
    case('personal-language-branch-stays-personal',[host(),personal(53)],link(53),[['中文|setting=1|coins=1']])
    case('personal-save-stays-independent-from-hud',[host(),personal(44)],link(44),[['zh|setting=1|coins=1']],saved_x=138)
    case('duplicate-personal-frame-references-without-reexecution',[host(),personal(),personal()],link(),[['zh|setting=1|coins=1']]*2,one_sink=True)
    case('rebuild-restores-frame-links-and-proofs',[host(),personal(),dict(op='rebuild'),personal()],link(),[['zh|setting=1|coins=1']]*2)
    rollback=world.ev('return UIState,TimelinePlayer:GetData().counter')
    case('saved-and-drawn-failure-rolls-back',[host(),personal(50,expect_error='timeline-injected'),personal(),rollback],dict(link(50),**link()),[['zh|setting=1|coins=1']],check_private_rollback=True,values=world.values(None,None))
    case('multiple-contributions-are-not-matched-by-value',[host(43),personal(44,expect_error='HUD authority contribution not unique'),personal(54),rollback],dict(link(44,43),**link(54,43)),[['x=137']],check_private_rollback=True,boundary_rejection=True,values=world.values(None,None))
    case('shared-helper-from-different-branch-is-rejected',[host(55),personal(55,expect_error='Timeline query state anchor not unique')],link(55,55,'replay'),boundary_rejection=True)
    case('new-query-without-replay-anchor-is-rejected',[host(46),personal(46,expect_error='Timeline query state anchor not unique')],link(46,46,'replay'),boundary_rejection=True)
    case('reward-controlled-hud-needs-branch-resolution',[host(),personal(49,expect_error='HUD control flow requires dual-view branch resolution')],link(49),boundary_rejection=True,required_compatibility=False)
    case('cycles-require-an-iteration-proof',[host(45,expect_error='Timeline cyclic control flow requires iteration proof')],{},boundary_rejection=True,expected_frames_count=0)
    case('random-is-not-executed-without-a-contract',[host(51,expect_error='Unregistered timeline random or time source')],{},boundary_rejection=True,expected_frames_count=0)
    case('mutated-vector-origin-is-not-assumed',[host(56,expect_error='Timeline vector mutation contract unavailable')],{},boundary_rejection=True,expected_frames_count=0)
    case('missing-frame-link-is-not-latest-state',[host(),personal(expect_error='Explicit authority frame link required')],{},boundary_rejection=True)
    case('missing-authority-frame-is-not-latest-state',[host(),personal(expect_error='Authority frame unavailable or expired')],link(authority_frame=99),boundary_rejection=True)
    case('hud-text-is-not-used-to-guess-rewards',[host(52),personal(57)],link(57,52),[['reward=2']])
    case('expired-authority-frame-is-not-current-state',[host(frame=i)for i in range(1,130)]+[personal(expect_error='Authority frame unavailable or expired')],link(),boundary_rejection=True,retained_frames=128)
    case('same-number-captured-upvalue-is-not-a-literal-proof',[host(58,expect_error='Timeline native argument literal provenance unavailable')],{},boundary_rejection=True,expected_frames_count=0)
    case('tainted-expression-does-not-certify-unknown-operands',[host(59,expect_error='Timeline game operand literal provenance unavailable')],{},boundary_rejection=True,expected_frames_count=0)
    case('other-player-coins-are-not-player-zero',[host(),personal(60)],link(60),[['p0=1|p1=0']])
    case('scene-query-uses-bound-frame-not-current-scene',[host(),dict(op='set_scene',role='host',scene=dict(revision=2,frame_count=99,num_players=2,is_paused=False)),personal(61)],link(61),[['frame=42|players=2']])
    snapshot=copy.deepcopy(world.parent.f.load(world.frozen.MENU)['snapshot']);snapshot['revision']=2;snapshot['players'][1]['coins']=7
    scene_action=dict(op='set_menu_snapshot',role='host',snapshot=snapshot)
    case('other-player-query-uses-explicit-seven',[scene_action,host(),personal(60)],link(60),[['p0=1|p1=7']])
    case('actor-query-uses-bound-snapshot-not-current-values',[host(),scene_action,personal(60)],link(60),[['p0=1|p1=0']])
    case('duplicate-save-and-private-state-only-commit-once',[host(),personal(44),personal(44),rollback],link(44),[['zh|setting=1|coins=1']]*2,saved_x=138,one_sink=True,values=world.values(1,1))
    case('replay-personal-only-hud-still-uses-authority-value',[host(62),personal(62)],link(62,62,'replay'),[['only|1']])
    for case in cases:
        if case.get('custom'):
            control=copy.deepcopy(case);control.pop('authority_timeline');control['steps']=[s for s in case['steps']if s.get('role')=='host'and(s.get('phase')=='authority'or s['op']in ['set_scene','set_menu_snapshot'])and'expect_error'not in s]
            if'values'in case:control['steps'].append(dict(case['steps'][-1],role='host'))
            controls.append(control);continue
        control=copy.deepcopy(case);control.pop('authority_timeline');control['steps']=[case['steps'][0]]
        if'values'in case:control['steps'].append(dict(case['steps'][-1],role='host'))
        controls.append(control)
    world.parent.f.freeze_json(MANIFEST,dict(schema='authority-timeline-model-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    world.parent.f.freeze_json(DIR/'controls-v8.json',dict(schema='authority-timeline-stock-host-controls-1',work_limit=10000000,timeout_seconds=5,cases=controls));print(json.dumps(dict(frozen=True,cases=len(cases))))
def run(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(MANIFEST)['cases']:
        a,reference=invoke(DIR/'controls-v8.json',c,True);pairs=[invoke(MANIFEST,c)for _ in range(2)];reports=[r for _,r in pairs];r=reports[0];checks={}
        checks['completed']=reference is not None and a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and all(p and'semantic'in p and x['returncode']==0 and not x['timed_out']and not x['output_limit_exceeded']and not x['reader_failures']for x,p in pairs)
        if checks['completed']:
            if'values'in c:checks['actual-query-timepoints']=[s['values']for s in r['steps']if'values'in s][-1]==c['values']
            checks['host-world-once']=r['semantic']['world']==reference['semantic']['world']and r['semantic']['menu_snapshot']==reference['semantic']['menu_snapshot']
            if c.get('custom'):
                expected=dict(c['settings']);expected['x']=c.get('saved_x',expected['x']);saved=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][c['owner']]['data_hex']));checks['personal-settings-preserved']=saved==expected
                if'expected_frames'in c:checks['actual-hud-game-view']=[[bytes.fromhex(d['text_hex']).decode()for d in s['draws']]for s in r['steps']if'draws'in s]==c['expected_frames']
                if c.get('one_sink'):checks['duplicate-not-executed']=sum(s['api']=='hud.text'for s in r['sparse_provenance'][1]['sinks'])==1
                if c.get('check_private_rollback'):checks['rejected-state-and-save-restored']=saved['x']==137 and all(n.get('actual',{}).get('hex')!='74696d656c696e652d696e6a6563746564'for n in r['sparse_provenance'][1]['nodes'])
            elif'saved_x'in c:
                saved=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1]['mods/world-view-fixture']['data_hex']));checks['personal-settings-preserved']=saved==dict(amount=2,language='zh',x=c['saved_x'])
                frames=[s['draws']for s in r['steps']if'draws'in s];checks['actual-hud-game-view']=[[bytes.fromhex(d['text_hex']).decode()for d in frame]for frame in frames]==c['frames']
                checks['personal-layout-kept']=[s[0]['x']for s in frames]==c['positions']
                checks['hud-references-proven']=any(p['kind']=='hud-reference'and p['selected']!=p['original']and not p['personal_storage_written']for p in r['timeline_proofs'][1]['proofs'])
            else:checks['personal-settings-preserved']=r['semantic']['mod_stores']==reference['semantic']['mod_stores']
            checks['repeat-proofs']=r['semantic']==reports[1]['semantic']and r['authority_timeline']==reports[1]['authority_timeline']and r['timeline_proofs']==reports[1]['timeline_proofs']
            if'expected_world_refs'in c or('values'in c and not c.get('custom')):checks['unique-native-void-references']=len(r['timeline_proofs'][1]['proofs'])==c.get('expected_world_refs',4) and all(not p['native_executed']for p in r['timeline_proofs'][1]['proofs'])
            if not c.get('custom'):checks['five-state-snapshots']=len(r['authority_timeline']['frames'])==1 and len(r['authority_timeline']['frames'][0]['states'])==5
            if'expected_frames_count'in c:checks['rejected-frame-not-published']=len(r['authority_timeline']['frames'])==c['expected_frames_count']
            if'retained_frames'in c:checks['authority-cache-bounded']=len(r['authority_timeline']['frame_index'])==c['retained_frames']
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']<=10000000 and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for p in [reference,*reports])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,boundary_rejection=c.get('boundary_rejection',False),checks=checks,reports=reports,artifacts=[x for x,_ in pairs],stock_control=reference,stock_artifact=a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection()
    result=dict(schema='authority-timeline-results-1',passed=all(c['passed']for c in rows),functional_cases=sum(not c['boundary_rejection']for c in rows),boundary_diagnostic_cases=sum(c['boundary_rejection']for c in rows),original_linked_model_gates_passed=all(c['passed']for c in rows[:2]),general_mod_compatibility_gate_passed=False,cases=rows,manifest_sha256=sha(MANIFEST),driver_sha256=sha(Path(__file__)),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','regressions','real-init']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':sys.exit(0 if run(a.output)else 1)
    else:
        world.EXE=EXE;world.REF=REF;world.invoke=invoke
        path=ROOT/'research/sparse_value/real-init-v1.json'if a.phase=='real-init'else world.MANIFEST
        sys.exit(0 if world.run(path,a.output)else 1)
