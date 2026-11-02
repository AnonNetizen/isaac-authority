"""Isolated initialization sizing probe; never changes the production 10M profile."""
import argparse, copy, importlib.util, json, os, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT, digest, write
from run_slice3_ui_research import verify_inputs
from audit_baseline import audit

LIMIT=100000000

def prepare(destination):
    destination.mkdir(parents=True,exist_ok=False)
    generated=destination/'generated';sources=destination/'sources';sources.mkdir()
    spec=importlib.util.spec_from_file_location('production_incremental_prepare',ROOT/'incremental_ui_runtime/prepare_lua.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.prepare(ROOT/'third_party/lua533',generated,10000000)
    path=generated/'bounded_cfg.hpp';text=path.read_text()
    if text.count('constexpr uint64_t work_limit=10000000;')!=1:raise ValueError('Probe work constant mismatch')
    path.write_text(text.replace('constexpr uint64_t work_limit=10000000;',f'constexpr uint64_t work_limit={LIMIT};'),encoding='utf-8')
    for path in (ROOT/'incremental_ui_runtime').iterdir():
        if path.suffix in ['.hpp','.h','.cpp','.inc']:
            (sources/path.name).write_bytes(path.read_bytes())
    path=sources/'evidence_store.hpp';text=path.read_text()
    if text.count('encoded_byte_limit=64*1024*1024')!=1:raise ValueError('Probe byte constant mismatch')
    path.write_text(text.replace('encoded_byte_limit=64*1024*1024','encoded_byte_limit=512*1024*1024'),encoding='utf-8')
    path=generated/'ia_trace.cpp'
    with path.open('a',encoding='utf-8') as handle:handle.write('''
// Passive measurement only: no execution, evidence suppression, or budget reset.
extern "C" __declspec(dllexport) const char* ia_initialization_sizing_status(){
    static std::string result;Json rows=Json::array();
    for(auto& [L,ptr]:states)if(ptr&&ptr->enabled){auto& s=*ptr;auto& b=ia_bounded_budget(L);auto& x=inc(s);
        rows.push_back({{"work_limit",ia::bounded::work_limit},{"work_used",b.used},{"categories",b.categories},{"budget_failure",b.failure},{"trace_failure",s.failure},{"instructions",s.instructions},{"logical_events",x.cache_events.size()},{"descriptors",x.cache_events.descriptors.size()},{"encoded_bytes",x.cache_events.encoded_bytes},{"encoded_byte_limit",IncEvidenceStore::encoded_byte_limit},{"evidence_first_fault",x.cache_events.first_fault}});
    }result=rows.dump();return result.c_str();
}
''')
    path=sources/'runner.cpp';text=path.read_text()
    needle='        host=api.newstate();api.openlibs(host);'
    replacement='''        auto sizing=reinterpret_cast<const char*(__cdecl*)()>(GetProcAddress(module,"ia_initialization_sizing_status"));
        if(!sizing)throw std::runtime_error("Sizing-only DLL required");
        auto snapshot=[&](){auto rows=Json::parse(sizing());if(rows.size()!=1)throw std::runtime_error("Sizing context is not unique");return rows.at(0);};
'''+needle
    if text.count(needle)!=1:raise ValueError('Probe runner initialization mismatch')
    text=text.replace(needle,replacement)
    text=text.replace('std::cerr<<"modules complete\\n"<<std::flush;','item["after_modules"]=snapshot();std::cerr<<"modules complete\\n"<<std::flush;')
    begin=text.index('            if(context&&trace)item["execution_dependencies"]')
    end=text.index('            std::cerr<<"evidence complete',begin)
    text=text[:begin]+'''            if(context&&trace)item["sizing"]=snapshot();
'''+text[end:]
    text=text.replace('        report["work_limit"]=IA_INCREMENTAL_WORK_LIMIT;','''        report["work_limit"]=IA_INCREMENTAL_WORK_LIMIT;
        report["measurement_only"]=true;report["full_final_evidence_export_tested"]=false;
        report["encoded_byte_limit"]=512*1024*1024;
''')
    path.write_text(text,encoding='utf-8')
    repo=ROOT.as_posix();local=sources.as_posix();gen=generated.as_posix()
    cmake=f'''cmake_minimum_required(VERSION 3.24)
project(IsaacInitializationSizing LANGUAGES C CXX)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
  message(FATAL_ERROR "Sizing probe requires Win32")
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
add_compile_options(/W4 /EHsc /utf-8)
add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN)
include_directories("{repo}/native" "{repo}/third_party")
add_library(authority_core STATIC IMPORTED)
set_target_properties(authority_core PROPERTIES IMPORTED_LOCATION "{repo}/build-ui-incremental-encoded/Release/authority_core.lib" INTERFACE_LINK_LIBRARIES bcrypt)
add_library(authority_lua_bridge STATIC IMPORTED)
set_target_properties(authority_lua_bridge PROPERTIES IMPORTED_LOCATION "{repo}/build-ui-incremental-encoded/Release/authority_lua_bridge.lib" INTERFACE_LINK_LIBRARIES authority_core)
file(GLOB LUA_C "{gen}/*.c")
list(FILTER LUA_C EXCLUDE REGEX "/lua[c]?\\\\.c$")
add_library(ia_lua533_ui_incremental SHARED ${{LUA_C}} "{gen}/ia_trace.cpp" "{gen}/ia_graph.cpp" "{gen}/ia_bounded.cpp" "{local}/liveness.cpp")
set_source_files_properties(${{LUA_C}} PROPERTIES COMPILE_OPTIONS "/W0")
target_compile_definitions(ia_lua533_ui_incremental PRIVATE LUA_BUILD_AS_DLL)
target_include_directories(ia_lua533_ui_incremental PRIVATE "{gen}" "{local}" "{repo}/bounded_ui_runtime" "{repo}/slice3_ui_runtime")
target_link_libraries(ia_lua533_ui_incremental PRIVATE authority_core)
add_executable(authority-ui-incremental-research "{local}/runner.cpp")
target_compile_definitions(authority-ui-incremental-research PRIVATE IA_INCREMENTAL_WORK_LIMIT={LIMIT})
target_link_libraries(authority-ui-incremental-research PRIVATE authority_lua_bridge)
target_link_options(authority-ui-incremental-research PRIVATE /LARGEADDRESSAWARE)
'''
    (destination/'CMakeLists.txt').write_text(cmake,encoding='utf-8')
    write(destination/'derivation.json',{'measurement_only':True,'formal_work_limit':10000000,'probe_work_limit':LIMIT,'probe_encoded_byte_limit':512*1024*1024,'passive_counters':True,'final_full_evidence_export_omitted':True,'ordinary_execution_tracking_unchanged':True,'source_hashes':{p.name:digest(p) for p in (ROOT/'incremental_ui_runtime').iterdir() if p.is_file()},'formal_dll_sha256':digest(ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_ui_incremental.dll'),'borrowed_library_hashes':{name:digest(ROOT/'build-ui-incremental-encoded/Release'/name) for name in ['authority_core.lib','authority_lua_bridge.lib']}})
    print(str(destination),flush=True)

def run(destination,cases):
    binary=destination/'build/Release';dll=binary/'ia_lua533_ui_incremental.dll';output=destination/'results';output.mkdir(exist_ok=True)
    before=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-before.json',before)
    frozen=verify_inputs(ROOT,Path(r'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth'))
    original=ROOT/'research/ui_incremental_suite_10m_v1.json';spec=json.loads(original.read_bytes());rows=[]
    formal=ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_ui_incremental.dll';formal_hash=digest(formal)
    for name in cases:
        subset=copy.deepcopy(spec);subset['cases']=[next(c for c in spec['cases'] if c['id']==name)]
        subset['limits']['exploration_work']=LIMIT;subset['measurement_only']=True;subset['parent_manifest_sha256']=digest(original)
        manifest=output/(name+'-suite.json');write(manifest,subset)
        path=output/(name+'.json');log=output/(name+'.stderr.txt');env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None)
        started=time.perf_counter();print('Measuring '+name,flush=True)
        with path.open('xb') as stdout,log.open('x',encoding='utf-8') as stderr:
            process=subprocess.Popen([str(binary/'authority-ui-incremental-research.exe'),'--suite',str(dll),digest(dll),str(ROOT/'research/slice3_ui_inputs'),str(ROOT),str(manifest)],stdout=stdout,stderr=stderr,env=env)
            timed_out=False
            try:code=process.wait(timeout=120)
            except subprocess.TimeoutExpired:process.kill();code=process.wait();timed_out=True
        row={'id':name,'exit_code':code,'timeout':timed_out,'process_seconds':time.perf_counter()-started}
        if code==0:
            report=json.loads(path.read_bytes());case=report['cases'][0]
            row.update({k:case.get(k) for k in ['initialization_passed','contract_passed','first_unsupported_entry','after_modules','sizing','observations','world','source_unchanged','host_stack_restored']})
            cost=row['sizing']
            if cost['work_used']!=sum(cost['categories'].values()) or cost['work_used']>LIMIT:raise ValueError('Sizing ledger inconsistent')
        else:row['stderr_tail']=log.read_text(encoding='utf-8',errors='replace')[-3000:]
        rows.append(row);write(output/'progress.json',rows)
        print(json.dumps({k:v for k,v in row.items() if k not in ['observations','sizing','after_modules','stderr_tail']},ensure_ascii=False),flush=True)
        if row.get('sizing'):print(json.dumps(row['sizing'],ensure_ascii=False),flush=True)
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-after.json',after)
    if [(c['file'],c['current_sha256']) for c in before['files']]!=[(c['file'],c['current_sha256']) for c in after['files']]:raise ValueError('Personal save/config changed')
    if digest(formal)!=formal_hash:raise ValueError('Formal DLL changed')
    frozen_after=verify_inputs(ROOT,Path(r'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth'))
    derivation=json.loads((destination/'derivation.json').read_bytes())
    for name,sha in derivation['source_hashes'].items():
        if digest(ROOT/'incremental_ui_runtime'/name)!=sha:raise ValueError('Formal runtime source changed')
    for name,sha in derivation['borrowed_library_hashes'].items():
        if digest(ROOT/'build-ui-incremental-encoded/Release'/name)!=sha:raise ValueError('Borrowed library changed')
    result={'schema':'isaac-initialization-completion-sizing-1','measurement_only':True,'formal_work_limit':10000000,'probe_work_limit':LIMIT,'probe_encoded_byte_limit':512*1024*1024,'runtime_sha256':digest(dll),'cases':rows,'game_started':False,'full_final_evidence_export_tested':False,'ordinary_tracking_and_native_checks_enabled':True,'frozen_inputs':frozen,'frozen_inputs_after':frozen_after,'save_config_files_unchanged':len(after['files']),'formal_runtime_unchanged':True}
    result['sizing_scope']='J460 enums and frozen mod initialization plus existing contract checks; passive counters, no final full evidence report export; context lifetime, not a frame budget'
    result['derivation']=derivation
    result['formal_runtime_source_unchanged']=True
    write(output/'completion-sizing.json',result);write(ROOT/'reports/ui-incremental-completion-sizing.json',result)

def finalize(destination):
    output=destination/'results';result=json.loads((output/'completion-sizing.json').read_bytes());derivation=json.loads((destination/'derivation.json').read_bytes())
    for name,sha in derivation['source_hashes'].items():
        if digest(ROOT/'incremental_ui_runtime'/name)!=sha:raise ValueError('Formal source changed')
    for name,sha in derivation['borrowed_library_hashes'].items():
        if digest(ROOT/'build-ui-incremental-encoded/Release'/name)!=sha:raise ValueError('Borrowed library changed')
    if digest(ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_ui_incremental.dll')!=derivation['formal_dll_sha256']:raise ValueError('Formal DLL changed')
    if digest(destination/'build/Release/ia_lua533_ui_incremental.dll')!=result['runtime_sha256']:raise ValueError('Probe DLL changed')
    before=json.loads((output/'save-before.json').read_bytes());after=audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    if [(c['file'],c['current_sha256']) for c in before['files']]!=[(c['file'],c['current_sha256']) for c in after['files']]:raise ValueError('Personal files changed')
    for row in result['cases']:
        if row['exit_code']!=0:continue
        cost=row['sizing']
        if cost['work_used']!=sum(cost['categories'].values()) or cost['work_used']>LIMIT:raise ValueError('Sizing ledger inconsistent')
        if row['contract_passed'] and (cost['budget_failure'] or cost['trace_failure'] or not all(c['passed'] for c in row['observations'])):raise ValueError('Sizing success is invalid')
    result['sizing_scope']='J460 enums and frozen mod initialization plus existing contract checks; passive counters, no final full evidence report export; context lifetime, not a frame budget'
    result['derivation']=derivation;result['formal_runtime_source_unchanged']=True;result['probe_large_address_aware']=True
    write(output/'save-final.json',after);write(output/'completion-sizing.json',result);write(ROOT/'reports/ui-incremental-completion-sizing.json',result)
    print(json.dumps({'cases':[{'id':r['id'],'module_work':r.get('after_modules',{}).get('work_used') if r.get('after_modules') else None,'work_used':r.get('sizing',{}).get('work_used'),'contract_passed':r.get('contract_passed'),'failure':r.get('first_unsupported_entry')} for r in result['cases']],'formal_runtime_unchanged':True,'personal_files_unchanged':len(after['files'])},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','run','finalize']);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--cases',nargs='+',default=['mcm-en','eid-en','mcm-zh','eid-zh','combined-en','combined-zh']);args=parser.parse_args()
    if args.phase=='prepare':prepare(args.directory.resolve())
    elif args.phase=='run':run(args.directory.resolve(),args.cases)
    else:finalize(args.directory.resolve())
