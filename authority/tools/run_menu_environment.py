"""Short CLI tests for personal input, authority snapshots and captured audio."""
import argparse,copy,gzip,hashlib,json,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as f
import bounded_font_process
import freeze_menu_environment as freezer
import freeze_pristine_mcm
ROOT=f.ROOT;EXE=ROOT/'build-menu-environment/Release/authority-menu-environment.exe';REF=EXE.with_name('authority-menu-environment-reference.exe')
MANIFEST=ROOT/'research/menu_environment_v3.json';REAL=ROOT/'research/menu_environment_real_v3.json'
ev=f.ev;values=f.parent.values
def device(button=None,controller=0,action=None):
    d=copy.deepcopy(f.load(freezer.PROFILE)['initial_inputs'][1]['device'])
    if button is not None:d['buttons'].setdefault(str(controller),{})[str(button)]=dict(pressed=True,triggered=True,value=1)
    if action is not None:d['actions']={str(controller):{str(action):dict(pressed=True,triggered=True,value=.5)}}
    return dict(device=d)
def dispatch(frame=1,event=2,role='personal',input=None,**kw):
    return dict(op='dispatch',frame_id=frame,event=event,phase='authority'if event==1 else'presentation',role=role,input=input or{},**kw)
def freeze():
    source=ROOT/'research/menu_environment/main.lua'
    code='''MenuMod=RegisterMod('Menu Environment Fixture',1)
local cfg=require('json').decode(MenuMod:LoadData())
local counter=0
P=Isaac.GetPlayer(0);Q=Isaac.GetPlayer(1);R=Game():GetRoom();SFX=SFXManager()
MenuMod:AddCallback(1,function()P:AddCoins(cfg.amount)end)
MenuMod:AddCallback(2,function()
 if Input.IsButtonTriggered(76,0)then cfg.x=cfg.x+10;counter=counter+1;MenuMod:SaveData(require('json').encode(cfg));SFX:Play(171,.5,0,false,1,0)end
 local data=P:GetData();if Input.IsButtonTriggered(70,0)then data.changed=999;cfg.x=999;MenuMod:SaveData('rejected');SFX:Play(171);Isaac.RenderText('rejected',0,0);error('menu-injected')end
 Isaac.RenderText(cfg.language..'|coins='..P:GetNumCoins()..'|private='..counter..'|data='..tostring(data.changed),cfg.x,0)
end)
MenuMod:AddCallback(3,function()Isaac.RenderText(tostring(P:GetPlayerType()),0,0)end)
MenuMod:AddCallback(4,function()Isaac.RenderText(tostring(Input.IsButtonTriggered(76,0)),0,0)end)
MenuMod:AddCallback(5,function()SFX:Play(171);SFX:Play(171,1,0,false,1)end)
MenuMod:AddCallback(6,function()for i=1,129 do SFX:Play(171)end end)
MenuMod:AddCallback(7,function()Isaac.RenderText(tostring(Input.GetMousePosition(true).X),0,0)end)
'''
    f.parent.frozen(source,code.encode());base=copy.deepcopy(f.load(f.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k in ['objects','mod_sdk','value_objects','engine_services','animation_profile','graphics_profile','font_profile','font_capture_profile','ui_flow_profile','stores']}
    root=dict(root='research/menu_environment',display='mods/menu-environment-fixture',sha256={'main.lua':f.digest(source)})
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=f.digest(source),modules=dict(entry=0,roots=[root]),menu_profile=dict(path=freezer.PROFILE.relative_to(ROOT).as_posix(),sha256=f.digest(freezer.PROFILE)))
    base['mod_sdk']['stores']=[{root['display']:json.dumps(dict(amount=1,language='en',x=17),separators=(',',':'))},{root['display']:json.dumps(dict(amount=2,language='zh',x=137),separators=(',',':'))}]
    cases=[]
    def case(id,steps,returns=None,**kw):
        c=copy.deepcopy(base);c.update(id=id,steps=steps,kind=kw.pop('kind','functional'),**kw)
        if returns is not None:c['values']=values(*returns)
        cases.append(c);return c
    def snapshot(rev,**edits):
        snap=copy.deepcopy(f.load(freezer.PROFILE)['snapshot']);snap['revision']=rev
        for path,value in edits.items():
            parts=path.split('/');target=snap
            for part in parts[:-1]:target=target[int(part)]if isinstance(target,list)else target[part]
            target[parts[-1]]=value
        return dict(op='set_menu_snapshot',role='host',snapshot=snap)
    case('two-player-identities-and-relations',[ev('return P==Isaac.GetPlayer(0),Q==Isaac.GetPlayer(1),P.ControllerIndex,Q.ControllerIndex,P:GetPlayerType(),Q:GetPlayerType(),P.Parent,Q:GetOtherTwin()')],[True,True,0,1,0,1,None,None])
    case('explicit-room-transform',[ev('local v=R:WorldToScreenPosition(Vector(3,4));local t=Game().ScreenShakeOffset;return v.X,v.Y,R:GetRenderScrollOffset().X,R:IsClear(),t.X')],[115.0,2.0,0.0,True,0.0])
    case('nonempty-pickup-scene',[ev('local rows=Isaac.FindInRadius(P.Position,30,EntityPartition.PICKUP);local p=rows[1];return #rows,p.Type,p.Variant,p.SubType,p:ToPickup()==p,p:ToPlayer(),GetPtrHash(p),p:IsShopItem(),#Isaac.GetRoomEntities(),Isaac.CountEnemies(),Isaac.CountBosses()')],[1,5,100,1,True,None,2001,False,3,0,0])
    case('filtered-entity-search',[ev('return #Isaac.FindByType(5,100,-1,true,false),#Isaac.FindByType(5,101,-1,true,false),#Isaac.FindByType(1,-1,-1,false,false)')],[1,0,2])
    case('independent-input-controllers',[dict(op='set_input',input=device(76,1,action=5)),ev('return Input.IsButtonTriggered(76,0),Input.IsButtonTriggered(76,1),Input.IsButtonPressed(76,1),Input.GetActionValue(5,1),Input.IsActionTriggered(5,1)')],[False,True,True,.5,True])
    case('input-cache-methods',[dict(op='set_input',input=device(76)),ev('local t,p,v=Input.IsButtonTriggered,Input.IsButtonPressed,Input.GetButtonValue;return t(76,0),p(76,0),v(76,0)')],[True,True,1.0])
    case('mouse-explicit-spaces',[ev('local a,b=Input.GetMousePosition(true),Input.GetMousePosition(false);return a.X,a.Y,b.X,b.Y')],[100.0,120.0,212.0,118.0])
    case('scene-field-precise-invalidation',[dict(op='capture_reads',event=3,phase='presentation'),snapshot(2,**{'players/1/player_type':2}),dict(op='consumer_status',consumer=3)],valid=[True])
    case('scene-field-aba',[dict(op='capture_reads',event=3,phase='presentation'),snapshot(2,**{'players/0/player_type':2}),snapshot(3),dict(op='consumer_status',consumer=3)],valid=[False])
    case('input-read-aba',[dict(op='capture_reads',event=4,phase='presentation'),dict(op='set_input',input=device(76)),dict(op='set_input',input=device()),dict(op='consumer_status',consumer=4)],valid=[False])
    case('input-unrelated-key',[dict(op='capture_reads',event=4,phase='presentation'),dict(op='set_input',input=device(77)),dict(op='consumer_status',consumer=4)],valid=[True])
    moved=device();moved['device']['mouse_world']=[101,120]
    case('mouse-read-aba',[dict(op='capture_reads',event=7,phase='presentation'),dict(op='set_input',input=moved),dict(op='set_input',input=device()),dict(op='consumer_status',consumer=7)],valid=[False])
    case('personal-movement-and-audio',[dispatch(input=device(76)),dispatch(2,role='host')],frames=[['zh|coins=0|private=1|data=nil'],['en|coins=0|private=0|data=nil']],positions=[147,17],audio=[1,0])
    case('authority-reward-once',[dispatch(event=1,role='host'),dispatch(event=1,role='host'),dispatch(input=device(76))],coins=1,frames=[['zh|coins=1|private=1|data=nil']],audio=[1])
    case('duplicate-personal-frame',[dispatch(input=device(76)),dispatch(input=device(76)),dispatch(2)],frames=[['zh|coins=0|private=1|data=nil']]*3,audio=[1,1,0],audio_calls=1)
    case('rejected-frame-full-recovery',[dispatch(input=device(76)),dispatch(2,input=device(70),expect_error='menu-injected'),dispatch(2)],frames=[['zh|coins=0|private=1|data=nil']]*2,audio=[1,0],restored=True)
    case('audio-optional-arity-kept',[dispatch(event=5)],audio=[2],audio_arity=[1,5])
    case('rebuild-cached-audio-stable-id',[dispatch(input=device(76)),dict(op='rebuild'),dispatch(input=device(76)),dispatch(2)],frames=[['zh|coins=0|private=1|data=nil']]*3,audio=[1,1,0],audio_ids_equal=True)
    case('private-config-reload',[dispatch(input=device(76)),dict(op='reload_saved'),dispatch()],frames=[['zh|coins=0|private=1|data=nil'],['zh|coins=0|private=0|data=nil']],positions=[147,147])
    c=case('stale-actor-and-root-retirement',[ev('Old=Isaac.FindByType(5)[1];Old:GetData().x=1'),snapshot(2),dict(op='menu_state')])
    c['steps'][1]['snapshot']['entities'][0]['id']=4;c['steps'].append(ev('Old:Exists()',expect_error='Stale menu object identity'));c['retired_data']=True
    for name,code,error in [('unknown-player-method','P:GetLuck()','Unregistered player API'),('unknown-world-write','Q.Position=Vector(1,2)','Authoritative menu objects are read-only'),('snapshot-alias-write','P.Position.X=0','Snapshot value alias writes unverified'),('foreign-query-method','P.GetPlayerType(R)','Menu query receiver class differs'),('unknown-input-index','Input.IsButtonPressed(76,9)','Input identity outside registered contract'),('input-colon-call','Input:IsButtonPressed(76,0)','Input query requires code and controller index'),('unregistered-audio','SFX:Play(99999)','Unregistered sound identity'),('unknown-audio-state','SFX:IsPlaying(171)','Unregistered audio API'),('personal-world-write','P:AddCoins(1)','World write requires authority phase')]:
        steps=[ev(code,expect_error=error),dispatch()]
        if name=='unregistered-audio':steps=[ev('MenuMod:AddCallback(9,function()SFX:Play(99999)end)'),dispatch(event=9,expect_error=error),dispatch()]
        case('reject-'+name,steps,kind='expected-rejection',frames=[['zh|coins=0|private=0|data=nil']])
    case('reject-audio-capacity-and-recover',[dispatch(event=6,expect_error='Audio frame capacity exceeded'),dispatch()],kind='expected-rejection',audio=[0])
    case('reject-frame-payload-conflict',[dispatch(input=device(76)),dispatch(expect_error='Menu frame identity reused with different payload'),dispatch(2)],kind='expected-rejection',audio=[1,0])
    case('reject-missing-frame-id',[dict(op='dispatch',event=2,phase='presentation',expect_error='Explicit positive menu frame identity required'),dispatch()],kind='expected-rejection')
    case('explicit-unbound-button-snapshot',[ev('return Input.IsButtonPressed(-1,0),Input.IsButtonTriggered(-1,1)')],[False,False])
    incomplete=device();incomplete['device']['buttons']={}
    case('reject-unbound-without-snapshot',[dict(op='set_input',input=incomplete),ev('Input.IsButtonPressed(-1,0)',expect_error='Input identity outside registered contract'),dispatch()],kind='expected-rejection')
    case('inventory-modifier-flag-has-separate-view',[snapshot(2,**{'players/0/collectibles':{'1':3},'players/0/collectibles_base':{'1':2}}),ev('return P:GetCollectibleNum(1),P:GetCollectibleNum(1,true),P:HasCollectible(1,true)')],[3,2,True])
    case('explicit-seed-and-heart-snapshot',[ev('return Game():GetSeeds():IsCustomRun(),Game():GetSeeds():GetStartSeed(),Game():GetVictoryLap(),Game().Challenge,P:GetEffectiveMaxHearts(),P:GetSoulHearts(),P:GetBrokenHearts()')],[False,460,0,0,6,0,0])
    case('reject-seed-write-during-personal-callback',[ev('MenuMod:AddCallback(10,function()Game():GetSeeds():AddSeedEffect(1)end)'),dispatch(event=10,expect_error='Unregistered seeds API: AddSeedEffect'),dispatch()],kind='expected-rejection')
    f.freeze_json(MANIFEST,dict(schema='menu-environment-tests-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    freeze_pristine_mcm.freeze()
    real=copy.deepcopy(f.load(f.REAL));real['schema']='menu-environment-real-2'
    for c in real['cases']:
        c['menu_profile']=copy.deepcopy(base['menu_profile'])
        for root in c['modules']['roots']:
            if root['display']=='mods/mod_config_menu_cn_2494192799':
                root['source_paths']={'scripts/modconfig.lua':freeze_pristine_mcm.TARGET.relative_to(ROOT).as_posix()}
                root['sha256']['scripts/modconfig.lua']=f.digest(freeze_pristine_mcm.TARGET)
        for s in c['steps']:s['frame_id']=1
    c=copy.deepcopy(real['cases'][0]);c['id']='mcm-open-via-personal-input';c['steps']=[dispatch(input=device(76)),ev('return ModConfigMenu.IsVisible')];real['cases'].append(c)
    c=copy.deepcopy(real['cases'][2]);c['id']='combined-open-via-personal-input';c['steps']=[dispatch(input=device(76)),ev('return ModConfigMenu.IsVisible')];real['cases'].append(c)
    f.freeze_json(REAL,real);print(json.dumps(dict(cases=len(cases),real_cases=len(real['cases']))))
def invoke(manifest,c,reference):
    a=bounded_font_process.run([str(REF if reference else EXE),'--menu-environment-suite',str(ROOT),str(manifest),c['id'],'reference'if reference else'boundary'])
    raw=a.pop('stdout');stderr=a.pop('stderr');a.update(stderr_hex=stderr.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest(),stdout_bytes=len(raw))
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def run(path,out,real=False):
    before=f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in f.load(path)['cases']:
        artifacts=[];reports=[];checks=[]
        def check(k,v):checks.append(dict(check=k,passed=bool(v)))
        for ref in [True,False,False]:
            a,r=invoke(path,c,ref);artifacts.append(a);reports.append(r)
        p=reports[1];check('bounded-results',all(r is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']for a,r in zip(artifacts,reports)))
        check('function-completed',all(a['returncode']==0 and r is not None and'semantic'in r for a,r in zip(artifacts,reports)))
        if p and'semantic'in p:
            check('formal-limits',all(r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())and r['private_commit_bytes']<1024**3 and not r['game_started']and not r['full_trace_enabled']for r in reports))
            ordinary=lambda r:[{k:v for k,v in s.items()if k!='metadata'}for s in r['steps']]
            check('stock-ordinary-equivalence',reports[0]['semantic']==p['semantic']and ordinary(reports[0])==ordinary(p));check('repeat-state-and-evidence',reports[2]['semantic']==p['semantic']and reports[2]['steps']==p['steps'])
            frames=[s for s in p['steps']if'draws'in s];returns=[s['values']for s in p['steps']if'values'in s]
            if'values'in c:check('exact-returns',returns[-1]==c['values'])
            if real and 'open-via-personal-input'in c['id']:check('menu-actually-open',returns and returns[-1]==values(True)and any(s['draws']for s in frames))
            if'frames'in c:check('exact-frame-text',[[bytes.fromhex(d['text_hex']).decode()for d in s['draws']]for s in frames]==c['frames'])
            if'positions'in c:check('personal-position',[s['draws'][0]['x']for s in frames]==c['positions'])
            if'audio'in c:check('captured-audio-count',[len(s['audio'])for s in frames]==c['audio'])
            if'audio_arity'in c:check('audio-raw-arity',[len(a['args'])for a in frames[0]['audio']]==c['audio_arity'])
            if'audio_calls'in c:check('duplicate-does-not-execute',p['metadata'][1]['menu_environment']['audio_calls']==c['audio_calls'])
            if'coins'in c:check('authority-world-once',p['semantic']['world']['coins']==c['coins']and len(p['semantic']['world']['effects'])==1)
            if c.get('audio_ids_equal'):check('stable-rebuilt-audio-id',frames[0]['audio'][0]['event_id']==frames[1]['audio'][0]['event_id'])
            if c.get('restored'):check('full-recovery',json.loads(bytes.fromhex(p['semantic']['mod_stores'][1]['mods/menu-environment-fixture']['data_hex']))==dict(amount=2,language='zh',x=147))
            if c.get('retired_data'):check('old-private-data-unrooted',p['steps'][2]['metadata']['private_entity_tables']==0)
            if'valid'in c:check('precise-read-versions',[s['metadata']['versions_valid']for s in p['steps']if'metadata'in s and'versions_valid'in s['metadata']]==c['valid'])
            check('native-claims-remain-false',all(not m['menu_environment']['native_environment_equivalence_verified']and m['menu_environment']['native_audio_calls']==0 for m in p['metadata']))
        passed=all(x['passed']for x in checks);rows.append(dict(id=c['id'],kind=c.get('kind'),passed=passed,checks=checks,artifacts=artifacts,reports=reports))
        print(json.dumps(dict(id=c['id'],passed=passed,first_failure=(p or{}).get('first_unsupported_entry'),failed=[x['check']for x in checks if not x['passed']])),flush=True)
    assert before==f.parent.protection.protection()
    result=dict(schema='menu-environment-results-1',passed=all(r['passed']for r in rows),cases=rows,manifest_sha256=f.digest(path),driver_sha256=f.digest(Path(__file__)),binaries={p.relative_to(ROOT).as_posix():f.digest(p)for p in [EXE,REF]},work_limit=10000000,timeout_seconds=5,protected_files_unchanged=True,real_callbacks=real,native_rendering_verified=False,authority_projection_passed=False,playable=False)
    raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((out/'result.json.gz').read_bytes())==raw
    print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows))));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL if a.phase=='real'else MANIFEST,a.output,a.phase=='real')else 1)
