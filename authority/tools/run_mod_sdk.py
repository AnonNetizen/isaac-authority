"""Bounded multi-mod identity, private data, callback and frozen enum gates."""
import argparse,copy,gzip,hashlib,json,re,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_model_objects as o
ROOT=o.ROOT;old=o.old;FOLDER=ROOT/'research/mod_sdk';MANIFEST=ROOT/'research/mod_sdk_v1.json';CURRENT=ROOT/'research/mod_sdk_v3.json';REAL=ROOT/'research/mod_sdk_real_v1.json';REAL_CURRENT=ROOT/'research/mod_sdk_real_v2.json';EXE=ROOT/'build-mod-sdk/Release/authority-sdk.exe';REF=EXE.with_name('authority-sdk-reference.exe')
MAIN=ROOT/'research/slice3_ui_inputs/resources/scripts/main.lua';ENUMS=MAIN.with_name('enums.lua')

def profile(roots,stores,order):
    fragment=b''.join(MAIN.read_bytes().splitlines(keepends=True)[:28])
    return dict(slot=1,stores=stores,load_order=order,main=dict(path=MAIN.relative_to(ROOT).as_posix(),sha256=old.digest(MAIN)),registration_sha256=hashlib.sha256(fragment).hexdigest(),enums=dict(path=ENUMS.relative_to(ROOT).as_posix(),sha256=old.digest(ENUMS)))

def freeze():
    files={
      'a/main.lua':"""A=RegisterMod('Shared Name',1)
AHelper=RegisterMod('A Helper',1)
function RegisterViaA(name)return RegisterMod(name,1)end
SDK_counter=0
SharedCallback=function(self)Isaac.RenderText(self==A and 'shared-a' or 'shared-b',0,0)end
A:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
A:AddCallback(2,function()
 SDK_counter=SDK_counter+1
 if Input.IsButtonTriggered('save')then A:SaveData('saved-a')end
 Isaac.RenderText('A:'..A:LoadData()..'|n='..SDK_counter,10,0)
end)
A:AddCallback(20,SharedCallback)
A:AddPriorityCallback(21,2,function()Isaac.RenderText('priority-a',0,0)end)
A:AddPriorityCallback(23,-1,function()Isaac.RenderText('stop-false',0,0);return false end)
A:AddCallback(24,function()
 A:SaveData('bad-a');B:SaveData('bad-b');SDK_counter=99
 Isaac.GetPlayer(0):GetNumCoins();Isaac.RenderText('unpublished',0,0);error('sdk-injected')
end)
A:AddCallback(25,function()Isaac.RenderText(tostring(A:HasData()),0,0)end)
A:AddCallback(26,function()Isaac.RenderText(A:LoadData(),0,0)end)
AHelper:AddPriorityCallback(21,-1,function()Isaac.RenderText('priority-helper',0,0)end)
""",
      'b/main.lua':"""B=RegisterMod('Shared Name',1)
BViaHelper=RegisterViaA('Via A Helper')
B:AddCallback(2,function()Isaac.RenderText('B:'..B:LoadData(),110,0)end)
B:AddCallback(20,SharedCallback)
B:AddPriorityCallback(21,0,function()Isaac.RenderText('priority-b',0,0)end)
B:AddCallback(22,function(_,arg)Isaac.RenderText('filtered:'..arg,0,0)end,7)
B:AddCallback(23,function()Isaac.RenderText('must-not-run',0,0)end)
B:AddCallback(30,function()BFromCallback=RegisterViaA('Callback via A')end)
"""}
    for name,code in files.items():o.freeze_file(FOLDER/name,code.encode('utf-8'))
    roots=[dict(root=(FOLDER/n).relative_to(ROOT).as_posix(),display='mods/sdk-'+n,sha256={'main.lua':old.digest(FOLDER/n/'main.lua')})for n in ['a','b']]
    common=dict(source=(FOLDER/'a/main.lua').relative_to(ROOT).as_posix(),source_sha256=old.digest(FOLDER/'a/main.lua'),modules=dict(entry=0,roots=roots),objects=o.load(o.MANIFEST)['cases'][0]['objects'],mod_sdk=profile(roots,[{'mods/sdk-a':'ha','mods/sdk-b':'hb'},{'mods/sdk-a':'pa','mods/sdk-b':'pb'}],[0,1]),stores=['{}','{}'])
    cases=[]
    def case(name,steps,expected=None,kind='functional',**extra):
        c=copy.deepcopy(common);c.update(id=name,steps=steps,kind=kind,**extra)
        if expected is not None:c['expected_values']=o.m.values(*expected)
        cases.append(c);return c
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(event=2,role='personal',phase='presentation',**kw):return dict(op='dispatch',event=event,role=role,phase=phase,**kw)
    def cap(event=2,**kw):return dict(op='capture_reads',event=event,phase='presentation',**kw)
    def status(n):return dict(op='consumer_status',consumer=n)
    case('registered-tables-and-names',[ev("return A.Name,B.Name,rawequal(A,B),rawequal(A.LoadData,B.LoadData),A:LoadData(),B:LoadData()" )],['Shared Name','Shared Name',False,False,'pa','pb'])
    case('same-folder-helper-shares-data',[ev("AHelper:SaveData('from-helper');return A:LoadData(),AHelper:LoadData(),B:LoadData()")],['from-helper','from-helper','pb'])
    case('foreign-helper-keeps-origin',[ev("BViaHelper:SaveData('from-b-helper');return A:LoadData(),B:LoadData(),BViaHelper:LoadData()"),dict(op='sdk_status')],expected_roots=['mods/sdk-a','mods/sdk-a','mods/sdk-b','mods/sdk-b'])
    case('name-mutation-keeps-origin',[ev("A.Name=B.Name;A:SaveData('renamed');return A:LoadData(),B:LoadData()")],['renamed','pb'])
    case('original-isaac-register-void',[ev("Manual={Name='Manual'};local result=Isaac.RegisterMod(Manual,'Manual',1);Isaac.SaveModData(Manual,'manual');return result,A:LoadData(),Isaac.LoadModData(Manual)")],[None,'manual','manual'])
    case('per-player-stores',[dispatch(role='host'),dispatch(input={'save':True}),dispatch(role='host')],frames=[['A:ha|n=1','B:hb'],['A:saved-a|n=1','B:pb'],['A:ha|n=2','B:hb']])
    case('save-and-reload',[dispatch(input={'save':True}),dict(op='reload_saved'),dispatch()],frames=[['A:saved-a|n=1','B:pb'],['A:saved-a|n=1','B:pb']])
    case('empty-versus-absent',[ev("A:RemoveData();local a,b=A:HasData(),A:LoadData();A:SaveData('');local c,d=A:HasData(),A:LoadData();A:RemoveData();return a,b,c,d,A:HasData(),A:LoadData()")],[False,'',True,'',False,''])
    case('raw-bytes-and-cached-method',[ev("local save,read=A.SaveData,A.LoadData;save(B,string.char(0,255));return read(A),read(B)")],['pa',b'\0\xff'])
    case('callback-removal-is-owned',[ev("A:RemoveCallback(20,SharedCallback)"),dispatch(20)],frames=[['shared-b']])
    case('callback-priorities',[dispatch(21)],frames=[['priority-helper','priority-b','priority-a']])
    case('callback-false-stops',[dispatch(23)],frames=[['stop-false']])
    case('callback-filter-equal',[dispatch(22,filter=7,arguments=['yes'])],frames=[['filtered:yes']])
    case('callback-filter-mismatch',[dispatch(22,filter=8,arguments=['no'])],frames=[[]])
    case('callback-filter-nil-wildcard',[dispatch(22,arguments=['nil'])],frames=[['filtered:nil']])
    case('callback-filter-minus-one',[dispatch(22,filter=-1,arguments=['wild'])],frames=[['filtered:wild']])
    case('callback-helper-root-inheritance',[dispatch(30),dict(op='sdk_status')],expected_roots=['mods/sdk-a','mods/sdk-a','mods/sdk-b','mods/sdk-b','mods/sdk-b'])
    case('selected-store-precision',[cap(26),ev("B:SaveData('other')"),status(8),ev("A:SaveData('changed')"),status(8)],valid_status=[True,False])
    case('selected-store-aba',[cap(26),ev("A:SaveData('changed');A:SaveData('pa')"),status(8)],valid_status=[False])
    case('presence-precision-and-aba',[cap(25),ev("A:SaveData('content-only')"),status(7),ev("A:RemoveData();A:SaveData('pa')"),status(7)],valid_status=[True,False])
    case('rollback-all-mods-and-private-state',[dispatch(),dict(dispatch(24),expect_error='sdk-injected'),dispatch()],frames=[['A:pa|n=1','B:pb'],['A:pa|n=2','B:pb']],expected_stores=[{'mods/sdk-a':'ha','mods/sdk-b':'hb'},{'mods/sdk-a':'pa','mods/sdk-b':'pb'}])
    case('authority-write-only',[dispatch(1,role='host',phase='authority'),dict(dispatch(1,phase='authority'),expect_error='Personal context cannot execute authority phase'),dispatch()],frames=[['A:pa|n=1','B:pb']],expected_coins=1)
    case('actual-enum-values',[ev("return Keyboard.KEY_L,Keyboard.KEY_F2,ModCallbacks.MC_POST_RENDER,CallbackPriority.EARLY,RoomDescriptor.DISPLAY_ALL,ItemConfig.CHARGE_SPECIAL,TearFlags.TEAR_SPECTRAL.l,TearFlags.TEAR_CREEP_TRAIL.l,TearFlags.TEAR_PUNCH.h")],[76,291,2,-100,5,2,1,-9223372036854775808,1])
    namespace=re.findall(r'^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{',ENUMS.read_text(encoding='utf-8'),re.M)+['ItemConfig','RoomDescriptor']
    names='{'+','.join(json.dumps(n)for n in sorted(set(namespace)))+'}'
    dump="local rows={};for _,name in ipairs("+names+")do for k,v in pairs(_G[name])do local t=type(v);if t=='userdata'then rows[#rows+1]=name..'.'..k..'='..v.l..','..v.h elseif t=='number'then rows[#rows+1]=name..'.'..k..'='..tostring(v)else error('unknown enum type '..t)end end end;table.sort(rows);return table.concat(rows,'\\n')"
    case('full-frozen-enum-bytes',[ev(dump)],enum_dump=True)
    case('personal-enum-table-independent',[ev("Keyboard.KEY_L=999"),ev("return Keyboard.KEY_L"),dict(ev("return Keyboard.KEY_L"),role='host')],enum_values=[999,76])
    for name,code,error in [
      ('forged-receiver',"local fake={Name=A.Name,LoadData=A.LoadData};return fake:LoadData()",'Unregistered mod receiver'),
      ('duplicate-table',"Isaac.RegisterMod(A,'again',1)",'Mod table already registered'),
      ('api-version',"RegisterMod('Bad',2)",'Mod API version unsupported'),
      ('unknown-bit-field',"return TearFlags.TEAR_NORMAL.Unknown",'BitSet128 operation contract unsupported'),
      ('bit-field-write',"TearFlags.TEAR_NORMAL.l=4",'BitSet128 writes not implemented'),
      ('unknown-namespace',"return ItemConfig.GetCollectibles",'Enum namespace operation not implemented')]:
        case('reject-'+name,[ev(code,expect_error=error),dispatch()],frames=[['A:pa|n=1','B:pb']])
    c=case('reject-sdk-source-hash',[],kind='process-rejection',error='Frozen SDK source hash mismatch');c['mod_sdk']['enums']['sha256']='0'*64
    c=case('reject-sdk-fragment-hash',[],kind='process-rejection',error='Frozen registration fragment hash mismatch');c['mod_sdk']['registration_sha256']='0'*64
    c=case('reject-unregistered-seed',[],kind='process-rejection',error='SDK seed uses unregistered mod root');c['mod_sdk']['stores'][0]['mods/unknown']='x'
    o.freeze_json(MANIFEST,dict(schema='mod-sdk-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    corrected=copy.deepcopy(cases);corrected[0]['expected_values'][3]['value']=True
    o.freeze_json(ROOT/'research/mod_sdk_v2.json',dict(schema='mod-sdk-contracts-2',work_limit=10000000,timeout_seconds=5,contract_correction='Unmodified Lua and unchanged registration wrapper reuse the same method closure; mod table identity remains distinct.',cases=corrected))
    portable=copy.deepcopy(corrected);portable[0]['id']='registered-tables-and-cached-receivers';portable[0]['steps']=[ev("local f=A.LoadData;return A.Name,B.Name,rawequal(A,B),type(f),f(A),f(B)")];portable[0]['expected_values']=o.m.values('Shared Name','Shared Name',False,'function','pa','pb')
    renamed=copy.deepcopy(portable[3]);renamed['id']='actual-name-mutation-keeps-origin';renamed['steps']=[ev("A.Name='Spoofed Name';A:SaveData('renamed');return A.Name,A:LoadData(),B:LoadData()")];renamed['expected_values']=o.m.values('Spoofed Name','renamed','pb');portable.append(renamed)
    o.freeze_json(CURRENT,dict(schema='mod-sdk-contracts-3',work_limit=10000000,timeout_seconds=5,contract_correction='Lua 5.3 section 3.4.4 permits closure identity to vary with caching. Keep original diagnostics; test distinct mod tables and cached methods with actual receivers, plus an actual Name change.',cases=portable))
    real=copy.deepcopy(o.load(o.REAL))
    for c in real['cases']:
        rr=c['modules']['roots'];c['mod_sdk']=profile(rr,[{root['display']:'{}'for root in rr}for _ in range(2)],list(range(len(rr))))
    real['schema']='mod-sdk-unchanged-real-entry-1';o.freeze_json(REAL,real)
    actual_flags={name:True for name in ['REPENTANCE','REPENTANCE_PLUS']if re.search(r'^'+name+r'\s*=\s*true\s*$',MAIN.read_text(encoding='utf-8'),re.M)}
    assert actual_flags=={'REPENTANCE':True,'REPENTANCE_PLUS':True}
    complete=copy.deepcopy(real);complete['schema']='mod-sdk-unchanged-real-entry-2';complete['flag_provenance']='Literal assignments in the hash-pinned J460 engine main.lua; not inferred from current API docs.'
    for c in complete['cases']:c['objects']['flags'].update(actual_flags)
    o.freeze_json(REAL_CURRENT,complete)
    print(json.dumps(dict(frozen=True,cases=len(cases),real_entries=3,enums_sha256=old.digest(ENUMS),source_copies=0)))

def invoke(path,c,reference=False):
    start=time.perf_counter()
    try:p=subprocess.run([str(REF if reference else EXE),'--sdk-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('SDK output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r

def run(path,out,real=False):
    o.EXE=EXE;o.REF=REF;o.invoke=invoke
    result=o.run(path,out,real)
    byid={c['id']:c for c in o.load(path)['cases']}
    for row in result['cases']:
        c=byid[row['id']];r=row['reports'][1];checks=row['checks']
        def check(name,value):checks.append(dict(check=name,passed=bool(value)))
        if r is not None and 'semantic'in r:
            if 'frames'in c:check('all-frame-contents',[[bytes.fromhex(d['text_hex']).decode('utf-8')for d in s['draws']]for s in r['steps']if 'draws'in s]==c['frames'])
            if 'expected_roots'in c:check('trusted-root-context', [m['root']for m in r['steps'][-1]['metadata']['registrations']]==c['expected_roots'])
            if 'expected_stores'in c:
                encoded=[{root:dict(present=value is not None,data_hex=value.encode('utf-8').hex()if value is not None else None)for root,value in role.items()}for role in c['expected_stores']]
                check('all-private-stores-restored',r['semantic']['mod_stores']==encoded)
            if 'expected_coins'in c:check('host-world-result',r['semantic']['world']['coins']==c['expected_coins'])
            if 'enum_values'in c:check('per-state-enum-values',[r['steps'][i]['values'][0]['value']for i in [1,2]]==c['enum_values'])
            if c.get('enum_dump'):check('nonempty-full-enum-comparison',len(r['steps'][0]['values'][0]['hex'])>50000)
        row['passed']=all(x['passed']for x in checks)
    result['passed']=len(result['cases'])==len(byid)and all(c['passed']for c in result['cases']);result['schema']='mod-sdk-results-1';result['sdk_driver_sha256']=old.digest(Path(__file__))
    data=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8');p=out/'result.json.gz';p.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(p.read_bytes())==data
    print(json.dumps(dict(sdk_finished=True,passed=result['passed'],cases=len(result['cases']),failures=[dict(id=c['id'],checks=[x['check']for x in c['checks']if not x['passed']])for c in result['cases']if not c['passed']])),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL_CURRENT if a.phase=='real'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
