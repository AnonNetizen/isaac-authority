"""Bounded authority-write and personal-intent tests; no native game calls."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_menu_environment as parent
import freeze_world_view as frozen
import bounded_font_process
ROOT=parent.ROOT;DIR=frozen.DIR;MANIFEST=ROOT/'research/world_view_v6.json';REAL=ROOT/'research/world_view_real_v6.json';PROJECTION=ROOT/'research/world_view_required_projection_v3.json'
EXE=ROOT/'build-world-view/Release/authority-world-view.exe';REF=EXE.with_name('authority-world-view-reference.exe')
ev=parent.ev;values=parent.values;dispatch=parent.dispatch;device=parent.device
def freeze():
    source=DIR/'main-v2.lua';code='''ViewMod=RegisterMod('World View Fixture',1)
local cfg=require('json').decode(ViewMod:LoadData())
local private=0
P=Isaac.GetPlayer(0);Q=Isaac.GetPlayer(1);Seeds=Game():GetSeeds();Config=Isaac.GetItemConfig()
local function sample()return tostring(Seeds:HasSeedEffect(10))..':'..P.Position.X end
Trace=''
ViewMod:AddCallback(1,function()
 Trace=sample();P:AddCoins(cfg.amount);P.Position=Vector(cfg.x,20);P.ControlsEnabled=false;Seeds:AddSeedEffect(10);Trace=Trace..'>'..sample()
end)
ViewMod:AddCallback(2,function()
 if Input.IsButtonTriggered(76,0)then cfg.x=cfg.x+10;ViewMod:SaveData(require('json').encode(cfg));SFXManager():Play(171)end
 private=private+1;P:GetData().counter=private
 P.Position=Vector(cfg.x,20);P.Velocity=Vector(0,0);P.ControlsEnabled=false;Seeds:AddSeedEffect(10)
 Isaac.RenderText(cfg.language..'|setting='..cfg.amount..'|coins='..P:GetNumCoins()..'|worldx='..P.Position.X..'|hud='..tostring(Seeds:HasSeedEffect(10))..'|private='..private,cfg.x,0)
 if Input.IsButtonTriggered(70,0)then cfg.x=999;ViewMod:SaveData('rejected');P:GetData().counter=999;error('view-injected')end
end)
ViewMod:AddCallback(3,function()Seeds:RemoveSeedEffect(10);P.Position=Vector(64,20);P.ControlsEnabled=true end)
ViewMod:AddCallback(4,function()Isaac.RenderText(tostring(Config:GetCollectible(78):IsAvailable()),0,0)end)
ViewMod:AddCallback(5,function()Isaac.RenderText(Config:GetCollectible(78).Name,0,0)end)
ViewMod:AddCallback(6,function()VoidReturns=select('#',Seeds:AddSeedEffect(10))end)
ViewMod:AddCallback(7,function()RandomValue=math.random(1,99);P.Position=Vector(RandomValue,20);Seeds:AddSeedEffect(10);ViewMod:SaveData('uncommitted');P:GetData().counter=999;error('authority-injected')end)
ViewMod:AddCallback(8,function()for i=1,513 do P.ControlsEnabled=false end end)
ViewMod:AddCallback(9,function()Seeds:AddSeedEffect(1)end)
ViewMod:AddCallback(10,function()Isaac.RenderText(tostring(P.ControlsEnabled),0,0)end)
ViewMod:AddCallback(11,function()Isaac.RenderText(tostring(Seeds:HasSeedEffect(10)),0,0)end)
ViewMod:AddCallback(12,function()P.Position=Vector(64,20)end)
''';parent.f.parent.frozen(source,code.encode());base=copy.deepcopy(parent.f.load(parent.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k not in ['id','steps','kind','values']}
    root=dict(root=DIR.relative_to(ROOT).as_posix(),display='mods/world-view-fixture',sha256={'main.lua':parent.f.digest(source)},source_paths={'main.lua':source.relative_to(ROOT).as_posix()})
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=parent.f.digest(source),modules=dict(entry=0,roots=[root]),menu_profile=dict(path=frozen.MENU.relative_to(ROOT).as_posix(),sha256=parent.f.digest(frozen.MENU)),world_view_profile=dict(path=frozen.PROFILE.relative_to(ROOT).as_posix(),sha256=parent.f.digest(frozen.PROFILE)))
    base['mod_sdk']['stores']=[{root['display']:json.dumps(dict(amount=1,language='en',x=17),separators=(',',':'))},{root['display']:json.dumps(dict(amount=2,language='zh',x=137),separators=(',',':'))}]
    cases=[]
    def case(id,steps,returns=None,**kw):
        c=copy.deepcopy(base);c.update(id=id,steps=steps,kind=kw.pop('kind','functional'),**kw)
        if returns is not None:c['values']=values(*returns)
        cases.append(c);return c
    def scene(revision,**edits):
        s=copy.deepcopy(parent.f.load(frozen.MENU)['snapshot']);s['revision']=revision
        for path,v in edits.items():
            parts=path.split('/');obj=s
            for part in parts[:-1]:obj=obj[int(part)]if isinstance(obj,list)else obj[part]
            obj[parts[-1]]=v
        return dict(op='set_menu_snapshot',role='host',snapshot=s)
    def authority(frame=1,event=1,**kw):return dict(dispatch(frame,event,'host',**kw),phase='authority')
    def state():return dict(op='world_view_state')
    case('xml-metadata-identities',[ev('local a,b,c=Config:GetCollectible(1),Config:GetCollectible(73),Config:GetCollectible(78);return a.ID,a.Quality,a.Type,b.AchievementID,c.AchievementID,c.Name,c.Hidden,c.MaxCharges')],[1,3,1,6,7,'#BOOK_OF_REVELATIONS_NAME',False,6])
    case('explicit-dynamic-availability',[ev('return Config:GetCollectible(1):IsAvailable(),Config:GetCollectible(73):IsAvailable(),Config:GetCollectible(78):IsAvailable()')],[True,False,True])
    case('cached-availability-method',[ev('local a=Config:GetCollectible(78);local f=a.IsAvailable;return f(a),Config:GetCollectible(78)==a')],[True,True])
    case('authority-query-timepoints',[authority(),ev('return Trace,P.Position.X,P.ControlsEnabled,Seeds:HasSeedEffect(10)',role='host')],['false:160.0>true:17.0',17.0,False,True],epoch=3,coins=1)
    case('personal-intents-authority-reads',[dispatch()],frames=[['zh|setting=2|coins=0|worldx=160.0|hud=false|private=1']],epoch=0,intents=[4],worldx=160)
    case('authority-reward-personal-config',[authority(),dispatch(input=device(76))],frames=[['zh|setting=2|coins=1|worldx=17.0|hud=true|private=1']],positions=[147],epoch=3,coins=1,intents=[4],saved_x=147)
    case('host-presentation-is-also-intent-only',[dispatch(role='host')],frames=[['en|setting=1|coins=0|worldx=160.0|hud=false|private=1']],epoch=0,intents=[4],worldx=160)
    case('duplicate-authority-not-committed-again',[authority(),authority(),dispatch()],epoch=3,coins=1,intents=[4])
    case('duplicate-personal-not-executed',[dispatch(input=device(76)),dispatch(input=device(76)),dispatch(2)],frames=[['zh|setting=2|coins=0|worldx=160.0|hud=false|private=1']]*2+[['zh|setting=2|coins=0|worldx=160.0|hud=false|private=2']],intents=[4,4,4],epoch=0,saved_x=147)
    case('authority-remove-and-new-position',[authority(),authority(2,3),dispatch()],frames=[['zh|setting=2|coins=1|worldx=64.0|hud=false|private=1']],epoch=6,worldx=64)
    case('void-call-has-zero-results',[dispatch(event=6),ev('return VoidReturns')],[0],epoch=0,intents=[1])
    case('config-availability-aba',[dict(op='capture_reads',event=4,phase='presentation'),scene(2,**{'item_availability/0/78':False}),scene(3),dict(op='consumer_status',consumer=4)],valid=[False])
    case('config-availability-unrelated-item',[dict(op='capture_reads',event=4,phase='presentation'),scene(2,**{'item_availability/0/73':True}),dict(op='consumer_status',consumer=4)],valid=[True])
    case('static-config-ignores-availability-change',[dict(op='capture_reads',event=5,phase='presentation'),scene(2,**{'item_availability/0/78':False}),dict(op='consumer_status',consumer=5)],valid=[True])
    case('rejected-personal-restores-all-drafts',[authority(),dispatch(input=device(76)),dispatch(2,input=device(70),expect_error='view-injected'),dispatch(2)],frames=[['zh|setting=2|coins=1|worldx=17.0|hud=true|private=1'],['zh|setting=2|coins=1|worldx=17.0|hud=true|private=2']],saved_x=147,epoch=3,worldx=17)
    case('rejected-authority-restores-rng-and-world',[authority(),dict(authority(2,7),expect_error='authority-injected'),ev('return P.Position.X,Seeds:HasSeedEffect(10),P.ControlsEnabled')],[17.0,True,False],epoch=3,coins=1,rng_unchanged=True)
    case('rebuild-world-and-intent-identities',[authority(),dispatch(input=device(76)),dict(op='rebuild'),dispatch(input=device(76))],epoch=3,saved_x=147,stable_intent_ids=True)
    case('unregistered-seed-does-not-mutates-world',[authority(),dispatch(event=9,expect_error='Unverified seed effect consequences'),dispatch()],kind='expected-rejection',epoch=3,worldx=17)
    case('world-record-capacity-rollback',[authority(),dispatch(event=8,expect_error='World record frame capacity exceeded'),dispatch()],kind='expected-rejection',epoch=3)
    for name,code,error in [('idle-write','P.Position=Vector(1,2)','World API requires authority or presentation phase'),('unknown-setter','P.Luck=100','World player property write unregistered'),('wrong-control-type','P.ControlsEnabled=1','ControlsEnabled requires boolean'),('wrong-vector','P.Position={X=1,Y=2}','Foreign or retired value receiver'),('unknown-item','Config:GetCollectible(2)','Uncaptured ItemConfig lookup'),('availability-receiver','Config:GetCollectible(78).IsAvailable(Config)','Foreign ItemConfig receiver'),('availability-arity','Config:GetCollectible(78):IsAvailable(1)','ItemConfig.IsAvailable signature unsupported'),('metadata-write','Config:GetCollectible(78).Quality=0','ItemConfig is read-only')]:
        case('reject-'+name,[ev(code,expect_error=error),dispatch()],kind='expected-rejection',epoch=0)
    case('reject-nonboolean-availability',[scene(2,**{'item_availability/0/78':'yes'}),ev('Config:GetCollectible(78):IsAvailable()',expect_error='Explicit ItemConfig availability required')],kind='expected-rejection')
    def capture(event):return dict(op='capture_reads',event=event,phase='presentation')
    def status(event):return dict(op='consumer_status',consumer=event)
    case('world-position-write-keeps-control-read',[capture(10),authority(event=12),status(10)],valid=[True],epoch=1)
    case('world-position-write-keeps-seed-read',[capture(11),authority(event=12),status(11)],valid=[True],epoch=1)
    case('personal-intent-keeps-world-read',[capture(11),dispatch(),status(11)],valid=[True],epoch=0)
    case('authority-seed-write-invalidates-seed-read',[capture(11),authority(),status(11)],valid=[False],epoch=3)
    case('same-value-world-write-keeps-pure-query',[authority(),capture(11),authority(2),status(11)],valid=[True],epoch=6)
    case('cached-vector-subtract-method',[ev('local a,b=Vector(3,4),Vector(1,2);local sub=a.__sub;local r=sub(a,b);return r.X,r.Y')],[2.0,2.0])
    case('cached-vector-distance',[ev('local a,b=Vector(3,4),Vector(0,0);local f=a.Distance;return f(a,b),f(b,a)')],[5.0,5.0])
    parent.f.freeze_json(MANIFEST,dict(schema='world-view-model-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(parent.f.load(parent.REAL));real['schema']='world-view-real-source-1'
    for c in real['cases']:
        c['menu_profile']=copy.deepcopy(base['menu_profile']);c['world_view_profile']=copy.deepcopy(base['world_view_profile'])
        if c['id']in ['eid-post-render','combined-post-render']:c['steps']=[dispatch(),dispatch(2)];c['requires_hud']=True
    warning=copy.deepcopy(real['cases'][1]);warning['id']='eid-authority-unlock-warning';warning['steps']=[scene(2,**{'item_availability/0/78':False,'item_availability/0/73':False}),dispatch()];warning['requires_hud']=True;real['cases'].append(warning)
    parent.f.freeze_json(REAL,real);print(json.dumps(dict(frozen=True,cases=len(cases),real_cases=len(real['cases']))))
    required=copy.deepcopy(next(c for c in cases if c['id']=='authority-reward-personal-config'));required['id']='required-authority-hud-keeps-personal-save';required['kind']='required-functional-projection';required['frames']=[['zh|setting=1|coins=1|worldx=17.0|hud=true|private=1']]
    parent.f.freeze_json(PROJECTION,dict(schema='required-world-view-projection-1',work_limit=10000000,timeout_seconds=5,cases=[required]))
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--world-view-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary']);raw=a.pop('stdout');error=a.pop('stderr');a.update(stderr_hex=error.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest(),stdout_bytes=len(raw))
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def run(path,out,real=False):
    before=parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in parent.f.load(path)['cases']:
        artifacts=[];reports=[];checks=[]
        def check(k,v):checks.append(dict(check=k,passed=bool(v)))
        for reference in [True,False,False]:
            a,r=invoke(path,c,reference);artifacts.append(a);reports.append(r)
        p=reports[1];check('bounded-structured-result',all(r is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']for a,r in zip(artifacts,reports)));check('callback-completed',all(a['returncode']==0 and r and'semantic'in r for a,r in zip(artifacts,reports)))
        if p and'semantic'in p:
            ordinary=lambda r:[{k:v for k,v in step.items()if k!='metadata'}for step in r['steps']]
            check('ordinary-stock-equivalence',reports[0]['semantic']==p['semantic']and ordinary(reports[0])==ordinary(p));check('repeat-world-private-and-evidence',reports[2]['semantic']==p['semantic']and reports[2]['steps']==p['steps'])
            check('formal-limits',all(r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())and r['private_commit_bytes']<1024**3 and not r['game_started']and not r['full_trace_enabled']for r in reports))
            frames=[s for s in p['steps']if'draws'in s];result_values=[s['values']for s in p['steps']if'values'in s]
            if'values'in c:check('exact-returns',result_values[-1]==c['values'])
            if'frames'in c:check('exact-hud',[[bytes.fromhex(d['text_hex']).decode()for d in s['draws']]for s in frames]==c['frames'])
            if'positions'in c:check('personal-position',[s['draws'][0]['x']for s in frames]==c['positions'])
            if'epoch'in c:check('authority-world-epoch',p['semantic']['world_view_epoch']==c['epoch'])
            if'worldx'in c:check('actual-model-position',p['semantic']['menu_snapshot']['players'][0]['position'][0]==c['worldx'])
            if'coins'in c:check('coins-host-once',p['semantic']['world']['coins']==c['coins']and len(p['semantic']['world']['effects'])==1)
            if'intents'in c:check('every-world-intent-recorded',[len(s['world_records'])for s in frames]==c['intents'])
            if'saved_x'in c:check('personal-save-preserved',json.loads(bytes.fromhex(p['semantic']['mod_stores'][1]['mods/world-view-fixture']['data_hex']))==dict(amount=2,language='zh',x=c['saved_x']))
            if c.get('rng_unchanged'):
                control=next(x for x in rows if x['id']=='authority-query-timepoints')['reports'][1];check('rng-state-restored',p['semantic']['world']['rng_sha256']==control['semantic']['world']['rng_sha256'])
            if c.get('stable_intent_ids'):check('intent-ids-survive-rebuild',frames[0]['world_records']==frames[1]['world_records'])
            if'valid'in c:check('precise-read-set',[s['metadata']['versions_valid']for s in p['steps']if'metadata'in s and'versions_valid'in s['metadata']]==c['valid'])
            check('unproven-intents-never-published',not p['personal_draws_publishable']and not p['automatic_projection_implemented']and all(not x['world_view']['intent_publication_allowed']and x['world_view']['personal_world_commits']==0 for x in p['metadata']))
            if real and'open-via-personal-input'in c['id']:check('actual-menu-open-and-drawn',result_values and result_values[-1]==values(True)and any(s['draws']for s in frames))
            if real and c.get('requires_hud'):check('actual-hud-nonempty',any(s['draws']for s in frames))
        passed=all(x['passed']for x in checks);rows.append(dict(id=c['id'],kind=c.get('kind'),passed=passed,checks=checks,reports=reports,artifacts=artifacts));print(json.dumps(dict(id=c['id'],passed=passed,first_failure=(p or{}).get('first_unsupported_entry'),failed=[x['check']for x in checks if not x['passed']])),flush=True)
    assert before==parent.f.parent.protection.protection()
    result=dict(schema='world-view-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=parent.f.digest(path),driver_sha256=parent.f.digest(Path(__file__)),binaries={p.relative_to(ROOT).as_posix():parent.f.digest(p)for p in [EXE,REF]},work_limit=10000000,timeout_seconds=5,protected_files_unchanged=True,real_source=real,native_equivalence_verified=False,full_ui_gate_passed=False,authority_projection_passed=False,playable=False)
    raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((out/'result.json.gz').read_bytes())==raw;print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows))));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real','projection']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL if a.phase=='real'else PROJECTION if a.phase=='projection'else MANIFEST,a.output,a.phase=='real')else 1)
