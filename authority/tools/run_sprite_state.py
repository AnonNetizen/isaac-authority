"""Frozen Sprite controls, operation state, packed ranges and real entries."""
import argparse,copy,gzip,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_engine_services as e
ROOT=e.ROOT;old=e.old;FOLDER=ROOT/'research/sprite_state';PROFILE=FOLDER/'profile.json';MANIFEST=ROOT/'research/sprite_state_v1.json';CURRENT=ROOT/'research/sprite_state_v2.json';REAL=ROOT/'research/sprite_state_real_v1.json'
EXE=ROOT/'build-sprite-state/Release/authority-sprites.exe';REF=EXE.with_name('authority-sprites-reference.exe');MENU='gfx/ui/modconfig/menu.anm2';OTHER='gfx/eid_transform_icons.anm2';PACKED='gfx/005.100_collectible.anm2'
def freeze():
    data=e.v.s.o.load(PROFILE)
    code="""SpriteMod=RegisterMod('Sprite State Fixture',1)
local cfg=require('json').decode(SpriteMod:LoadData())
SP=Sprite();SP:Load('gfx/ui/modconfig/menu.anm2');SP:SetFrame('Cursor',4)
SpriteMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
SpriteMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;SpriteMod:SaveData(require('json').encode(cfg));SP:SetFrame('Cursor',1);SP.Color=Color(1,0.5,0.25,0.5)end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|root='..SP:GetFrame(),cfg.x,0)
 if Input.IsButtonTriggered('fail')then cfg.x=999;SpriteMod:SaveData('uncommitted');SP:SetFrame('Slider1',7);SP.Color=Color(0,0,0);Isaac.RenderText('unpublished',0,0);error('sprite-injected')end
end)
SpriteMod:AddCallback(3,function()Isaac.RenderText(SP:GetAnimation(),0,0)end)
SpriteMod:AddCallback(4,function()Isaac.RenderText(tostring(SP:GetFrame()),0,0)end)
"""
    p=FOLDER/'main.lua';e.v.s.o.freeze_file(p,code.encode());rr=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/sprite-state-fixture',sha256={'main.lua':old.digest(p)})
    common=dict(source=p.relative_to(ROOT).as_posix(),source_sha256=old.digest(p),modules=dict(entry=0,roots=[rr]),objects=e.v.s.o.load(e.v.s.o.MANIFEST)['cases'][0]['objects'],value_objects=e.v.profile(),
      mod_sdk=e.v.s.profile([rr],[{rr['display']:old.store(1,17,'en')},{rr['display']:old.store(2,137,'zh')}],[0]),engine_services=copy.deepcopy(e.v.s.o.load(e.CURRENT)['cases'][0]['engine_services']),animation_profile=dict(path=PROFILE.relative_to(ROOT).as_posix(),sha256=old.digest(PROFILE)),stores=['{}','{}'])
    cases=[]
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(event=2,**kw):return dict(op='dispatch',event=event,phase='presentation',**kw)
    def cap(event):return dict(op='capture_reads',event=event,phase='presentation')
    def status(id):return dict(op='consumer_status',consumer=id)
    def case(id,steps,expected=None,kind='functional',**kw):
        c=copy.deepcopy(common);c.update(id=id,steps=steps,kind=kind,**kw)
        if expected is not None:c['expected_values']=e.v.values(*expected)
        cases.append(c);return c
    for i,asset in enumerate(data['sprites']):
        rows=[];expected=[]
        for name,frame in asset['animations'].items():
            n=json.dumps(name);last=frame['selectable']-1
            rows.append("SP:SetFrame("+n+","+str(last)+");local named=SP:GetFrame();SP:SetFrame("+str(last)+");local numeric=SP:GetFrame();SP:SetFrame("+n+",0);out[#out+1]="+n+"..':'..named..':'..numeric..':'..SP:GetFrame()")
            expected.append(name+':'+str(frame['native_last_root'])+':'+str(frame['native_last_root'])+':0')
        case('native-frame-controls-'+str(i),[ev('SP:Load('+json.dumps(asset['aliases'][0])+',false);local out={};'+';'.join(rows)+";return table.concat(out,'|')")],['|'.join(expected)],native_animations=len(rows))
    case('requested-frame-preserved',[ev("return SP:GetFrame(),SP:GetAnimation()")],[0,'Cursor'],requested_frame=4,root_frame=0)
    case('numeric-wrapper-ignores-extra-arg',[ev("SP:SetFrame(2,999);return SP:GetFrame(),SP:GetAnimation()")],[0,'Cursor'],requested_frame=2,root_frame=0)
    case('cached-wrapper',[ev("local set=SP.SetFrame;set(SP,'Slider1',7);set(SP,4);return SP:GetFrame(),SP:GetAnimation()")],[4,'Slider1'])
    case('original-load-wrapper',[ev("SP:Load('"+MENU+"',nil);SP:SetFrame('Idle',0);return SP:GetDefaultAnimationName(),SP:IsLoaded()")],['Idle',True],graphics_requested=True)
    case('original-load-wrapper-nonfalse',[ev("SP:Load('"+MENU+"',1);return SP:GetLayerCount()")],[10],graphics_requested=True)
    case('initial-and-forced-play',[ev("SP:Load('"+OTHER+"',false);SP:Play('Arrow');local f=SP:GetFrame();SP:SetFrame('Cursor',1);SP:Play('Arrow',true);return f,SP:GetFrame(),SP:GetAnimation()")],[0,0,'Arrow'])
    case('color-recorded-separately',[ev("SP.Color=Color(1,0.5,0.25,0.5);return SP:GetFrame()")],[0],color=[1,0.5,0.25,0.5,0,0,0])
    case('independent-settings-and-sprites',[dict(dispatch(),role='host'),dispatch(input={'move':True}),dict(dispatch(),role='host')],frames=[['en|x=17|coins=0|root=0'],['zh|x=147|coins=0|root=0'],['en|x=17|coins=0|root=0']],requested_by_role=[4,1])
    case('authority-coins-personal-state',[dict(dispatch(1),role='host',phase='authority'),dispatch(input={'move':True})],frames=[['zh|x=147|coins=1|root=0']],expected_coins=1)
    case('save-reload',[dispatch(input={'move':True}),dict(op='reload_saved'),dispatch()],frames=[['zh|x=147|coins=0|root=0'],['zh|x=147|coins=0|root=0']])
    case('rollback-save-sprite-and-draw',[dispatch(input={'move':True}),dict(dispatch(input={'fail':True}),expect_error='sprite-injected'),dispatch()],frames=[['zh|x=147|coins=0|root=0'],['zh|x=147|coins=0|root=0']],requested_frame=1,root_frame=0,forbidden_animation='Slider1')
    case('name-read-ignores-numeric-frame',[cap(3),ev('SP:SetFrame(2)'),status(3)],valid_status=[True])
    case('name-write-invalidates',[cap(3),ev("SP:SetFrame('Slider1',2)"),status(3)],valid_status=[False])
    case('frame-write-aba',[cap(4),ev('SP:SetFrame(1);SP:SetFrame(4)'),status(4)],valid_status=[False])
    case('frame-read-ignores-color',[cap(4),ev('SP.Color=Color(0,1,0)'),status(4)],valid_status=[True])
    case('load-invalidates-frame',[cap(4),ev("SP:Load('"+MENU+"');SP:SetFrame('Cursor',4)"),status(4)],valid_status=[False])
    case('retire-sprite-operation-records',[ev("for i=1,128 do local s=Sprite();s:Load('"+MENU+"',false);s:SetFrame('Cursor',i%5);if i%16==0 then collectgarbage('collect')end end;collectgarbage('collect')"),dict(op='sprite_state')],live_states=1)
    case('packed-proof-reused',[ev("SP:Load('"+PACKED+"',false);SP:SetFrame('Idle',0);SP:Load('"+PACKED+"',false);SP:SetFrame('ShopIdle',1);return SP:GetFrame()")],[1],packed_cached=True)
    for id,code,error in [
      ('unknown-animation',"SP:SetFrame('NotRegistered',0)",'Unregistered sprite animation'),
      ('frame-range',"SP:SetFrame('Cursor',5)",'Unverified sprite frame range'),
      ('negative-frame',"SP:SetFrame('Cursor',-1)",'Unverified sprite frame range'),
      ('unknown-postload-frame',"SP:Load('"+MENU+"');return SP:GetFrame()",'Sprite animation selection unknown after Load'),
      ('numeric-without-selection',"SP:Load('"+MENU+"');SP:SetFrame(0)",'Numeric SetFrame has no selected animation'),
      ('play-continuation',"SP:Play('Cursor',false)",'Sprite.Play continuation contract unverified'),
      ('unknown-update',"SP:Update()",'Sprite.Update contract not implemented'),
      ('unknown-render',"SP:Render(Vector(0,0))",'Sprite.Render contract not implemented'),
      ('unknown-color-alias',"return SP.Color",'Sprite.Color contract not implemented'),
      ('foreign-color',"SP.Color=KColor(1,1,1,1)",'Foreign or retired value receiver'),
      ('cached-wrong-receiver',"SP.SetFrame(Game(),'Cursor',0)",'Foreign or stale object receiver')]:
        case('reject-'+id,[ev(code,expect_error=error),dispatch(3)],frames=[['Cursor']],requested_frame=4,root_frame=0)
    case('reject-operation-cap',[ev("for i=1,129 do SP:SetFrame('Cursor',0)end")],kind='process-rejection',error='Sprite operation capacity exceeded')
    for id,mutate,error in [
      ('range-hash',lambda p:p['range_proofs'][0]['ranges'][0].update(sha256='0'*64),'Packed sprite range hash mismatch'),
      ('conflicting-range',lambda p:p['range_proofs'][0]['ranges'].append(dict(p['range_proofs'][0]['ranges'][0],sha256='0'*64)),'Conflicting packed range proof')]:
        corrupted=copy.deepcopy(data);a=next(a for a in corrupted['sprites']if a['aliases'][0]==PACKED);mutate(a);path=FOLDER/(id+'.json');e.v.s.o.freeze_json(path,corrupted)
        c=case('reject-'+id,[ev("SP:Load('"+PACKED+"',false)",expect_error=error),dispatch(3)],frames=[['Cursor']],requested_frame=4,root_frame=0);c['animation_profile']=dict(path=path.relative_to(ROOT).as_posix(),sha256=old.digest(path))
    e.v.s.o.freeze_json(MANIFEST,dict(schema='sprite-state-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    hardened=copy.deepcopy(cases)
    for id,key,value,error in [('unknown-storage','storage','unknown','Unknown sprite resource storage'),('loose-resource-mismatch','path','mods/mod_config_menu_cn_2494192799/resources/gfx/not-frozen.anm2','Animation resource differs from verified base catalog')]:
        bad=copy.deepcopy(data);bad['sprites'][0][key]=value;path=FOLDER/(id+'.json');e.v.s.o.freeze_json(path,bad)
        c=copy.deepcopy(common);c.update(id='reject-'+id,kind='process-rejection',steps=[],error=error,animation_profile=dict(path=path.relative_to(ROOT).as_posix(),sha256=old.digest(path)));hardened.append(c)
    e.v.s.o.freeze_json(CURRENT,dict(schema='sprite-state-contracts-2',work_limit=10000000,timeout_seconds=5,cases=hardened))
    real=copy.deepcopy(e.v.s.o.load(e.REAL))
    for c in real['cases']:c['animation_profile']=copy.deepcopy(common['animation_profile'])
    real['schema']='sprite-state-real-entry-1';e.v.s.o.freeze_json(REAL,real)
    print(json.dumps(dict(frozen=True,cases=len(hardened),native_animation_controls=sum(c.get('native_animations',0)for c in cases),real_entries=3)))
def invoke(path,c,reference=False):
    start=time.perf_counter()
    try:p=subprocess.run([str(REF if reference else EXE),'--sprite-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Sprite output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r
def setup():e.EXE=EXE;e.REF=REF;e.invoke=invoke;e.setup()
def run(path,out,real=False):
    setup();r=e.v.s.run(path,out,real);cases={c['id']:c for c in e.v.s.o.load(path)['cases']}
    for row in r['cases']:
        c=cases[row['id']];p=row['reports'][1];checks=row['checks']
        if p and 'semantic'in p:
            states=p['semantic']['sprite_states'];s=states[1][0]if states[1]else None
            def check(name,value):checks.append(dict(check=name,passed=bool(value)))
            if 'requested_frame'in c:check('requested-and-root-frame-distinct',s['requested_frame']==c['requested_frame']and s['root_frame']==c['root_frame'])
            if 'requested_by_role'in c:check('independent-role-state',[role[0]['requested_frame']for role in states]==c['requested_by_role'])
            if 'color'in c:check('color-components-recorded',s['color']==c['color'])
            if c.get('forbidden_animation'):check('rejected-command-discarded',all(cmd.get('animation')!=c['forbidden_animation']for cmd in s['commands']))
            if 'live_states'in c:check('retired-commands-reclaimed',len(states[1])==c['live_states'])
            if 'graphics_requested'in c:check('unchanged-load-wrapper',s['commands'][0]['graphics_requested']==c['graphics_requested'])
            if c.get('packed_cached'):
                m=p['metadata'][1]['sprite_state']['resources'];check('packed-ranges-not-rehashed',m['range_cache_hits']>0 and m['range_checks']>0 and not m['full_archives_rehashed'])
            check('full-sprite-state-repeat',all(x['semantic']['sprite_states']==states for x in row['reports']))
        row['passed']=all(x['passed']for x in checks)
    r['passed']=len(r['cases'])==len(cases)and all(c['passed']for c in r['cases']);r['schema']='sprite-state-results-1';r['sprite_driver_sha256']=old.digest(Path(__file__))
    raw=(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode();p=out/'result.json.gz';p.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(p.read_bytes())==raw
    print(json.dumps(dict(sprite_finished=True,passed=r['passed'],cases=len(r['cases']),failures=[dict(id=c['id'],checks=[x['check']for x in c['checks']if not x['passed']])for c in r['cases']if not c['passed']])),flush=True);return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL if a.phase=='real'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
