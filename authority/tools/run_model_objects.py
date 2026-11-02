"""Bounded object/resource contracts and unchanged real-source attempts."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
sys.dont_write_bytecode=True
import run_frozen_modules as m
ROOT=m.ROOT;old=m.old;EXE=ROOT/'build-model-objects/Release/authority-objects.exe';REF=EXE.with_name('authority-objects-reference.exe')
FOLDER=ROOT/'research/model_objects';MANIFEST=ROOT/'research/model_objects_v1.json';REAL=ROOT/'research/model_objects_real_v1.json';MODULES=ROOT/'research/model_objects_modules_v1.json';CATALOG=FOLDER/'resources.json'
MENU='gfx/ui/modconfig/menu.anm2';OTHER='gfx/eid_transform_icons.anm2'

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def freeze_file(p,data):
    if p.exists():assert p.read_bytes()==data,'Frozen object input changed: '+str(p)
    else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
def freeze_json(p,data):freeze_file(p,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
def resource_catalog():
    original=load(ROOT/'research/slice3_ui_resources.json');game=Path(load(ROOT/'research/slice3_ui_inputs.json')['original_game_root']);sprites=[];omitted=[]
    for entry in original['resources']:
        if entry['kind']!='sprite':continue
        if entry.get('storage'):
            omitted.append(dict(path=entry['path'],reason='packed resource contract not installed'));continue
        p=game/entry['path'];tree=ET.parse(p).getroot();assert tree.tag=='AnimatedActor'
        default=tree.find('Animations').attrib['DefaultAnimation'];layers=[int(n.attrib['Id'])for n in tree.findall('Content/Layers/Layer')]
        files={entry['path']}
        for n in tree.findall('Content/Spritesheets/Spritesheet'):
            rel=n.attrib['Path'].replace('\\','/');assert not Path(rel).is_absolute()and '..'not in Path(rel).parts
            files.add((Path(entry['path']).parent/rel).as_posix())
        assert files=={f['path']for f in entry['files']}
        assert default==entry['default_animation']and layers==entry['layers']
        for f in entry['files']:assert old.digest(game/f['path'])==f['sha256']
        sprites.append(dict(path=entry['path'],aliases=entry['aliases'],default_animation=default,layers=layers,files=entry['files']))
    return dict(schema='frozen-object-resources-1',game_root=game.as_posix(),source_manifest_sha256=old.digest(ROOT/'research/slice3_ui_resources.json'),metadata_extractor='Python ElementTree over hash-pinned original ANM2',sprites=sprites,omitted=omitted)

def freeze():
    FOLDER.mkdir(exist_ok=True);freeze_json(CATALOG,resource_catalog())
    source="""ObjectModelMod=RegisterMod('Object Model',1)
local cfg=require('json').decode(ObjectModelMod:LoadData())
ObjectSprite=Sprite();ObjectSprite:Load('gfx/ui/modconfig/menu.anm2',false)
OtherSprite=Sprite();OtherSprite:Load('gfx/ui/modconfig/menu.anm2',false)
local sprite=ObjectSprite;local game=Game()
ObjectModelMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
ObjectModelMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;ObjectModelMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('change')then sprite:Load('gfx/eid_transform_icons.anm2',false)end
 Isaac.RenderText(cfg.language..'|amount='..cfg.amount..'|default='..sprite:GetDefaultAnimationName()..'|players='..game:GetNumPlayers(),cfg.x,game:GetFrameCount())
 if Input.IsButtonTriggered('fail')then cfg.x=cfg.x+100;ObjectModelMod:SaveData(require('json').encode(cfg));sprite:Load('gfx/eid_transform_icons.anm2',false);Isaac.RenderText('unpublished',0,0);error('object-injected')end
 if Input.IsButtonTriggered('unknown')then pcall(sprite.Reset,sprite)end
end)
"""
    freeze_file(FOLDER/'main.lua',source.encode('utf-8'))
    ephemeral="local m=RegisterMod('Ephemeral Object',1)\nm:AddCallback(2,function()local s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',false);Isaac.RenderText(s:GetDefaultAnimationName(),0,0)end)\n"
    freeze_file(FOLDER/'ephemeral.lua',ephemeral.encode('utf-8'))
    frame="local m=RegisterMod('Frame Snapshot',1)\nlocal g=Game();m:AddCallback(2,function()Isaac.RenderText(tostring(g:GetFrameCount()),0,0)end)\n"
    freeze_file(FOLDER/'frame.lua',frame.encode('utf-8'))
    def objects(catalog=CATALOG,scene=None):return dict(catalog=catalog.relative_to(ROOT).as_posix(),catalog_sha256=old.digest(catalog),flags={'REPENTANCE_PLUS':True},scene=scene if scene is not None else dict(revision=1,frame_count=42,num_players=2))
    cases=[]
    def case(name,steps,expected=None,kind='functional',source=FOLDER/'main.lua',**extra):
        c=dict(id=name,source=source.relative_to(ROOT).as_posix(),source_sha256=old.digest(source),objects=objects(),stores=[old.store(1,17,'en'),old.store(2,137,'zh')],steps=steps,kind=kind,**extra)
        if expected is not None:c['expected_values']=m.values(*expected)
        cases.append(c);return c
    def evaluate(code,**kw):return dict(op='evaluate',code=code,**kw)
    def capture(**kw):return dict(op='capture_reads',event=2,phase='presentation',input=kw)
    status=dict(op='consumer_status',consumer=2)
    case('constructor-and-model-identity',[evaluate("local a=Sprite();local b=Sprite();return type(a),rawequal(a,b),rawequal(Game(),Game()),REPENTANCE_PLUS")],['userdata',False,True,True])
    case('unloaded-metadata',[evaluate("local a=Sprite();return a:GetFilename(),a:GetDefaultAnimationName(),a:GetLayerCount(),a:IsLoaded()")],['','',0,False])
    case('actual-menu-metadata',[evaluate("return ObjectSprite:GetFilename(),ObjectSprite:GetDefaultAnimationName(),ObjectSprite:GetLayerCount(),ObjectSprite:IsLoaded()")],[MENU,'Idle',10,True])
    for asset in load(CATALOG)['sprites']:
        alias=asset['aliases'][0]
        case('asset-'+Path(alias).stem,[evaluate("local s=Sprite();s:Load("+json.dumps(alias)+",true);return s:GetDefaultAnimationName(),s:GetLayerCount()")],[asset['default_animation'],len(asset['layers'])])
    case('cached-method-current-receiver',[evaluate("local f=ObjectSprite.GetDefaultAnimationName;OtherSprite:Load('gfx/eid_transform_icons.anm2',false);return f(ObjectSprite),f(OtherSprite),rawequal(f,OtherSprite.GetDefaultAnimationName)")],['Idle','active',True])
    case('cached-load-current-receiver',[evaluate("local f=ObjectSprite.Load;f(OtherSprite,'gfx/eid_transform_icons.anm2',false);return ObjectSprite:GetDefaultAnimationName(),OtherSprite:GetDefaultAnimationName()")],['Idle','active'])
    case('explicit-scene-values',[evaluate("local g=Game();return g:GetFrameCount(),g:GetNumPlayers()")],[42,2])
    case('private-config-resource-state',[dict(capture(),role='host'),capture(move=True,change=True),dict(capture(),role='host')],kind='draws',expected_draws=[('en|amount=1|default=Idle|players=2',17,42),('zh|amount=2|default=active|players=2',147,42),('en|amount=1|default=Idle|players=2',17,42)])
    case('save-reload-resource-state',[capture(move=True,change=True),dict(op='reload_saved'),capture()],kind='draws',expected_draws=[('zh|amount=2|default=active|players=2',147,42),('zh|amount=2|default=Idle|players=2',147,42)])
    case('object-write-aba',[capture(),status,evaluate("ObjectSprite:Load('gfx/eid_transform_icons.anm2',false);ObjectSprite:Load('gfx/ui/modconfig/menu.anm2',false)"),status],kind='versions',valid_status=[True,False])
    case('other-object-write-isolated',[capture(),evaluate("OtherSprite:Load('gfx/eid_transform_icons.anm2',false)"),status],kind='versions',valid_status=[True])
    frame_status=dict(op='consumer_status',consumer=1)
    def scene(revision,frame_count=42,num_players=2,**kw):return dict(op='set_scene',scene=dict(revision=revision,frame_count=frame_count,num_players=num_players),**kw)
    case('scene-field-precision',[capture(),scene(2,num_players=1),frame_status,scene(3,frame_count=43,num_players=1),frame_status],source=FOLDER/'frame.lua',kind='versions',valid_status=[True,False])
    case('scene-field-aba',[capture(),scene(2,frame_count=43),scene(3),frame_status],source=FOLDER/'frame.lua',kind='versions',valid_status=[False])
    case('scene-history-recovery',[scene(2,frame_count=51),capture(move=True,change=True),dict(capture(fail=True),expect_error='object-injected'),capture()],kind='rollback',expected_draws=[('zh|amount=2|default=active|players=2',147,51),('zh|amount=2|default=active|players=2',147,51)])
    case('object-gc-retirement',[capture(),dict(op='consumer_status',consumer=1),dict(op='gc'),dict(op='consumer_status',consumer=1),dict(op='object_status'),evaluate("local s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',false)"),dict(op='gc'),dict(op='consumer_status',consumer=1),dict(op='object_status')],source=FOLDER/'ephemeral.lua',kind='gc',valid_status=[True,False,False])
    case('bounded-gc-churn',[evaluate("for i=1,4096 do local s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',false);if i%32==0 then collectgarbage('collect')end end;collectgarbage('collect')"),dict(op='object_status')],kind='churn')
    for name,code,error in [
        ('wrong-receiver',"ObjectSprite.Load({},'gfx/ui/modconfig/menu.anm2',false)",'Foreign or stale object receiver'),
        ('wrong-object-kind',"ObjectSprite.Load(Game(),'gfx/ui/modconfig/menu.anm2',false)",'Foreign or stale object receiver'),
        ('unknown-method',"pcall(function()ObjectSprite:Reset()end)",'Sprite.Reset contract not implemented'),
        ('property-write',"ObjectSprite.FlipX=true",'Object property write contract not implemented'),
        ('missing-resource',"ObjectSprite:Load('gfx/not-registered.anm2',false)",'Unregistered Sprite resource'),
        ('resource-path-escape',"ObjectSprite:Load('../outside.anm2',false)",'Frozen module path outside registered roots'),
        ('bad-graphics-flag',"ObjectSprite:Load('gfx/ui/modconfig/menu.anm2',1)",'Sprite.Load graphics flag must be boolean'),
        ('bad-constructor',"Sprite(1)",'Zero-argument object constructor required'),
        ('unknown-game-query',"Game():GetRoom()",'Game.GetRoom contract not implemented')]:
        case('reject-'+name,[evaluate(code,expect_error=error),capture()],kind='recovery')
    case('reject-scene-revision',[scene(1,expect_error='Scene revision must increase'),capture()],kind='recovery')
    case('reject-personal-scene',[scene(2,role='personal',expect_error='Scene snapshots require authority role'),capture()],kind='recovery')
    case('reject-missing-scene-field',[evaluate("return Game():GetFrameCount()",expect_error='Missing authoritative scene field')],kind='recovery')['objects']['scene']=dict(revision=1,num_players=2)
    case('reject-live-object-cap',[evaluate("held={};for i=1,1025 do held[i]=Sprite()end")],kind='process-rejection',error='Live object capacity exceeded')
    case('reject-object-work-budget',[evaluate("while true do local s=Sprite();collectgarbage('collect')end")],kind='process-rejection',error='Boundary work limit exceeded')
    case('reject-catalog-hash',[],kind='process-rejection',error='Object resource catalog hash mismatch')['objects']['catalog_sha256']='0'*64
    for name,mutate,error in [
      ('dependency-hash',lambda j:j['sprites'][0]['files'][0].update(sha256='0'*64),'Object resource dependency hash mismatch'),
      ('alias-collision',lambda j:j['sprites'][1]['aliases'].append(MENU),'Ambiguous object resource alias')]:
        j=load(CATALOG);mutate(j);p=FOLDER/(name+'.json');freeze_json(p,j);case('reject-'+name,[],kind='process-rejection',error=error)['objects']=objects(p)
    freeze_json(MANIFEST,dict(schema='model-object-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    mods=copy.deepcopy(load(m.MANIFEST))
    for c in mods['cases']:c['objects']=objects()
    mods['schema']='model-objects-unchanged-module-contracts-1';freeze_json(MODULES,mods)
    real=copy.deepcopy(load(m.REAL))
    for c in real['cases']:c['objects']=objects()
    real['schema']='model-objects-unchanged-real-entry-1';freeze_json(REAL,real)
    print(json.dumps(dict(frozen=True,object_cases=len(cases),module_cases=len(mods['cases']),real_entries=len(real['cases']),resource_copies=0)))

def invoke(path,c,reference=False):
    start=time.perf_counter();exe=REF if reference else EXE
    try:p=subprocess.run([str(exe),'--object-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Object output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r

def run(path,out,real=False):
    before=m.protected();sourcecatalog=resource_catalog();assert sourcecatalog==load(CATALOG);saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');out.mkdir(exist_ok=False,parents=True);rows=[];start=time.perf_counter()
    for c in load(path)['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short object batch deadline')
        artifacts=[];reports=[]
        for reference in [True,False,False]:a,r=invoke(path,c,reference);artifacts.append(a);reports.append(r)
        ref,first,second=reports;checks=[]
        def check(name,value):checks.append(dict(check=name,passed=bool(value)))
        check('structured-results',all(r is not None for r in reports))
        if all(r is not None for r in reports):
            check('formal-bounds',all(r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())and not r['full_trace_enabled']and not r['game_started']for r in reports))
            if c.get('kind')=='process-rejection':check('explicit-rejection',all(c['error']in r.get('first_unsupported_entry','')for r in reports))
            elif real:
                def diagnostic(r):return r.get('first_unsupported_entry','').replace('\\','/')
                # Stock loadfile uses physical file names; compare source line+body.
                def suffix(r):return ':'.join(diagnostic(r).split(':')[-2:])
                check('same-first-unsupported',all(suffix(r)==suffix(ref)for r in reports));check('real-initialization-completed',all(a['returncode']==0 for a in artifacts))
            elif not all('semantic'in r for r in reports):check('functional-completed',False)
            else:
                check('stock-lua-ordinary-results',m.compact.b.draws.ordinary(ref)==m.compact.b.draws.ordinary(first)==m.compact.b.draws.ordinary(second))
                check('repeat-candidate',first['steps']==second['steps']and first['semantic']==second['semantic'])
                if c.get('expected_values')is not None:check('expected-values',first['steps'][-1].get('values')==c['expected_values'])
                if c.get('expected_draws')is not None:
                    actual=[(bytes.fromhex(s['draws'][0]['text_hex']).decode('utf-8'),s['draws'][0]['x'],s['draws'][0]['y'])for s in first['steps']if 'draws'in s]
                    expected=[tuple(d)for d in c['expected_draws']]
                    check('expected-private-draws',len(actual)==len(expected)and all(a[:len(e)]==e for a,e in zip(actual,expected)))
                if c.get('valid_status')is not None:check('precise-version-and-lifetime', [s['metadata']['versions_valid']for s in first['steps']if 'versions_valid'in s.get('metadata',{})]==c['valid_status'])
                if c['kind']=='gc':check('gc-not-pinned',first['metadata'][1]['model_objects']['live']==0 and first['metadata'][1]['model_objects']['created']==first['metadata'][1]['model_objects']['retired']==2)
                if c['kind']=='churn':check('bounded-live-objects',first['metadata'][1]['model_objects']['live']==3 and first['metadata'][1]['model_objects']['created']==4099 and first['metadata'][1]['model_objects']['retired']==4096 and first['metadata'][1]['model_objects']['peak']<128)
                if path==MODULES:
                    if c['kind']=='rollback':check('original-module-store-and-draw-rollback',first['semantic']['stores']==c['stores']and bytes.fromhex(first['steps'][1]['draws'][0]['text_hex'])==b'module=2|zh')
                    if c['kind']=='authority':check('original-module-host-commits-once',first['semantic']['world']['coins']==1 and len(first['semantic']['world']['effects'])==1)
                    if c['kind']=='cache-stress':check('original-module-cache-hits-no-recompile',first['modules']['states'][1]['compilations']==2 and first['modules']['states'][1]['searches']==2)
                    if c['id']=='closing-generation':check('original-module-audit-generations',first['modules']['states'][1]['compilations']==1 and first['modules']['states'][1]['generation']==4)
                check('projection-stays-closed',not first['automatic_projection_implemented']and not first['personal_draws_publishable'])
        row=dict(id=c['id'],kind=c['kind'],passed=all(t['passed']for t in checks),checks=checks,artifacts=artifacts,reports=reports);rows.append(row)
        print(json.dumps(dict(id=c['id'],passed=row['passed'],first_unsupported=(first or{}).get('first_unsupported_entry'),failed=[t['check']for t in checks if not t['passed']])),flush=True)
        if not row['passed']and not real:break
    result=dict(schema='model-object-results-1',cases=rows,passed=len(rows)==len(load(path)['cases'])and all(r['passed']for r in rows),seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,manifest_sha256=old.digest(path),driver_sha256=old.digest(Path(__file__)),binaries={p.relative_to(ROOT).as_posix():old.digest(p)for p in [EXE,REF]},resource_catalog_sha256=old.digest(CATALOG),protected_files_unchanged=before==m.protected(),save_files_unchanged=saves['files']==old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')['files'],game_started=False,real_initialization_attempt=real,authority_projection_passed=False)
    assert result['protected_files_unchanged']and result['save_files_unchanged']
    data=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8');p=out/'result.json.gz';p.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(p.read_bytes())==data
    print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows),seconds=result['seconds'],bytes=p.stat().st_size)),flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','modules','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL if a.phase=='real'else MODULES if a.phase=='modules'else MANIFEST,a.output.resolve(),a.phase=='real')['passed']else 1)
