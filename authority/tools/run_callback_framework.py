"""Execute the exact J460 callback implementation in bounded private contexts."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_texture_state as t
ROOT=t.ROOT;old=t.old;FOLDER=ROOT/'research/callback_framework';PROFILE=FOLDER/'profile.json';MANIFEST=ROOT/'research/callback_framework_v1.json';CORRECTED=ROOT/'research/callback_framework_v2.json';CURRENT=ROOT/'research/callback_framework_v3.json';REAL=ROOT/'research/callback_framework_real_v1.json'
EXE=ROOT/'build-callback-framework/Release/authority-callbacks.exe';REF=EXE.with_name('authority-callbacks-reference.exe')

def freeze():
    main=t.s.e.v.s.MAIN;lines=main.read_bytes().splitlines(keepends=True)
    profile=dict(schema='frozen-j460-callbacks-1',main_path=main.relative_to(ROOT).as_posix(),main_sha256=old.digest(main),first=41,last=163,fragment_sha256=hashlib.sha256(b''.join(lines[40:163])).hexdigest(),source_unmodified=True,reference='https://wofsauge.github.io/IsaacDocs/rep/Isaac.html#runcallback',native_engine_equivalence_verified=False)
    t.s.e.v.s.o.freeze_json(PROFILE,profile)
    code="""CallbackMod=RegisterMod('Callback Framework Fixture',1)
local cfg=require('json').decode(CallbackMod:LoadData())
local private=0
Tex=Sprite();Tex:Load('gfx/ui/modconfig/menu.anm2',false);Tex:SetFrame('Cursor',4)
CallbackMod:AddCallback('fixture.reward',function()Isaac.GetPlayer(0):AddCoins(1)end)
CallbackMod:AddCallback('fixture.ui',function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;private=private+1;CallbackMod:SaveData(require('json').encode(cfg))end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|private='..private,cfg.x,0)
 if Input.IsButtonTriggered('fail')then CallbackMod:AddCallback('transient',function()return 999 end);CallbackMod:SaveData('not committed');error('callback-injected')end
end)
"""
    source=FOLDER/'main.lua';t.s.e.v.s.o.freeze_file(source,code.encode());rr=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/callback-framework-fixture',sha256={'main.lua':old.digest(source)})
    base=copy.deepcopy(t.s.e.v.s.o.load(t.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k in ['objects','value_objects','engine_services','animation_profile','graphics_profile','stores']}
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=old.digest(source),modules=dict(entry=0,roots=[rr]),mod_sdk=t.s.e.v.s.profile([rr],[{rr['display']:old.store(1,17,'en')},{rr['display']:old.store(2,137,'zh')}],[0]),callback_contract=dict(path=PROFILE.relative_to(ROOT).as_posix(),sha256=old.digest(PROFILE)))
    cases=[]
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(event='fixture.ui',**kw):return dict(op='dispatch',event=event,phase='presentation',**kw)
    def case(id,steps,values=None,kind='functional',**kw):
        c=copy.deepcopy(base);c.update(id=id,steps=steps,kind=kind,**kw)
        if values is not None:c['expected_values']=t.s.e.v.values(*values)
        cases.append(c);return c
    case('string-id-registration',[ev("CallbackMod:AddCallback('EIDCallbacks.SEARCH_NAME_CONVERSION',function(_,s)return 'found:'..s end);return Isaac.RunCallback('EIDCallbacks.SEARCH_NAME_CONVERSION','foo')")],['found:foo'])
    case('numeric-and-string-identities',[ev("CallbackMod:AddCallback(123,function()return 'number'end);CallbackMod:AddCallback('123',function()return 'string'end);return Isaac.RunCallback(123),Isaac.RunCallback('123')")],['number','string'])
    case('binary-string-event',[ev("local k='evt'..string.char(0,255);CallbackMod:AddCallback(k,function()return 'binary'end);return Isaac.RunCallback(k),#Isaac.GetCallbacks(k)")],['binary',1])
    case('priority-stable-order',[ev("local out={};local function add(p,v)CallbackMod:AddPriorityCallback('p',p,function()out[#out+1]=v end)end;add(10,'late');add(-2,'first');add(10,'late2');Isaac.RunCallback('p');return table.concat(out,'|')")],['first|late|late2'])
    case('fractional-priority',[ev("local out={};CallbackMod:AddPriorityCallback('p',0.5,function()out[#out+1]='half'end);CallbackMod:AddPriorityCallback('p',0.25,function()out[#out+1]='quarter'end);Isaac.RunCallback('p');return table.concat(out,'|')")],['quarter|half'])
    case('false-stops-chain',[ev("local n=0;CallbackMod:AddCallback('s',function()n=n+1;return false end);CallbackMod:AddCallback('s',function()n=n+100 end);local r=Isaac.RunCallback('s');return r,n")],[False,1])
    case('nil-continues-chain',[ev("CallbackMod:AddCallback('s',function()return nil end);CallbackMod:AddCallback('s',function()return 7 end);return Isaac.RunCallback('s')")],[7])
    case('filter-match',[ev("CallbackMod:AddCallback('f',function()return 'seven'end,7);return Isaac.RunCallbackWithParam('f',6)==nil,Isaac.RunCallbackWithParam('f',7)")],[True,'seven'])
    case('filter-false-is-wildcard',[ev("CallbackMod:AddCallback('f',function()return 5 end,7);return Isaac.RunCallbackWithParam('f',false)")],[5])
    case('filter-minus-one-wildcard',[ev("CallbackMod:AddCallback('f',function()return 5 end,-1);return Isaac.RunCallbackWithParam('f',9)")],[5])
    case('custom-parameter-matcher',[ev("CallbackMod:AddCallback('f',function()return 'matched'end,'A');getmetatable(Isaac.GetCallbacks('f')).__matchParams=function(a,b)return a..b=='BA'end;return Isaac.RunCallbackWithParam('f','B')")],['matched'])
    case('argument-nil-preserved',[ev("CallbackMod:AddCallback('a',function(_,...)return select('#',...)end);return Isaac.RunCallback('a',1,nil,3)")],[3])
    case('mod-self-identity',[ev("CallbackMod:AddCallback('s',function(m)return m==CallbackMod end);return Isaac.RunCallback('s')")],[True])
    case('cached-public-method',[ev("local add,run=Isaac.AddCallback,Isaac.RunCallback;add(CallbackMod,'c',function()return 9 end);return run('c')")],[9])
    case('nested-callback-result',[ev("CallbackMod:AddCallback('inner',function(_,n)return n+1 end);CallbackMod:AddCallback('outer',function(_,n)return Isaac.RunCallback('inner',n)*2 end);return Isaac.RunCallback('outer',3)")],[8])
    case('nested-arguments-restored',[ev("CallbackMod:AddCallback('i',function(_,x)return x*2 end);CallbackMod:AddCallback('o',function(_,a,b)local i=Isaac.RunCallback('i',a);return i..':'..b end);return Isaac.RunCallback('o',4,'tail')")],['8:tail'])
    case('remove-same-function-all-duplicates',[ev("local fn=function()return 1 end;CallbackMod:AddCallback('r',fn);CallbackMod:AddCallback('r',fn);CallbackMod:RemoveCallback('r',fn);return #Isaac.GetCallbacks('r'),Isaac.RunCallback('r')==nil")],[0,True])
    case('remove-shared-function-across-mods',[ev("local other=RegisterMod('Other',1);local fn=function()return 1 end;CallbackMod:AddCallback('r',fn);other:AddCallback('r',fn);CallbackMod:RemoveCallback('r',fn);return #Isaac.GetCallbacks('r')")],[0])
    case('remove-next-during-dispatch',[ev("local out={};local nextfn=function()out[#out+1]='next'end;CallbackMod:AddCallback('r',function()out[#out+1]='first';CallbackMod:RemoveCallback('r',nextfn)end);CallbackMod:AddCallback('r',nextfn);Isaac.RunCallback('r');return table.concat(out,'|')")],['first'])
    case('add-during-dispatch',[ev("local out={};local once=false;CallbackMod:AddCallback('a',function()out[#out+1]='first';if not once then once=true;CallbackMod:AddCallback('a',function()out[#out+1]='added'end)end end);Isaac.RunCallback('a');return table.concat(out,'|')")],['first|added'])
    case('get-list-reference-and-record-shape',[ev("local fn=function()end;CallbackMod:AddPriorityCallback('x',-3,fn,7);local a=Isaac.GetCallbacks('x');local b=Isaac.GetCallbacks('x');return a==b,a[1].Function==fn,a[1].Mod==CallbackMod,a[1].Priority,a[1].Param")],[True,True,True,-3,7])
    case('built-in-enabled-and-removed',[ev("local fn=function()end;CallbackMod:AddCallback(777,fn);local a=Isaac.GetBuiltInCallbackState(777);CallbackMod:RemoveCallback(777,fn);return a,Isaac.GetBuiltInCallbackState(777)")],[True,False])
    case('missing-list-is-not-registered',[ev("local a=Isaac.GetCallbacks('missing');local b=Isaac.GetCallbacks('missing');return a==b,#a,#b")],[False,0,0])
    case('original-unload-removes-mod-callbacks',[ev("_UnloadMod(CallbackMod);return #Isaac.GetCallbacks('fixture.ui'),#Isaac.GetCallbacks('fixture.reward')")],[0,0])
    case('private-debug-not-exposed',[ev("return debug==nil,io==nil,package==nil")],[True,True,True])
    case('independent-personal-configuration',[dict(dispatch(),role='host'),dispatch(input={'move':True}),dict(dispatch(),role='host')],frames=[['en|x=17|coins=0|private=0'],['zh|x=147|coins=0|private=1'],['en|x=17|coins=0|private=0']])
    case('authority-world-once',[dict(dispatch('fixture.reward'),role='host',phase='authority'),dispatch(input={'move':True})],frames=[['zh|x=147|coins=1|private=1']],expected_coins=1)
    case('saved-personal-configuration',[dispatch(input={'move':True}),dict(op='reload_saved'),dispatch()],frames=[['zh|x=147|coins=0|private=1'],['zh|x=147|coins=0|private=0']])
    case('rollback-registry-private-save-and-draw',[dispatch(input={'move':True}),dict(dispatch(input={'move':True,'fail':True}),expect_error='callback-injected'),dispatch(),ev("return #Isaac.GetCallbacks('transient'),CallbackMod:LoadData():find('147',1,true)~=nil")],[0,True],frames=[['zh|x=147|coins=0|private=1'],['zh|x=147|coins=0|private=1']])
    case('accepted-history-rebuild',[dispatch(input={'move':True}),dict(op='rebuild'),dispatch()],frames=[['zh|x=147|coins=0|private=1'],['zh|x=147|coins=0|private=1']])
    for id,step,error in [
      ('personal-world-write',dispatch('fixture.reward'),'Personal world mutation not submitted'),
      ('personal-authority',dict(dispatch('fixture.reward'),phase='authority'),'Personal context cannot execute authority phase'),
      ('consumer-capture',dict(op='capture_reads',event='fixture.ui',phase='presentation'),'Framework callback consumer capture not implemented'),
      ('boolean-event',ev("Isaac.RunCallback(true)"),'Callback event must be int32 or string'),
      ('table-event',ev("CallbackMod:AddCallback({},function()end)"),'Callback event must be int32 or string'),
      ('event-bytes',ev("Isaac.GetCallbacks(string.rep('a',4097),true)"),'Callback event byte capacity exceeded'),
      ('callback-count',ev("for i=1,256 do CallbackMod:AddCallback('many',function()end)end"),'Callback registry capacity exceeded'),
      ('registry-alias-overflow',ev("local a=Isaac.GetCallbacks('many',true);for i=1,257 do a[i]={}end"),'Callback registry capacity exceeded'),
      ('nested-forwarding',ev("CallbackMod:AddCallback('loop',function()return Isaac.RunCallback('loop')end);Isaac.RunCallback('loop')"),'Callback forwarding depth exceeded')]:
        step['expect_error']=error;case('reject-'+id,[step,dispatch()],kind='expected-rejection',frames=[['zh|x=137|coins=0|private=0']])
    case('reject-nested-hook-budget',[ev("Isaac.GetCallbacks('none');while true do end")],kind='process-rejection',error='Boundary work limit exceeded')
    case('reject-callback-profile-hash',[],kind='process-rejection',error='Callback profile hash mismatch')['callback_contract']['sha256']='0'*64
    t.s.e.v.s.o.freeze_json(MANIFEST,dict(schema='callback-framework-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(t.s.e.v.s.o.load(t.REAL))
    for c in real['cases']:c['callback_contract']=copy.deepcopy(base['callback_contract'])
    real['schema']='callback-framework-real-entry-1';t.s.e.v.s.o.freeze_json(REAL,real)
    print(json.dumps(dict(frozen=True,cases=len(cases),source_first=41,source_last=163)))

def freeze_corrected():
    data=copy.deepcopy(t.s.e.v.s.o.load(MANIFEST))
    c=next(c for c in data['cases']if c['id']=='private-debug-not-exposed');c['steps'][0]['code']='return debug==nil,io==nil,package.loaded.debug==nil'
    c=next(c for c in data['cases']if c['id']=='reject-personal-world-write');c['steps'][0]['expect_error']='World write requires authority phase'
    base=copy.deepcopy(next(c for c in data['cases']if c['id']=='reject-boolean-event'))
    for id,code,error in [('function-type',"CallbackMod:AddCallback('bad',3)",'function expected, got number'),('priority-type',"CallbackMod:AddPriorityCallback('bad','oops',function()end)",'number expected, got string')]:
        c=copy.deepcopy(base);c.update(id='reject-'+id);c['steps'][0]=dict(op='evaluate',code=code,expect_error=error);data['cases'].append(c)
    data['schema']='callback-framework-contracts-2';t.s.e.v.s.o.freeze_json(CORRECTED,data)
    c=copy.deepcopy(base);c.update(id='reject-callback-mod-ownership');c['steps'][0]=dict(op='evaluate',code="CallbackMod:AddCallback('owner',function()RegisterMod('Runtime Child',1)end);Isaac.RunCallback('owner')",expect_error='Framework callback mod registration ownership unverified');data['cases'].append(c)
    data['schema']='callback-framework-contracts-3';t.s.e.v.s.o.freeze_json(CURRENT,data)
    print(json.dumps(dict(corrected_manifest=True,cases=len(data['cases']))))

def invoke(path,c,reference=False):
    start=time.perf_counter()
    try:p=subprocess.run([str(REF if reference else EXE),'--callback-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Callback output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r
def setup():t.EXE=EXE;t.REF=REF;t.invoke=invoke;t.setup()
def run(path,out,real=False):
    setup();r=t.s.e.v.s.run(path,out,real)if path==t.s.e.v.s.CURRENT else t.run(path,out,real)
    for row in r['cases']:
        for p in row['reports']:
            if p and 'semantic'in p and path in [MANIFEST,CURRENT]:
                row['checks'].append(dict(check='source-framework-explicit-capture-boundary',passed=not p['consumer_read_sets_implemented']and all(m['callback_framework']['source_unmodified']and not m['callback_framework']['consumer_capture_supported']and m['callback_framework']['depth']==0 for m in p['metadata'])))
        row['passed']=all(x['passed']for x in row['checks'])
    r['passed']=all(c['passed']for c in r['cases']);r['schema']='callback-framework-results-1';r['callback_driver_sha256']=old.digest(Path(__file__))
    raw=(json.dumps(r,separators=(',',':'))+'\n').encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));print(json.dumps(dict(callback_finished=True,passed=r['passed'],cases=len(r['cases']),failures=[dict(id=c['id'],checks=[x['check']for x in c['checks']if not x['passed']])for c in r['cases']if not c['passed']])),flush=True);return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real','textures','sdk']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze();freeze_corrected()
    else:sys.exit(0 if run(REAL if a.phase=='real'else t.CURRENT if a.phase=='textures'else t.s.e.v.s.CURRENT if a.phase=='sdk'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
