"""Frozen Lua module contracts, isolated caches and real-source entry attempts."""
import argparse,copy,gzip,hashlib,json,re,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_compact_values as compact
import verify_compact_values
ROOT=compact.ROOT;BASE=ROOT/'build-frozen-module';EXE=BASE/'Release/authority-modules.exe';REF=EXE.with_name('authority-modules-reference.exe');MANIFEST=ROOT/'research/frozen_modules_v3.json';REAL=ROOT/'research/frozen_modules_real_v1.json'
old=compact.b.old
def evaluate(code):return dict(op='evaluate',code=code)
def capture(**keys):return dict(op='capture_reads',event=2,phase='presentation',input=keys)
def values(*items):
    return [dict(type='nil')if v is None else dict(type='boolean',value=v)if isinstance(v,bool)else dict(type='integer',value=v)if isinstance(v,int)else dict(type='string',hex=(v if isinstance(v,bytes)else v.encode()).hex())for v in items]
def freeze():
    folder=ROOT/'research/frozen_modules';folder.mkdir(exist_ok=True)
    files={
      'main.lua':"ModuleFixtureMod=RegisterMod('Frozen Module Contract',1)\nlocal state=require('lib.state')\nlocal function flag(k)return Input.IsButtonTriggered(k)end\nModuleFixtureMod:AddCallback(1,function()require('lib.world')end)\nModuleFixtureMod:AddCallback(2,function()\n if flag('move')then state.cfg.x=state.cfg.x+10;ModuleFixtureMod:SaveData(require('json').encode(state.cfg))end\n if flag('fail')or flag('escape')or flag('native')or flag('binary')or flag('random')then state.cfg.amount=state.cfg.amount+10;ModuleFixtureMod:SaveData(require('json').encode(state.cfg));Isaac.RenderText('unpublished',0,0)end\n if flag('fail')then require('lib.fail')end\n if flag('escape')then pcall(require,'../outside')end\n if flag('native')then pcall(package.loadlib,'outside.dll','entry')end\n if flag('binary')then pcall(require,'lib.binary')end\n if flag('random')then pcall(require,'lib.random')end\n if flag('late')then require('lib.late').paint()else state.paint()end\n if flag('cache')then for i=1,20000 do require('lib.args')end end\nend)\n",
      'lib/state.lua':"local cfg=require('json').decode(ModuleFixtureMod:LoadData())\nreturn {cfg=cfg,paint=function()Isaac.RenderText('module='..cfg.amount..'|'..cfg.language,cfg.x,0)end}\n",
      'lib/false.lua':"false_count=(false_count or 0)+1;return false\n",
      'lib/nil.lua':"nil_count=(nil_count or 0)+1;return nil\n",
      'lib/setloaded.lua':"local name=...;package.loaded[name]={tag='manual'}\n",
      'lib/args.lua':"local name,file=...;return {name=name,file=file}\n",
      'lib/multi.lua':"multi_count=(multi_count or 0)+1;return false,nil,string.char(0,255)\n",
      'lib/syntax.lua':"local = broken syntax\n",
      'lib/error.lua':"error_count=(error_count or 0)+1;error_object=error_object or {};error(error_object)\n",
      'lib/retry.lua':"retry_count=(retry_count or 0)+1;if retry_count==1 then error('retry-once')end;return {count=retry_count}\n",
      'lib/fail.lua':"ModuleFailureState=1;package.loaded.uncommitted={value=9};error('module-injected')\n",
      'lib/late.lua':"local cfg=require('json').decode(ModuleFixtureMod:LoadData());return {paint=function()Isaac.RenderText('late='..cfg.amount,cfg.x,0)end}\n",
      'lib/world.lua':"Isaac.GetPlayer(0):AddCoins(1);return {reward=1}\n",
      'lib/random.lua':"return math.random(1,9)\n",
      'lib/busy.lua':"while true do end\n",
      'resources/lib/fallback.lua':"return 'resource-source'\n",
      'second/main.lua':"-- A second frozen root, not automatically executed.\n",
      'second/lib/function.lua':"return function()return require('private.second')end\n",
      'second/private/second.lua':"return 'second-root'\n"}
    for name,source in files.items():
        p=folder/name;p.parent.mkdir(exist_ok=True,parents=True)
        if p.exists():assert p.read_text(encoding='utf-8')==source
        else:p.write_text(source,encoding='utf-8')
    binary=folder/'lib/binary.lua'
    if binary.exists():assert binary.read_bytes()==b'\x1bLua-not-text'
    else:binary.write_bytes(b'\x1bLua-not-text')
    for name,data in [('bom.lua',b'\xef\xbb\xbfreturn "bom"\n'),('header.lua',b'#!/unavailable/interpreter\nreturn "header"\n'),('header_empty.lua',b'#!/unavailable/interpreter')]:
        p=folder/'lib'/name
        if p.exists():assert p.read_bytes()==data
        else:p.write_bytes(data)
    def root(path,display,paths):return dict(root=path.relative_to(ROOT).as_posix(),display=display,sha256={p.relative_to(path).as_posix():old.digest(p)for p in paths})
    second=folder/'second';roots=[root(folder,'mods/fixture',[p for p in folder.rglob('*.lua')if not p.is_relative_to(second)]),root(second,'mods/second',second.rglob('*.lua'))]
    cases=[]
    def case(name,steps,expected=None,kind='contract',**kw):
        c=dict(id=name,source=(folder/'main.lua').relative_to(ROOT).as_posix(),source_sha256=old.digest(folder/'main.lua'),modules=dict(entry=0,roots=copy.deepcopy(roots)),stores=[old.store(1,17,'en'),old.store(2,137,'zh')],steps=steps,kind=kind,**kw)
        if expected is not None:c['expected_values']=values(*expected)
        cases.append(c);return c
    case('cache-identity',[evaluate("local a=require('lib.state');local b=require('lib.state');return rawequal(a,b),a.cfg.amount")],[True,2])
    case('false-reexecutes',[evaluate("local a=require('lib.false');local b=require('lib.false');return a,b,false_count")],[False,False,2])
    case('nil-becomes-true',[evaluate("local a=require('lib.nil');local b=require('lib.nil');return a,b,nil_count")],[True,True,1])
    case('module-sets-loaded',[evaluate("local a=require('lib.setloaded');return rawequal(a,package.loaded['lib.setloaded']),a.tag")],[True,'manual'])
    case('loader-arguments',[evaluate("local a=require('lib.args');return a.name,a.file")],['lib.args','mods/fixture/lib/args.lua'])
    case('require-first-return',[evaluate("local a=require('lib.multi');return a,multi_count")],[False,1])
    case('dofile-multi-return',[evaluate("return dofile('lib/multi.lua')")],[False,None,b'\0\xff'])
    case('include-multi-return',[evaluate("return include('lib.multi')")],[False,None,b'\0\xff'])
    case('include-without-cache',[evaluate("include('lib.multi');include('lib.multi');local a=require('lib.multi');return a,multi_count")],[False,3])
    case('utf8-bom',[evaluate("return require('lib.bom')")],['bom'])
    case('ignored-source-header',[evaluate("return require('lib.header')")],['header'])
    case('header-without-newline',[evaluate("return include('lib.header_empty')")],[])
    case('explicit-dofile-root',[evaluate("local a=dofile('mods/fixture/lib/args.lua');return a.name==nil,a.file==nil")],[True,True])
    case('missing-catchable',[evaluate("local ok,e=pcall(require,'absent');return ok,type(e)=='string' and e:find('no file',1,true)~=nil,require('lib.state').cfg.amount")],[False,True,2])
    case('empty-name-discovery',[evaluate("local ok,e=pcall(require,'');local _,a=e:find(\"no file '\",1,true);local _,b=e:find(\"no file '\",a,true);local finish=e:find(\".lua'\",b,true);return ok,e:sub(b+1,finish-1)")],[False,'mods/fixture/'])
    case('syntax-retry',[evaluate("local a=pcall(require,'lib.syntax');local b=pcall(require,'lib.syntax');return a,b,package.loaded['lib.syntax']==nil")],[False,False,True])
    case('error-object-identity',[evaluate("local a,e=pcall(require,'lib.error');return a,rawequal(e,error_object),error_count,package.loaded['lib.error']==nil")],[False,True,1,True])
    case('retry-after-error',[evaluate("local a=pcall(require,'lib.retry');local b=require('lib.retry');local c=require('lib.retry');return a,b.count,rawequal(b,c)")],[False,2,True])
    case('prepopulated-loaded',[evaluate("package.loaded['lib.false']=true;local a=require('lib.false');package.loaded['lib.false']=false;local b=require('lib.false');return a,b,false_count")],[True,False,1])
    case('preload-contract',[evaluate("package.preload.fixture=function(n,d)preload_nil=d==nil;return {name=n}end;local a=require('fixture');return a.name,preload_nil,rawequal(a,require('fixture'))")],['fixture',True,True])
    case('numeric-module-name',[evaluate("return require(12)")],['numeric-name'])
    p=folder/'12.lua'
    if p.exists():assert p.read_text(encoding='utf-8')=="return 'numeric-name'\n"
    else:p.write_text("return 'numeric-name'\n",encoding='utf-8')
    for c in cases:c['modules']['roots'][0]['sha256']['12.lua']=old.digest(p)
    roots[0]['sha256']['12.lua']=old.digest(p)
    case('package-loaded-alias',[evaluate("local old=package.loaded;package.loaded={};return rawequal(require('lib.state'),old['lib.state'])")],[True])
    case('caller-root-closure',[evaluate("local f=dofile('mods/second/lib/function.lua');return f()")],['second-root'])
    case('ascii-case-source',[evaluate("local a=require('LIB.ARGS');return a.name,a.file")],['LIB.ARGS','mods/fixture/lib/args.lua'])
    case('resource-fallback',[evaluate("return require('lib.fallback')")],['resource-source'])
    case('no-native-searchers',[evaluate("return #package.searchers,package.loaded.os==nil,io==nil,debug==nil,load==nil,os.execute==nil")],[2,True,True,True,True,True])
    case('private-config-closures',[dict(capture(),role='host'),capture()],kind='draws',expected_draws=[('module=1|en',17),('module=2|zh',137)])
    case('private-save-reload',[capture(move=True),dict(op='reload_saved'),capture()],kind='draws',expected_draws=[('module=2|zh',147),('module=2|zh',147)])
    case('late-callback-load',[capture(late=True),capture(late=True)],kind='draws',expected_draws=[('late=2',137),('late=2',137)])
    case('cache-hit-stress',[capture(cache=True)],kind='cache-stress')
    case('closing-generation',[evaluate("gc_anchor=setmetatable({},{__gc=function()require('lib.args')end})"),dict(op='rebuild'),evaluate("return package.loaded['lib.args']==nil")],[True])
    case('authority-module-once',[old.dispatch('host',1,'authority'),old.dispatch('host',1,'authority')],kind='authority')
    for key,error in [('fail','module-injected'),('escape','Frozen module path outside registered roots'),('native','Native package capability unsupported'),('binary','Frozen binary module unsupported'),('random','Random result has no proven authority reference')]:case('rollback-'+key,[dict(capture(**{key:True}),expect_error=error),capture(),evaluate("return ModuleFailureState==nil,package.loaded.uncommitted==nil,package.loaded['lib.fail']==nil")],expected=[True,True,True],kind='rollback')
    c=case('hash-mismatch',[],kind='process-rejection',error='Frozen module source hash mismatch');c['modules']['roots'][0]['sha256']['lib/state.lua']='0'*64
    c=case('root-outside',[],kind='process-rejection',error='Frozen module path outside registered roots');c['modules']['roots'][0]['root']='../outside'
    case('module-work-cap',[evaluate("return require('lib.busy')")],kind='process-rejection',error='Boundary work limit exceeded')
    # Execute the real helper without changing it; the fixture main remains the entry.
    real_suite=json.loads((ROOT/'research/ui_incremental_suite_10m_v1.json').read_text(encoding='utf-8'));realmods={}
    for item in real_suite['cases']:
        for mod in item['mods']:realmods[mod['root']]=mod
    realroots=[dict(root='research/slice3_ui_inputs/'+name,display=name,sha256=mod['sha256'])for name,mod in realmods.items()]
    mcm=next(r for r in realroots if 'mod_config_menu' in r['display']);eid=next(r for r in realroots if 'external item' in r['display'])
    c=case('real-filepath-helper',[evaluate("local helper=dofile('"+mcm['display']+"/scripts/filepathhelper.lua');return helper.GetCurrentModPath()")],expected=[mcm['display']+'/']);c['modules']['roots'].append(mcm)
    def save_manifest(path,obj):
        if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==obj
        else:old.save(path,obj)
    save_manifest(MANIFEST,dict(schema='frozen-modules-contract-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    attempts=[]
    for name,rr in [('mcm',[mcm]),('eid',[eid]),('combined',[mcm,eid])]:
        first=rr[0];source=first['root']+'/main.lua';attempts.append(dict(id=name,source=source,source_sha256=old.digest(ROOT/source),modules=dict(entry=0,roots=rr),stores=['{}','{}'],steps=[],kind='real-entry'))
    save_manifest(REAL,dict(schema='frozen-real-module-entry-1',work_limit=10000000,timeout_seconds=5,cases=attempts));print(json.dumps(dict(cases=len(cases),real_entries=len(attempts))))

def invoke(path,c,reference=False):
    start=time.perf_counter();exe=REF if reference else EXE
    try:p=subprocess.run([str(exe),'--module-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Module output capacity')
    try:report=json.loads(p.stdout)
    except ValueError:report=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),stdout_tail=None if report is not None else p.stdout[-4096:].decode('utf-8',errors='replace')),report

def protected():
    verify_compact_values.main();v=json.loads((ROOT/'reports/compact-values-final.json').read_text(encoding='utf-8'));result=compact.protected()
    for group in ['inputs','binaries']:
        for p,h in v[group].items():assert old.digest(ROOT/p)==h;result[p]=h
    return result

def run(out,real=False):
    before=protected();out.mkdir(exist_ok=False,parents=True);path=REAL if real else MANIFEST;spec=json.loads(path.read_text(encoding='utf-8'));rows=[];start=time.perf_counter();saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    for c in spec['cases']:
        if time.perf_counter()-start>60:raise RuntimeError('Short module batch deadline')
        results=[];artifacts=[]
        for reference in [True,False,False]:a,r=invoke(path,c,reference);results.append(r);artifacts.append(a)
        ref,first,second=results;checks=[]
        def check(name,value):checks.append(dict(check=name,passed=bool(value)))
        if any(r is None for r in results):check('completed-with-diagnostic',False)
        elif real:
            def diagnostic(r):
                error=r.get('first_unsupported_entry');match=re.match(r'^(.*?:\d+: )(.*)$',error or'')
                return match.group(1).replace('\\','/')+match.group(2)if match else error
            check('same-initialization-result',all(diagnostic(r)==diagnostic(ref)for r in results));check('valid-work-accounting',all(r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())for r in results));check('no-full-trace',all(not r['full_trace_enabled']and not r['game_started']for r in results))
        elif c['kind']=='process-rejection':check('explicit-process-rejection',all(c['error']in r.get('first_unsupported_entry','')for r in results))
        elif any('semantic'not in r for r in results):check('contract-completed',False)
        else:
            check('stock-lua-ordinary-results',compact.b.draws.ordinary(ref)==compact.b.draws.ordinary(first)==compact.b.draws.ordinary(second));check('repeat-source-compilations',first['modules']==second['modules']);check('no-full-trace-or-projection',not first['full_trace_enabled']and not first['automatic_projection_implemented']and not first['personal_draws_publishable']);check('work-accounting',first['budget']['used']==sum(first['budget']['categories'].values())and first['budget']['limit']==10000000)
            if c.get('expected_values')is not None:check('contract-values',first['steps'][-1].get('values')==c['expected_values'])
            if c['kind']=='draws':check('actual-private-draws',[(bytes.fromhex(s['draws'][0]['text_hex']).decode(),s['draws'][0]['x'])for s in first['steps']if 'draws'in s]==[tuple(v)for v in c['expected_draws']])
            if c['kind']=='rollback':check('private-store-and-draw-restored',first['semantic']['stores']==c['stores']and bytes.fromhex(first['steps'][1]['draws'][0]['text_hex'])==b'module=2|zh')
            if c['kind']=='authority':check('host-commits-world-once',first['semantic']['world']['coins']==1 and len(first['semantic']['world']['effects'])==1)
            if c['kind']=='cache-stress':check('cache-hits-do-not-recompile',first['modules']['states'][1]['compilations']==2 and first['modules']['states'][1]['searches']==2)
            if c['id']=='closing-generation':check('old-finalizer-does-not-pollute-new-audit',first['modules']['states'][1]['compilations']==1 and first['modules']['states'][1]['generation']==4)
        diagnostic_agreement=all(x['passed']for x in checks);initialized=all(a.get('returncode')==0 for a in artifacts)
        row=dict(id=c['id'],kind=c['kind'],passed=diagnostic_agreement and(initialized if real else True),diagnostic_agreement=diagnostic_agreement if real else None,initialization_completed=initialized,checks=checks,artifacts=artifacts,reports=results);rows.append(row);old.save(out/'progress.json',dict(cases=rows));print(json.dumps(dict(id=c['id'],passed=row['passed'],error=(first or{}).get('first_unsupported_entry'))),flush=True)
        if not row['passed']and not real:break
    r=dict(schema='frozen-module-entry-result-1'if real else'frozen-module-contract-result-1',passed=len(rows)==len(spec['cases'])and all(r['passed']for r in rows),real_mod_initialization_passed=real and all(r['artifacts'][1]['returncode']==0 for r in rows),cases=rows,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,game_started=False,full_trace_enabled=False,authority_projection_passed=False,protected_files_unchanged=before==protected(),save_files_unchanged=saves['files']==old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')['files'],manifest_sha256=old.digest(path),driver_sha256=old.digest(Path(__file__)),binaries={p.name:old.digest(p)for p in [EXE,REF]})
    r['passed']=r['passed']and r['protected_files_unchanged']and r['save_files_unchanged'];old.save(out/'result.json',r);(out/'progress.json').unlink();print(json.dumps(dict(passed=r['passed'],cases=len(rows),seconds=r['seconds'],real_mod_initialization_passed=r['real_mod_initialization_passed'])));return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:
        output=a.output.resolve();existed=output.exists()
        try:sys.exit(0 if run(output,a.phase=='real')['passed']else 1)
        except Exception as e:
            if not existed and output.is_dir():old.save(output/'failure.json',dict(classification='interrupted-module-gate',error=type(e).__name__+': '+str(e),driver_sha256=old.digest(Path(__file__)),binaries={p.name:old.digest(p)for p in[EXE,REF]}))
            raise
