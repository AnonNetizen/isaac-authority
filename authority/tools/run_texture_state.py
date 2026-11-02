"""Bounded texture contracts, unchanged sprite controls and real entry attempts."""
import argparse,copy,gzip,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_sprite_state as s
ROOT=s.ROOT;old=s.old;FOLDER=ROOT/'research/texture_state';PROFILE=FOLDER/'profile.json';MANIFEST=ROOT/'research/texture_state_v1.json';CURRENT=ROOT/'research/texture_state_v2.json';REAL=ROOT/'research/texture_state_real_v1.json'
EXE=ROOT/'build-texture-state/Release/authority-textures.exe';REF=EXE.with_name('authority-textures-reference.exe')
MENU=s.MENU;NEW='gfx/ui/modconfig/arrows.png';ORIGINAL='gfx/ui/modconfig/popup_thin_small.png';PACKED=s.PACKED;QUESTION='gfx/items/collectibles/questionmark.png'

def freeze():
    code="""TextureMod=RegisterMod('Texture State Fixture',1)
local cfg=require('json').decode(TextureMod:LoadData())
Tex=Sprite();Tex:Load('gfx/ui/modconfig/menu.anm2',false);Tex:SetFrame('Cursor',4)
TextureMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
TextureMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;TextureMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('fail_save')then error('texture-fail-save')end
 if Input.IsButtonTriggered('move')or Input.IsButtonTriggered('fail_replace')then Tex:ReplaceSpritesheet(5,'gfx/ui/modconfig/arrows.png')end
 if Input.IsButtonTriggered('fail_replace')then error('texture-fail-replace')end
 if Input.IsButtonTriggered('graphics')or Input.IsButtonTriggered('fail_graphics')then Tex:LoadGraphics()end
 if Input.IsButtonTriggered('fail_graphics')then error('texture-fail-graphics')end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins(),cfg.x,0)
 if Input.IsButtonTriggered('fail_draw')then error('texture-fail-draw')end
end)
"""
    source=FOLDER/'main.lua';s.e.v.s.o.freeze_file(source,code.encode());rr=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/texture-state-fixture',sha256={'main.lua':old.digest(source)})
    common=copy.deepcopy(s.e.v.s.o.load(s.CURRENT)['cases'][0]);common={k:v for k,v in common.items()if k in ['objects','value_objects','engine_services','animation_profile','stores']}
    common.update(source=source.relative_to(ROOT).as_posix(),source_sha256=old.digest(source),modules=dict(entry=0,roots=[rr]),mod_sdk=s.e.v.s.profile([rr],[{rr['display']:old.store(1,17,'en')},{rr['display']:old.store(2,137,'zh')}],[0]),graphics_profile=dict(path=PROFILE.relative_to(ROOT).as_posix(),sha256=old.digest(PROFILE)))
    cases=[]
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(**buttons):return dict(op='dispatch',event=2,phase='presentation',input=buttons)
    def state():return dict(op='texture_state')
    def case(id,steps,values=None,kind='functional',**kw):
        c=copy.deepcopy(common);c.update(id=id,steps=steps,kind=kind,**kw)
        if values is not None:c['expected_values']=s.e.v.values(*values)
        cases.append(c);return c
    replace="Tex:ReplaceSpritesheet(5,'"+NEW+"')"
    load='Tex:LoadGraphics()'
    case('replace-returns-changed-boolean',[ev('return '+replace)],[True],selected={5:NEW},loaded=False,commands=['Load','SetFrame','ReplaceSpritesheet'])
    case('same-identity-returns-false',[ev('return Tex:ReplaceSpritesheet(5,\''+ORIGINAL+'\')')],[False],selected={},loaded=False)
    case('repeat-replace-return',[ev('local a='+replace+';return a,'+replace)],[True,False],selected={5:NEW},loaded=False,selection_version=1)
    case('alias-normalization',[ev("local a=Tex:ReplaceSpritesheet(5,'GFX/UI/MODCONFIG/ARROWS.PNG');return a,"+replace)],[True,False],selected={5:NEW},loaded=False)
    case('shared-spritesheet-layer-independent',[ev("return Tex:ReplaceSpritesheet(2,'"+NEW+"')")],[True],selected={2:NEW},loaded=False,unchanged_layers=[3])
    case('load-graphics-commits-selection',[ev(replace),state(),ev(load),state()],selected={5:NEW},loaded=True,commands=['Load','SetFrame','ReplaceSpritesheet','LoadGraphics'],pending_snapshot=True)
    case('load-graphics-from-false',[ev(load)],selected={},loaded=True,graphics_version=1)
    case('load-true-realizes-base',[ev("Tex:Load('"+MENU+"',true)")],selected={},loaded=True,graphics_version=1,commands=['Load'])
    case('replace-does-not-load',[ev(load+';'+replace)],selected={5:NEW},loaded=True,loaded_overrides={},graphics_version=1)
    case('second-graphics-commits-new-selection',[ev(load+';'+replace+';'+load)],selected={5:NEW},loaded=True,graphics_version=2)
    case('repeated-load-graphics-recorded',[ev(load+';'+load)],selected={},loaded=True,graphics_version=2,commands=['Load','SetFrame','LoadGraphics','LoadGraphics'])
    case('replacement-aba',[ev('local a='+replace+";local b=Tex:ReplaceSpritesheet(5,'"+ORIGINAL+"');return a,b")],[True,True],selected={},loaded=False,selection_version=2)
    case('reload-clears-selection',[ev(replace+';'+load+";Tex:Load('"+MENU+"',false)")],selected={},loaded=False,commands=['Load'])
    case('cached-methods',[ev("local r,g=Tex.ReplaceSpritesheet,Tex.LoadGraphics;local changed=r(Tex,5,'"+NEW+"');g(Tex);return changed")],[True],selected={5:NEW},loaded=True)
    case('frame-query-unchanged',[ev(replace+';'+load+';return Tex:GetAnimation(),Tex:GetFrame()')],['Cursor',0],selected={5:NEW},loaded=True)
    case('numeric-frame-unchanged',[ev(replace+";Tex:SetFrame(2);"+load+';return Tex:GetFrame()')],[0],selected={5:NEW},loaded=True)
    case('packed-questionmark',[ev("Tex:Load('"+PACKED+"',true);local a=Tex:ReplaceSpritesheet(1,'"+QUESTION+"');Tex:LoadGraphics();Tex:SetFrame('Idle',0);return a,Tex:GetAnimation()")],[True,'Idle'],sprite=PACKED,selected={1:QUESTION},loaded=True,packed=True)
    case('packed-repeat-cache',[ev("Tex:Load('"+PACKED+"',false);local r=Tex.ReplaceSpritesheet;local a=r(Tex,1,'"+QUESTION+"');Tex:LoadGraphics();return a,r(Tex,1,'"+QUESTION+"')")],[True,False],sprite=PACKED,selected={1:QUESTION},loaded=True,packed=True)
    case('independent-role-config-and-textures',[dict(dispatch(),role='host'),dispatch(move=True,graphics=True),dict(dispatch(),role='host')],selected={5:NEW},loaded=True,host_unmodified=True,frames=[['en|x=17|coins=0'],['zh|x=147|coins=0'],['en|x=17|coins=0']])
    case('authority-world-once-personal-textures',[dict(op='dispatch',event=1,phase='authority',role='host'),dispatch(move=True,graphics=True)],selected={5:NEW},loaded=True,expected_coins=1,frames=[['zh|x=147|coins=1']])
    case('configuration-reloads-independently',[dispatch(move=True,graphics=True),dict(op='reload_saved'),dispatch()],selected={},loaded=False,frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']])
    case('accepted-history-rebuild',[dispatch(move=True,graphics=True),dict(op='rebuild'),dispatch()],selected={5:NEW},loaded=True,frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']])
    for stage in ['save','replace','graphics','draw']:
        failed=dispatch(move=True,graphics=True,**{'fail_'+stage:True});failed['expect_error']='texture-fail-'+stage
        case('rollback-after-'+stage,[dispatch(move=True,graphics=True),failed,dispatch()],selected={5:NEW},loaded=True,selection_version=1,graphics_version=1,frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']],no_failed_draw=True)
    case('gc-retires-texture-state',[ev("for i=1,128 do local t=Sprite();t:Load('"+MENU+"',false);t:ReplaceSpritesheet(5,'"+NEW+"');if i%16==0 then collectgarbage('collect')end end;collectgarbage('collect')"),state()],selected={},loaded=False,live_states=1)
    for id,code,error in [
      ('invalid-layer',"Tex:ReplaceSpritesheet(999,'"+NEW+"')",'Unregistered sprite layer'),
      ('fractional-layer',"Tex:ReplaceSpritesheet(1.5,'"+NEW+"')",'Expected integer'),
      ('unknown-image',"Tex:ReplaceSpritesheet(5,'gfx/unknown.png')",'Unregistered replacement image'),
      ('wrong-type',"Tex:ReplaceSpritesheet(5,3)",'Expected string'),
      ('wrong-signature',"Tex:ReplaceSpritesheet(5,'"+NEW+"',true)",'Sprite.ReplaceSpritesheet signature unsupported'),
      ('graphics-argument','Tex:LoadGraphics(true)','Sprite.LoadGraphics signature unsupported'),
      ('foreign-receiver',"Tex.ReplaceSpritesheet(Game(),5,'"+NEW+"')",'Foreign or stale object receiver'),
      ('unloaded-receiver',"Sprite():ReplaceSpritesheet(0,'"+NEW+"')",'Sprite animation resource not loaded'),
      ('unloaded-graphics','Sprite():LoadGraphics()','Sprite animation resource not loaded'),
      ('unknown-render','Tex:Render(Vector(0,0))','Sprite.Render contract not implemented')]:
        case('reject-'+id,[ev(code,expect_error=error)],selected={},loaded=False,commands=['Load','SetFrame'])
    case('reject-operation-cap',[ev('for i=1,129 do '+replace+' end')],kind='process-rejection',error='Sprite operation capacity exceeded')
    profile=s.e.v.s.o.load(PROFILE)
    for id,change,error,process in [
      ('loose-hash',lambda p:p['images'][0].update(sha256='0'*64),'Texture resource hash mismatch',False),
      ('loose-size',lambda p:p['images'][0].update(bytes=p['images'][0]['bytes']+1),'Texture resource size mismatch',False),
      ('unknown-storage',lambda p:p['images'][0].update(storage='unknown'),'Unknown texture resource storage',True),
      ('layer-coverage',lambda p:p['sprites'][0]['layers'].pop(),'Texture layer coverage mismatch',True),
      ('packed-range',lambda p:next(x for x in p['images']if x['path'].endswith('/questionmark.png'))['range_proofs'][0]['ranges'][-1].update(sha256='0'*64),'Packed sprite range hash mismatch',False)]:
        bad=copy.deepcopy(profile);change(bad);path=FOLDER/(id+'.json');s.e.v.s.o.freeze_json(path,bad)
        code="Tex:ReplaceSpritesheet(5,'gfx/ui/modconfig/menu.png')"if id.startswith('loose-')else"Tex:ReplaceSpritesheet(5,'"+QUESTION+"')"
        c=case('reject-'+id,[]if process else[ev(code,expect_error=error)],kind='process-rejection'if process else'expected-rejection',error=error,selected={},loaded=False)
        c['graphics_profile']=dict(path=path.relative_to(ROOT).as_posix(),sha256=old.digest(path))
    s.e.v.s.o.freeze_json(MANIFEST,dict(schema='texture-state-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(s.e.v.s.o.load(s.REAL))
    for c in real['cases']:c['graphics_profile']=copy.deepcopy(common['graphics_profile'])
    real['schema']='texture-state-real-entry-1';s.e.v.s.o.freeze_json(REAL,real)
    print(json.dumps(dict(frozen=True,cases=len(cases),real_entries=len(real['cases']))))

def freeze_witness():
    data=copy.deepcopy(s.e.v.s.o.load(MANIFEST));base=copy.deepcopy(data['cases'][0])
    for key in ['expected_values','selected','loaded','commands']:base.pop(key,None)
    for id,steps,argument in [
      ('sdk-string-event-refusal-witness',[dict(op='evaluate',code="TextureMod:AddCallback('EIDCallbacks.SEARCH_NAME_CONVERSION',function()end)",expect_error='Expected integer')],dict(index=2,type='string',bytes_hex='EIDCallbacks.SEARCH_NAME_CONVERSION'.encode().hex())),
      ('first-refusal-witness-preserved',[dict(op='evaluate',code="Tex:ReplaceSpritesheet(999,'"+NEW+"')",expect_error='Unregistered sprite layer'),dict(op='evaluate',code='Tex:LoadGraphics(true)',expect_error='Sprite.LoadGraphics signature unsupported')],dict(index=2,type='number',integer=999))]:
        c=copy.deepcopy(base);c.update(id=id,steps=steps,kind='expected-rejection',selected={},loaded=False,commands=['Load','SetFrame'],failure_witness_argument=argument);data['cases'].append(c)
    data['schema']='texture-state-contracts-2';s.e.v.s.o.freeze_json(CURRENT,data)
    print(json.dumps(dict(witness_manifest=True,cases=len(data['cases']))))

def invoke(path,c,reference=False):
    start=time.perf_counter()
    try:p=subprocess.run([str(REF if reference else EXE),'--texture-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Texture output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r

def setup():s.EXE=EXE;s.REF=REF;s.invoke=invoke;s.setup()
def run(path,out,real=False):
    setup();r=s.run(path,out,real);cases={c['id']:c for c in s.e.v.s.o.load(path)['cases']};profile=s.e.v.s.o.load(PROFILE)
    canonical={alias.casefold():a['path']for a in profile['images']for alias in [a['path'],*a['aliases']]}
    sprites={a['path']:{x['layer']:x['image']for x in a['layers']}for a in profile['sprites']}
    animation=s.e.v.s.o.load(s.PROFILE);sprite_alias={alias.casefold():a['path']for a in animation['sprites']for alias in [a['path'],*a['aliases']]}
    for row in r['cases']:
        c=cases[row['id']];p=row['reports'][1]
        def check(name,value):row['checks'].append(dict(check=name,passed=bool(value)))
        if p and 'semantic'in p and 'graphics_profile'in c:
            state=p['semantic']['sprite_graphics'];a=state[1][0];base=sprites[sprite_alias[c.get('sprite',MENU).casefold()]]
            selected=base|{int(k):canonical[v.casefold()]for k,v in c.get('selected',{}).items()}
            def mapping(x):return {v['layer']:v['image']for v in x}
            if 'selected'in c:check('layer-selection-exact',mapping(a['selected'])==selected)
            if 'loaded'in c:
                loaded=base|{int(k):canonical[v.casefold()]for k,v in c.get('loaded_overrides',c.get('selected',{})).items()}if c['loaded']else{}
                check('loaded-and-pending-distinct',mapping(a['loaded'])==loaded and a['graphics_loaded']==c['loaded'])
            for field in ['selection_version','graphics_version']:
                if field in c:check(field,a[field]==c[field])
            if c.get('host_unmodified'):check('host-state-independent',mapping(state[0][0]['selected'])==base and not state[0][0]['graphics_loaded'])
            if c.get('commands'):check('operation-order',[x['op']for x in p['semantic']['sprite_states'][1][0]['commands']]==c['commands'])
            if c.get('live_states'):check('gc-retired-state',len(state[1])==c['live_states'])
            if c.get('pending_snapshot'):
                snapshots=[x['states'][0]for x in p['steps']if 'states'in x];check('intermediate-pending-state',len(snapshots)==2 and snapshots[0]['selected']==snapshots[1]['selected']and not snapshots[0]['loaded']and snapshots[1]['loaded']==snapshots[1]['selected'])
            if c.get('packed'):check('packed-proof-used',p['metadata'][1]['sprite_state']['resources']['range_cache_hits']>0)
            if c.get('failure_witness_argument'):
                witness=p['metadata'][1]['texture_state']['resources']['first_failure'];check('bounded-first-failure-witness',witness is not None and c['failure_witness_argument']in witness['arguments']and len(witness['arguments'])<=6 and 0<len(witness['frames'])<=8)
            check('repeat-texture-state',all(x['semantic']['sprite_graphics']==state for x in row['reports']))
        row['passed']=all(x['passed']for x in row['checks'])
    r['passed']=len(r['cases'])==len(cases)and all(c['passed']for c in r['cases']);r['schema']='texture-state-results-1';r['texture_driver_sha256']=old.digest(Path(__file__))
    raw=(json.dumps(r,separators=(',',':'))+'\n').encode();p=out/'result.json.gz';p.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(p.read_bytes())==raw
    print(json.dumps(dict(texture_finished=True,passed=r['passed'],cases=len(r['cases']),failures=[dict(id=c['id'],checks=[x['check']for x in c['checks']if not x['passed']])for c in r['cases']if not c['passed']])),flush=True);return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real','sprites']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze();freeze_witness()
    else:sys.exit(0 if run(REAL if a.phase=='real'else s.CURRENT if a.phase=='sprites'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
