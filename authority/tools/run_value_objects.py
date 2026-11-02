"""Bounded float value objects, frozen compatibility fragments and real entries."""
import argparse,copy,gzip,hashlib,json,math,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_mod_sdk as s
ROOT=s.ROOT;old=s.old;FOLDER=ROOT/'research/value_objects';MANIFEST=ROOT/'research/value_objects_v1.json';CURRENT=ROOT/'research/value_objects_v2.json';REAL=ROOT/'research/value_objects_real_v1.json';EXE=ROOT/'build-value-objects/Release/authority-values.exe';REF=EXE.with_name('authority-values-reference.exe')

def profile():
    lines=s.MAIN.read_bytes().splitlines(keepends=True)
    return dict(numeric_model='ieee754-binary32-finite',main_sha256=old.digest(s.MAIN),fragments=[dict(name=name,first=first,last=last,sha256=hashlib.sha256(b''.join(lines[first-1:last])).hexdigest())for name,first,last in [('constants',171,189),('color-vector',232,248)]])
def values(*items):
    return [dict(type='number',value=v)if isinstance(v,float)else s.o.m.values(v)[0]for v in items]
def freeze():
    code="""ValueMod=RegisterMod('Value Fixture',1)
local cfg=require('json').decode(ValueMod:LoadData())
V=Vector(cfg.x,42);C=Color(1,0.5,0.25);K=KColor(0.25,0.5,0.75,1)
local alias=V;local cached=V.LengthSquared
ValueMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
ValueMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;alias.X=cfg.x;C.A=0.5;K.Alpha=0.25;ValueMod:SaveData(require('json').encode(cfg))end
 Isaac.RenderText(cfg.language..'|x='..string.format('%.0f',alias.X)..'|coins='..Isaac.GetPlayer(0):GetNumCoins(),cfg.x,0)
 if Input.IsButtonTriggered('fail')then alias.Y=999;C.RO=2;K.Red=0.9;ValueMod:SaveData('uncommitted');Isaac.RenderText('unpublished',0,0);error('value-injected')end
end)
ValueMod:AddCallback(3,function()Isaac.RenderText(string.format('%.0f',alias.X),0,0)end)
ValueMod:AddCallback(4,function()Isaac.RenderText(string.format('%.0f',cached(alias)),0,0)end)
ValueMod:AddCallback(5,function()Isaac.RenderText(string.format('%.1f',C.A),0,0)end)
"""
    s.o.freeze_file(FOLDER/'main.lua',code.encode('utf-8'))
    ephemeral="local m=RegisterMod('Ephemeral Value',1)\nm:AddCallback(2,function()local v=Vector(7,8);Isaac.RenderText(string.format('%.0f',v.X),0,0)end)\n"
    s.o.freeze_file(FOLDER/'ephemeral.lua',ephemeral.encode('utf-8'))
    root=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/value-fixture',sha256={p.name:old.digest(p)for p in FOLDER.glob('*.lua')})
    common=dict(source=(FOLDER/'main.lua').relative_to(ROOT).as_posix(),source_sha256=old.digest(FOLDER/'main.lua'),modules=dict(entry=0,roots=[root]),objects=s.o.load(s.o.MANIFEST)['cases'][0]['objects'],mod_sdk=s.profile([root],[{'mods/value-fixture':old.store(1,17,'en')},{'mods/value-fixture':old.store(2,137,'zh')}],[0]),value_objects=profile(),stores=['{}','{}'])
    cases=[]
    def case(name,steps,expected=None,kind='functional',**kw):
        c=copy.deepcopy(common);c.update(id=name,steps=steps,kind=kind,**kw)
        if expected is not None:c['expected_values']=values(*expected)
        cases.append(c);return c
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(**kw):return dict(op='dispatch',event=2,phase='presentation',**kw)
    def cap(event=3):return dict(op='capture_reads',event=event,phase='presentation')
    def status(id):return dict(op='consumer_status',consumer=id)
    case('constructors-fields-and-constants',[ev("return type(V),V.X,V.Y,C.R,C.G,C.A,C.RO,K.Red,K.Alpha,Vector.Zero.X,Vector.One.Y,Color.Default.A,KColor.Transparent.Alpha")],['userdata',137.,42.,1.,0.5,1.,0.,0.25,1.,0.,1.,1.,0.])
    case('frozen-color-default-wrapper',[ev("local a=Color(1,2,3);local b=Color(1,2,3,false,false,nil,false);return a.A,a.RO,a.GO,a.BO,b.A,b.RO,b.GO,b.BO")],[1.,0.,0.,0.,1.,0.,0.,0.])
    case('vector-add-sub-neg-div',[ev("local a=Vector(3,4);local b=Vector(1,2);local x=a+b;local y=a-b;local z=-a;local q=a/2;return x.X,x.Y,y.X,y.Y,z.X,z.Y,q.X,q.Y")],[4.,6.,2.,2.,-3.,-4.,1.5,2.])
    case('frozen-vector-multiply',[ev("local a=Vector(3,4);local b=a*2;local c=2*a;local d=a*Vector(2,3);return b.X,b.Y,c.X,c.Y,d.X,d.Y")],[6.,8.,6.,8.,6.,12.])
    case('vector-query-and-cached-receiver',[ev("local a=Vector(3,4);local b=Vector(5,12);local f=a.LengthSquared;return a:Length(),f(a),f(b),a:Dot(Vector(-4,3)),a:DistanceSquared(Vector(0,0))")],[5.,25.,169.,0.,25.])
    case('cached-field-get-and-set',[ev("local read=getmetatable(V).__index;local write=getmetatable(V).__newindex;local other=Vector(8,9);write(other,'X',11);return read(V,'X'),read(other,'X'),other.Y")],[137.,11.,9.])
    case('aliases-and-closure',[ev("local alias={position=V};local function get()return alias.position.X end;alias.position.X=19;return get(),V.X")],[19.,19.])
    case('private-context-values',[dict(dispatch(),role='host'),dispatch(input={'move':True}),dict(dispatch(),role='host')],frames=[['en|x=17|coins=0'],['zh|x=147|coins=0'],['en|x=17|coins=0']])
    case('authority-result-personal-position',[dict(dispatch(),event=1,role='host',phase='authority'),dispatch(input={'move':True})],frames=[['zh|x=147|coins=1']],expected_coins=1)
    case('value-save-reload',[dispatch(input={'move':True}),dict(op='reload_saved'),dispatch()],frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']])
    case('same-field-aba',[cap(),ev("V.X=12;V.X=137"),status(3)],valid_status=[False])
    case('other-field-does-not-invalidate',[cap(),ev("V.Y=99;C.A=0.3"),status(3)],valid_status=[True])
    case('cached-method-all-read-fields',[cap(4),ev("V.Y=99"),status(4)],valid_status=[False])
    case('color-fields-are-distinct',[cap(5),ev("C.R=0.8;C.RO=0.2"),status(5),ev("C.A=0.4;C.A=1"),status(5)],valid_status=[True,False])
    case('rollback-private-values-save-draw',[dispatch(input={'move':True}),dict(dispatch(input={'fail':True}),expect_error='value-injected'),dispatch(),ev("return V.X,V.Y,C.A,C.RO,K.Red,K.Alpha")],[147.,42.,0.5,0.,0.25,0.25],frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']])
    case('gc-churn',[ev("for i=1,4096 do local v=Vector(i,-i);local c=KColor(0,0,0,1);if i%32==0 then collectgarbage('collect')end end;collectgarbage('collect')"),dict(op='value_status')],churn_created=8192)
    case('gc-shadow-cleanup',[ev("local mt=getmetatable(V);mt.__gc=nil;for i=1,2048 do local v=Vector(i,-i);if i%32==0 then collectgarbage('collect')end end;collectgarbage('collect')"),dict(op='value_status')],churn_created=2048)
    c=case('ephemeral-lifetime',[dict(op='capture_reads',event=2,phase='presentation'),status(1),dict(op='gc'),status(1),dict(op='value_status')],valid_status=[True,False],final_live=12);c['source']=(FOLDER/'ephemeral.lua').relative_to(ROOT).as_posix();c['source_sha256']=old.digest(FOLDER/'ephemeral.lua');c['modules']['roots'][0]['sha256']['main.lua']=old.digest(FOLDER/'ephemeral.lua')
    # FrozenModules requires the actual main.lua file for an entry, so this case
    # uses a distinct small fixture root rather than changing the original main.
    ep=FOLDER/'ephemeral/main.lua';s.o.freeze_file(ep,ephemeral.encode('utf-8'));c['source']=ep.relative_to(ROOT).as_posix();c['source_sha256']=old.digest(ep);c['modules']['roots'][0]['root']=ep.parent.relative_to(ROOT).as_posix();c['modules']['roots'][0]['sha256']={'main.lua':old.digest(ep)}
    oracle_samples=[(0.1,-0.0),(1+2**-24,1+2**-23),(16777217.,-16777217.),(2**-149,2**-126),(3.4e38,-3.4e38),(1/3,34/255)]
    for i,(x,y)in enumerate(oracle_samples):
        code="local v=Vector("+repr(x)+","+repr(y)+");return string.pack('<ff',v.X,v.Y)"
        case('binary32-oracle-'+str(i),[ev(code)],[struct.pack('<ff',x,y)],oracle_input=[x,y])
    for name,code,error in [
      ('bad-constructor',"Vector()",'Value constructor signature unsupported'),
      ('bad-number',"Vector('1',2)",'Value component must be a number'),
      ('nonfinite',"V.X=0/0",'Nonfinite value component unsupported'),
      ('overflow',"V.X=3.5e38",'Value component outside binary32 range'),
      ('zero-divisor',"local a=V/0",'Zero value divisor unsupported'),
      ('unknown-field',"V.Z=3",'Unknown value field write'),
      ('unknown-method',"V:Rotated(90)",'Vector operation not implemented'),
      ('color-method',"C:SetColorize(1,1,1,1)",'Color operation not implemented'),
      ('wrong-cached-receiver',"V.LengthSquared(C)",'Foreign or retired value receiver'),
      ('wrong-cached-getter',"getmetatable(V).__index(K,'Red')",'Foreign or retired value receiver'),
      ('wrong-cached-setter',"getmetatable(V).__newindex(K,'Red',1)",'Foreign or retired value receiver'),
      ('unverified-equality',"return V==Vector(V.X,V.Y)",'Value equality contract not verified'),
      ('unverified-tostring',"return tostring(V)",'Value tostring contract not verified')]:
        case('reject-'+name,[ev(code,expect_error=error),dispatch()],frames=[['zh|x=137|coins=0']])
    case('reject-live-cap',[ev("held={};for i=1,1025 do held[i]=Vector(i,0)end")],kind='process-rejection',error='Live value-object capacity exceeded')
    c=case('reject-fragment-hash',[],kind='process-rejection',error='Frozen value fragment hash mismatch');c['value_objects']['fragments'][0]['sha256']='0'*64
    s.o.freeze_json(MANIFEST,dict(schema='value-object-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    mixed="""local m=RegisterMod('Mixed Userdata GC',1)
local anchor=Vector(17,42);local mt=getmetatable(anchor);local original=mt.__gc
m:AddCallback(2,function()
 mt.__gc=nil
 for i=1,128 do
  local temporary=Vector(i,-i);temporary=nil;collectgarbage('collect')
  local bits=BitSet128(i,0);local sprite=Sprite();sprite:Load('gfx/ui/modconfig/menu.anm2',false)
  assert(bits.l==i and sprite:GetLayerCount()==10)
 end
 mt.__gc=original;collectgarbage('collect');assert(anchor.X==17)
 Isaac.RenderText('mixed-ok',0,0)
end)
"""
    mixed_path=FOLDER/'mixed/main.lua';s.o.freeze_file(mixed_path,mixed.encode('utf-8'));extra=copy.deepcopy(common);extra.update(id='mixed-userdata-gc-shadow',kind='functional',source=mixed_path.relative_to(ROOT).as_posix(),source_sha256=old.digest(mixed_path),steps=[dict(op='capture_reads',event=2,phase='presentation'),dict(op='value_status')],frames=[['mixed-ok']],final_live=13)
    extra['modules']['roots'][0].update(root=mixed_path.parent.relative_to(ROOT).as_posix(),sha256={'main.lua':old.digest(mixed_path)})
    s.o.freeze_json(CURRENT,dict(schema='value-object-contracts-2',work_limit=10000000,timeout_seconds=5,cases=copy.deepcopy(cases)+[extra]))
    real=copy.deepcopy(s.o.load(s.REAL_CURRENT))
    for c in real['cases']:c['value_objects']=profile()
    real['schema']='value-objects-real-entry-1';s.o.freeze_json(REAL,real)
    print(json.dumps(dict(frozen=True,cases=len(cases),real_entries=3,game_resources_copied=0)))

def invoke(path,c,reference=False):
    start=time.perf_counter()
    try:p=subprocess.run([str(REF if reference else EXE),'--value-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Value output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r

def run(path,out,real=False):
    s.EXE=EXE;s.REF=REF;s.invoke=invoke;r=s.run(path,out,real);cases={c['id']:c for c in s.o.load(path)['cases']}
    for row in r['cases']:
        c=cases[row['id']];report=row['reports'][1]
        if report and 'semantic'in report:
            m=report['metadata'][1]['value_objects'];checks=row['checks']
            if c.get('churn_created'):checks.append(dict(check='bounded-live-records-after-churn',passed=m['live']==15 and m['created']==15+c['churn_created']and m['retired']==c['churn_created']and m['peak']<128))
            if c.get('final_live')is not None:checks.append(dict(check='weak-lifetime-records-retired',passed=m['live']==c['final_live']))
            checks.append(dict(check='not-permanently-pinned',passed=m['permanent_instance_references']==0 and not m['native_engine_equivalence_verified']))
        row['passed']=all(t['passed']for t in row['checks'])
    r['passed']=len(r['cases'])==len(cases)and all(c['passed']for c in r['cases']);r['value_driver_sha256']=old.digest(Path(__file__));r['schema']='value-object-results-1'
    data=(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8');p=out/'result.json.gz';p.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(p.read_bytes())==data
    print(json.dumps(dict(value_finished=True,passed=r['passed'],cases=len(r['cases']),failures=[dict(id=c['id'],checks=[t['check']for t in c['checks']if not t['passed']])for c in r['cases']if not c['passed']])),flush=True);return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL if a.phase=='real'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
