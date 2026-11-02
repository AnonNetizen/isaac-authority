"""Standalone x64 sizing estimate. Never replaces the Windows x86 game runtime."""
import argparse,ctypes,json,os,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import probe_incremental_walk_completion as walk
from run_incremental_ui import ROOT,digest,write

REPORT=ROOT/'reports/ui-incremental-x64-completion-sizing.json'
walk.REPORT=REPORT
walk.WATCHDOG=1800

def evaluator(destination):
    # The old evaluator calls research.tag whenever exports exist, even in plain
    # mode. Match boundary_tests' explicit active-mode guard in this test adapter.
    source=(ROOT/'trace_runtime/runner.cpp').read_text(encoding='utf-8')
    source=source.replace('ia::BridgeLuaApi active_api;','ia::BridgeLuaApi active_api;bool active_traced{};')
    source=source.replace('if(api.trace.source)api.trace.mark','if(active_traced&&api.trace.source)api.trace.mark')
    source=source.replace('const bool trace=std::wstring(argv[5])==L"trace";','const bool trace=std::wstring(argv[5])==L"trace";active_traced=trace;')
    (destination/'sources/trace_runner.cpp').write_text(source,encoding='utf-8')

def prepare(destination):
    walk.prepare(destination,2000000000,8192,4194304,524288,True)
    path=destination/'CMakeLists.txt';text=path.read_text(encoding='utf-8')
    text=text.replace('CMAKE_SIZEOF_VOID_P EQUAL 4','CMAKE_SIZEOF_VOID_P EQUAL 8').replace('Sizing probe requires Win32','Sizing estimate requires Windows x64')
    begin=text.index('add_library(authority_core STATIC IMPORTED)');end=text.index('file(GLOB LUA_C',begin)
    repo=ROOT.as_posix()
    core=['core.cpp','platform.cpp','steam.cpp']
    bridge=['lua_bridge.cpp','mod_runtime.cpp','mod_runtime_slice2.cpp','mod_runtime_slice3.cpp','runtime_suite.cpp','engine_api.cpp','resources.cpp','ui_backend.cpp']
    native_files=core+bridge
    generated_header=ROOT/'build-ui-incremental-encoded/resource_catalog.hpp'
    (destination/'sources/resource_catalog.hpp').write_bytes(generated_header.read_bytes())
    text=text[:begin]+f'''add_library(authority_core STATIC {' '.join(chr(34)+repo+'/native/'+n+chr(34) for n in core)})
target_link_libraries(authority_core PUBLIC bcrypt)
add_library(authority_lua_bridge STATIC {' '.join(chr(34)+repo+'/native/'+n+chr(34) for n in bridge)})
target_include_directories(authority_lua_bridge PRIVATE "{destination.as_posix()}/sources")
target_link_libraries(authority_lua_bridge PUBLIC authority_core)
'''+text[end:]
    text+=f'''
file(GLOB REFERENCE_C "{repo}/third_party/lua533/src/*.c")
list(FILTER REFERENCE_C EXCLUDE REGEX "/lua[c]?\\\\.c$")
add_library(ia_lua533_reference SHARED ${{REFERENCE_C}})
target_compile_definitions(ia_lua533_reference PRIVATE LUA_BUILD_AS_DLL)
target_compile_options(ia_lua533_reference PRIVATE /W0)
add_executable(authority-trace-research "{destination.as_posix()}/sources/trace_runner.cpp")
target_link_libraries(authority-trace-research PRIVATE authority_lua_bridge)
add_executable(authority-incremental-upvalue-tests "{repo}/incremental_ui_runtime/upvalue_tests.cpp")
target_link_libraries(authority-incremental-upvalue-tests PRIVATE authority_lua_bridge)
'''
    path.write_text(text,encoding='utf-8')
    evaluator(destination)
    with (destination/'generated/ia_trace.cpp').open('a',encoding='utf-8') as handle:handle.write('\nextern "C" __declspec(dllexport) unsigned ia_sizing_pointer_bytes(){return sizeof(void*);}\n')
    walk.edit(destination/'sources/runner.cpp','        if(!sizing)throw std::runtime_error("Sizing-only DLL required");','''        if(!sizing)throw std::runtime_error("Sizing-only DLL required");
        auto pointer_bytes=reinterpret_cast<unsigned(__cdecl*)()>(GetProcAddress(module,"ia_sizing_pointer_bytes"));
        if(sizeof(void*)!=8||!pointer_bytes||pointer_bytes()!=8)throw std::runtime_error("Standalone x64 sizing ABI required");''',1)
    walk.edit(destination/'sources/runner.cpp','report["measurement_only"]=true;','report["architecture"]="x64";report["estimate_only"]=true;report["measurement_only"]=true;',1)
    derivation=json.loads((destination/'derivation.json').read_bytes())
    derivation.update({'architecture':'x64','pointer_bytes':8,'estimate_only':True,'native_sources_recompiled':{n:digest(ROOT/'native'/n) for n in native_files},'resource_catalog_sha256':digest(generated_header),'borrowed_x86_libraries_linked':False,'watchdog_seconds':walk.WATCHDOG,'x64_probe_tool_sha256':digest(Path(__file__))})
    write(destination/'derivation.json',derivation)

def machine(path):
    with path.open('rb') as handle:
        handle.seek(60);offset=struct.unpack('<I',handle.read(4))[0];handle.seek(offset)
        if handle.read(4)!=b'PE\0\0':raise ValueError('Not a PE binary')
        return struct.unpack('<H',handle.read(2))[0]

def preflight(destination):
    binary=destination/'build/Release';output=destination/'preflight';attempt=1
    while output.exists():attempt+=1;output=destination/('preflight-'+str(attempt))
    output.mkdir(exist_ok=False)
    dll=binary/'ia_lua533_ui_incremental.dll';ref=binary/'ia_lua533_reference.dll';runner=binary/'authority-trace-research.exe'
    for path in [dll,ref,runner,binary/'authority-sizing-checkpoint-tests.exe']:
        if machine(path)!=0x8664:raise ValueError('Non-x64 binary: '+str(path))
    # Frozen ordinary Lua oracle programs remain unchanged; source hashes verified.
    manifest=ROOT/'research/ui_incremental_oracle_encoded_v1.json'
    spec=json.loads(manifest.read_bytes());rows=[]
    for case in spec['cases']:
        source=ROOT/case['file']
        if digest(source)!=case['sha256']:raise ValueError('Frozen oracle source changed')
        runs={}
        for name,runtime,mode in [('reference',ref,'plain'),('candidate-plain',dll,'plain'),('candidate-trace',dll,'trace')]:
            env=os.environ.copy();env.pop('IA_SIZING_COMPACT_CHECKPOINT',None);env.pop('IA_INCREMENTAL_VERIFY',None)
            if mode=='trace':env['IA_INCREMENTAL_VERIFY']='1'
            result=subprocess.run([str(runner),'--evaluate',str(runtime),digest(runtime),str(source),mode],capture_output=True,env=env,timeout=60)
            (output/(case['id']+'-'+name+'.json')).write_bytes(result.stdout)
            (output/(case['id']+'-'+name+'.stderr.txt')).write_bytes(result.stderr)
            if result.returncode:raise ValueError('Preflight process failed: '+case['id'])
            runs[name]=json.loads(result.stdout)
        ordinary=lambda r:{k:r.get(k) for k in ['success','values','error']}
        same=ordinary(runs['reference'])==ordinary(runs['candidate-plain'])==ordinary(runs['candidate-trace'])
        # Known unsupported-native cases must preserve their registered refusal.
        safety=case.get('case_kind')=='safety'
        if safety:same=ordinary(runs['reference'])==ordinary(runs['candidate-plain']) and not runs['candidate-trace']['success'] and case['expected_unsupported'] in runs['candidate-trace'].get('error','')
        trace=runs['candidate-trace']['trace'];b=trace['bounded_work'];inc=trace['incremental']
        if not same or b['used']!=sum(b['categories'].values()) or b['failure'] or (not safety and not inc['full_oracle_checks']):raise ValueError('Ordinary execution/origin/accounting preflight failed: '+case['id'])
        rows.append({'id':case['id'],'source_sha256':case['sha256'],'ordinary_execution_equal':same,'expected_safety_refusal':safety,'work_used':b['used'],'origin_oracle_checks':inc['full_oracle_checks']})
    upvalues={}
    for name,runtime,mode in [('reference',ref,'plain'),('candidate',dll,'trace')]:
        env=os.environ.copy();env.pop('IA_SIZING_COMPACT_CHECKPOINT',None);env['IA_INCREMENTAL_VERIFY']='1'
        result=subprocess.run([str(binary/'authority-incremental-upvalue-tests.exe'),str(runtime),digest(runtime),mode],capture_output=True,env=env,timeout=60)
        (output/('upvalues-'+name+'.json')).write_bytes(result.stdout)
        if result.returncode:raise ValueError('Upvalue preflight process failed')
        upvalues[name]=json.loads(result.stdout)
    if [x['value'] for x in upvalues['reference']['observations']]!=[x['value'] for x in upvalues['candidate']['observations']]:raise ValueError('Upvalue ordinary result changed')
    proof={'passed':True,'architecture':'x64','estimate_only':True,'runtime_sha256':digest(dll),'reference_sha256':digest(ref),'manifest_sha256':digest(manifest),'cases':rows,'upvalue_values_equal':True}
    proof['raw_output_directory']=str(output)
    write(output/'result.json',proof)
    if output!=destination/'preflight':write(destination/'preflight/result.json',proof)
    print(json.dumps({'preflight_passed':True,'cases':len(rows),'origin_checks':sum(x['origin_oracle_checks'] for x in rows)}),flush=True)
    walk.boundaries(destination)

class ProcessMemoryCounters(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage']]

class MeteredProcess(walk.SizingProcess):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.memory={};self.started=time.perf_counter()
        command=args[0] if args else kwargs.get('args',[]);self.manifest=Path(command[-1])
    def wait(self,timeout=None):
        deadline=time.monotonic()+(walk.WATCHDOG if timeout==120 else timeout or walk.WATCHDOG)
        psapi=ctypes.WinDLL('psapi');get=psapi.GetProcessMemoryInfo;get.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong];get.restype=ctypes.c_int
        while True:
            counter=ProcessMemoryCounters();counter.cb=ctypes.sizeof(counter)
            if get(int(self._handle),ctypes.byref(counter),counter.cb):
                for name in ['PeakWorkingSetSize','PeakPagefileUsage','PrivateUsage']:self.memory[name]=max(self.memory.get(name,0),getattr(counter,name))
            try:code=super().wait(timeout=min(1,max(0,deadline-time.monotonic())))
            except subprocess.TimeoutExpired:
                if time.monotonic()<deadline:continue
                raise
            write(self.manifest.with_name(self.manifest.stem.replace('-suite','')+'-process.json'),{'exit_code':code,'process_seconds':time.perf_counter()-self.started,'memory':self.memory,'architecture':'x64'})
            return code

def finalize(destination):
    walk.finalize(destination);result=json.loads(REPORT.read_bytes());derivation=result['derivation']
    for name,sha in derivation['native_sources_recompiled'].items():
        if digest(ROOT/'native'/name)!=sha:raise ValueError('Native source changed during sizing')
    for relative,sha in derivation.get('candidate_source_hashes',{}).items():
        if digest(destination/relative)!=sha:raise ValueError('Candidate source changed during sizing')
    if digest(ROOT/'build-ui-incremental-encoded/resource_catalog.hpp')!=derivation['resource_catalog_sha256']:raise ValueError('Resource catalog changed')
    result.update({'schema':'isaac-x64-initialization-sizing-1','architecture':'x64','pointer_bytes':8,'estimate_only':True,'formal_x86_acceptance':False,'borrowed_x86_libraries_linked':False,'preflight':json.loads((destination/'preflight/result.json').read_bytes()),'binary_hashes':{p.name:digest(p) for p in (destination/'build/Release').iterdir() if p.suffix in ['.dll','.exe']}})
    for row in result['cases']:
        metrics=destination/'results'/(row['id']+'-process.json')
        if metrics.exists():row['process_metrics']=json.loads(metrics.read_bytes())
    result['full_cases_completed']=[r['id'] for r in result['cases'] if r['exit_code']==0 and r.get('initialization_passed') and r.get('contract_passed')]
    result['sizing_scope']='Standalone Windows x64 estimate: frozen J460/mod initialization and existing contract checks, all tracking/charges retained, compact diagnostic copies, final full evidence export omitted. Not Windows x86 acceptance or game frame time.'
    write(destination/'results/completion-sizing.json',result);write(REPORT,result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','preflight','run','finalize']);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--cases',nargs='+',default=['eid-en','combined-en']);args=parser.parse_args();destination=args.directory.resolve()
    if args.phase=='prepare':prepare(destination)
    elif args.phase=='preflight':preflight(destination)
    elif args.phase=='finalize':finalize(destination)
    else:
        proof=json.loads((destination/'preflight/result.json').read_bytes())
        dll=destination/'build/Release/ia_lua533_ui_incremental.dll'
        if not proof.get('passed') or proof['runtime_sha256']!=digest(dll):raise ValueError('Exact x64 preflight required')
        from run_trace_research import verify_pristine
        derivation=json.loads((destination/'derivation.json').read_bytes())
        derivation['pristine_lua_files_verified']=verify_pristine()
        derivation['candidate_source_hashes']={p.relative_to(destination).as_posix():digest(p) for folder in ['sources','generated'] for p in (destination/folder).iterdir() if p.is_file()}
        derivation['candidate_source_hashes']['CMakeLists.txt']=digest(destination/'CMakeLists.txt')
        derivation['x64_probe_tool_sha256']=digest(Path(__file__))
        derivation['evaluator_plain_mode_guard']=True
        derivation['preflight_prior_failed_attempts_retained']=2
        write(destination/'derivation.json',derivation)
        walk.base.LIMIT=json.loads((destination/'derivation.json').read_bytes())['probe_work_limit'];os.environ['IA_SIZING_COMPACT_CHECKPOINT']='1';subprocess.Popen=MeteredProcess
        walk.base.run(destination,args.cases);finalize(destination)
