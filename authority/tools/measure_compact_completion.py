"""One disposable, uncapped-work x86 initialization measurement; formal files stay intact."""
import argparse, ctypes, gzip, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / 'build-ui-incremental2/compact'
GEN = FORMAL / 'generated-lua'
BASE = FORMAL / 'completion-measurement'
ABI = 'ia-lua533-compact-sizing-1'
CAP = '4294967294'

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def save(p, data):
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def protected():
    paths=[]
    for folder in [ROOT/'compact_ui_runtime', GEN, FORMAL/'Release']:
        paths += [p for p in folder.rglob('*') if p.is_file()]
    paths += [ROOT/'research/ui_incremental_suite_10m_v1.json']
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(set(paths))}

def replace(s, a, b):
    if a not in s:raise RuntimeError('Measurement patch missing: '+a)
    return s.replace(a,b)

def prepare():
    BASE.mkdir(exist_ok=False)
    source=BASE/'source';source.mkdir()
    save(BASE/'protected-before.json',protected())
    # Reuse only the C object files with unchanged VM layout. No formal sources are edited.
    names=[]
    for p in GEN.iterdir():
        if p.suffix in ['.h','.hpp','.inc'] or p.name in ['ia_graph.cpp','ia_trace.cpp','ia_bounded.cpp','private_lua_bridge.cpp','ui_backend_roots.cpp','mod_runtime_roots.cpp']:
            shutil.copyfile(p,source/p.name)
        if p.suffix=='.c' and p.name not in ['lua.c','luac.c']:names.append(p.stem)
    for p in (ROOT/'compact_ui_runtime').iterdir():
        if p.suffix in ['.hpp','.inc']:shutil.copyfile(p,source/p.name)
    shutil.copyfile(ROOT/'incremental_ui_runtime/liveness.cpp',source/'liveness.cpp')
    shutil.copyfile(ROOT/'compact_ui_runtime/real_runner.cpp',source/'real_runner.cpp')
    changes={}
    for p in source.iterdir():
        s=p.read_text(encoding='utf-8');original=s
        s=s.replace('ia-lua533-slice3-ui-compact-1',ABI)
        if p.name=='bounded_cfg.hpp':
            s=replace(s,'constexpr uint64_t work_limit=10000000;','constexpr uint64_t work_limit=UINT64_MAX;')
            s=replace(s,'constexpr int block_limit=4096;','constexpr int block_limit=2147483646;')
            s=replace(s,'#include <array>','#include <cstdio>\n#include <array>')
            s=replace(s,'used+=amount;categories[kind]+=amount;',
                'auto previous=used;used+=amount;categories[kind]+=amount;\n'
                '        if(previous/1000000!=used/1000000){std::fprintf(stderr,"MEASURE work=%llu category=%s\\n",static_cast<unsigned long long>(used),kind);std::fflush(stderr);}')
            s=s.replace('Bounded UI work budget exceeded: ','Measurement uint64 accounting overflow: ')
        if p.name in ['ia_graph.cpp','ia_trace.cpp','ia_bounded.cpp','incremental.inc','bounded_views.inc','evidence_store.hpp','liveness.cpp','compact_graph.hpp']:
            # Lift count/dependency guards, preserving their charge sites and operand validation.
            s=s.replace('>24','>1024').replace('>16384','>'+CAP).replace('>=65536','>='+CAP).replace('>65536','>'+CAP)
            s=s.replace('>=8192','>='+CAP).replace('>4096','>2147483646').replace('>256','>2147483646')
            if p.name in ['ia_trace.cpp','ia_graph.cpp','bounded_views.inc']:
                s=s.replace('2000000',CAP)
            if p.name=='ia_trace.cpp':
                s=replace(s,'max_nodes=65536,max_walk=16384','max_nodes='+CAP+',max_walk='+CAP)
                s=s.replace('origins.size()>1024','origins.size()>'+CAP).replace('tail.size()>32','tail.size()>'+CAP)
            if p.name=='ia_graph.cpp':
                s=replace(s,'std::bitset<262145> retired_views;',
                    'struct Retired {std::set<unsigned> ids;bool test(unsigned n)const{return ids.contains(n);}void set(unsigned n){ids.insert(n);}void reset(unsigned n){ids.erase(n);}} retired_views;')
                s=s.replace('>=262144','>='+CAP)
            if p.name=='evidence_store.hpp':
                s=replace(s,'static constexpr size_t descriptor_limit=65536,encoded_byte_limit=64*1024*1024;',
                    'static constexpr size_t descriptor_limit='+CAP+';static constexpr uint64_t encoded_byte_limit=UINT64_MAX;')
                s=replace(s,'size_t encoded_bytes{},cached_uses{};','uint64_t encoded_bytes{};size_t cached_uses{};')
        if p.name=='ui_backend_roots.cpp':s=replace(s,'self->sequence_>=2048','self->sequence_>=UINT64_MAX-1')
        if p.name=='mod_runtime_roots.cpp':s=replace(s,'++budget_>2000','++budget_>4294967294u')
        if p.name=='real_runner.cpp':
            s=replace(s,'ia_incremental_work_limit")()!=10000000','ia_incremental_work_limit")()!=UINT64_MAX')
            s=replace(s,'{"work_limit",10000000}', '{"work_limit",nullptr},{"measurement_only",true},{"work_rejection_disabled",true},{"formal_work_limit",10000000}')
            s=replace(s,'try{\n   context=',
                'Json milestones=Json::array();auto milestone=[&](const char* phase){if(!context)return;auto ledger=Json::parse(symbol<Text>(module,"ia_incremental2_ledger")(context->research_state()));milestones.push_back({{"phase",phase},{"work",ledger.at("used")},{"categories",ledger.at("categories")},{"private_commit_bytes",commit()}});std::cerr<<"MILESTONE "<<milestones.back().dump()<<"\\n"<<std::flush;};\n  try{\n   context=')
            s=replace(s,'std::cerr<<"bootstrap complete\\n"<<std::flush;','milestone("bootstrap");')
            s=replace(s,'std::cerr<<"enums complete\\n"<<std::flush;','milestone("enums");')
            s=replace(s,'for(size_t i=0;i<mods.size();++i)context->load_mod(i);context->check();',
                'for(size_t i=0;i<mods.size();++i){context->load_mod(i);milestone(("mod_"+std::to_string(i)).c_str());}context->check();milestone("initialized");')
            s=replace(s,'item["contract_passed"]=ok;', 'item["contract_passed"]=ok;milestone("contract_checks");')
            s=replace(s,'bool unchanged=true;', 'item["milestones"]=milestones;bool unchanged=true;')
        p.write_text(s,encoding='utf-8')
        if s!=original:changes[p.name]={'before':hashlib.sha256(original.encode()).hexdigest(),'after':digest(p)}
    objs=[FORMAL/'ia_lua533_ui_compact.dir/Release'/(name+'.obj') for name in sorted(names)]
    objs.append(FORMAL/'ia_lua533_ui_compact.dir/Release/managed_heap.obj')
    if not all(p.is_file() for p in objs):raise RuntimeError('Missing formal external C object')
    save(BASE/'preparation.json',{'schema':'compact-sizing-overlay-1','abi':ABI,'changes':changes,'reused_objects':{str(p.relative_to(ROOT)):digest(p) for p in objs},'formal_work_limit':10000000,'work_rejection_disabled':True,'representation_bounds':'32-bit IDs, depth1024, uint64 counters','preserved_guards':{'dll_cpp_heap_bytes':512*1024**2,'child_private_bytes':1024**3,'journal_bytes':4*1024**3,'record_bytes':8*1024**2},'mod_source_modified':False})
    def cm(p):return p.as_posix()
    object_lines='\n'.join('  "'+cm(p)+'"' for p in objs)
    (source/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.24)
project(CompactSizing LANGUAGES CXX)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
 message(FATAL_ERROR "Measurement requires Windows x86")
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
add_compile_options(/W3 /EHsc /utf-8)
add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN)
set(IA_ROOT "'''+cm(ROOT)+'''")
include_directories("${CMAKE_CURRENT_SOURCE_DIR}" "${IA_ROOT}/native" "${IA_ROOT}/third_party" "${IA_ROOT}/incremental_ui_runtime" "${IA_ROOT}/bounded_ui_runtime" "${IA_ROOT}/slice3_ui_runtime" "${IA_ROOT}/incremental2_ui_runtime")
add_library(authority_core STATIC IMPORTED)
set_target_properties(authority_core PROPERTIES IMPORTED_LOCATION "${IA_ROOT}/build-ui-incremental-encoded/Release/authority_core.lib" INTERFACE_LINK_LIBRARIES bcrypt)
add_library(authority_lua_bridge STATIC IMPORTED)
set_target_properties(authority_lua_bridge PROPERTIES IMPORTED_LOCATION "${IA_ROOT}/build-ui-incremental-encoded/Release/authority_lua_bridge.lib" INTERFACE_LINK_LIBRARIES authority_core)
set(EXTERNAL_OBJS
'''+object_lines+'''
)
set_source_files_properties(${EXTERNAL_OBJS} PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)
add_library(ia_lua533_compact_measure SHARED ${EXTERNAL_OBJS} ia_trace.cpp ia_graph.cpp ia_bounded.cpp liveness.cpp)
target_compile_definitions(ia_lua533_compact_measure PRIVATE LUA_BUILD_AS_DLL)
target_link_libraries(ia_lua533_compact_measure PRIVATE authority_core)
add_executable(authority-compact-measure real_runner.cpp private_lua_bridge.cpp ui_backend_roots.cpp mod_runtime_roots.cpp)
target_link_libraries(authority-compact-measure PRIVATE authority_lua_bridge psapi)
target_link_options(authority-compact-measure PRIVATE /STACK:16777216)
''',encoding='utf-8')
    print('Measurement overlay prepared: '+str(BASE),flush=True)

class Memory(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ['peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private']]

def run():
    from audit_baseline import audit
    from inspect_compact_prefix import inspect
    out=ROOT/'reports/compact-completion-measurement';out.mkdir(exist_ok=False)
    before=audit(ROOT.parent/'artifacts/authority-baseline-20261009');save(out/'save-before.json',before)
    binary=BASE/'build/Release';dll=binary/'ia_lua533_compact_measure.dll';exe=binary/'authority-compact-measure.exe'
    command=[str(exe),'--suite',str(dll),digest(dll),str(ROOT),str(ROOT/'research/ui_incremental_suite_10m_v1.json'),'combined-en','trace']
    env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None);env['IA_COMPACT_AUDIT_FILE']=str(out/'combined-en.audit')
    save(out/'invocation.json',{'command':command,'watchdog_seconds':None,'case_runs':1,'formal_work_limit':10000000,'work_rejection_disabled':True,'dll_sha256':digest(dll),'exe_sha256':digest(exe)})
    psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong]
    started=time.perf_counter();peak=0;timed_out=False;last=0
    with (out/'stdout.json').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr,(out/'memory.jsonl').open('x',encoding='utf-8') as samples:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=env)
        while child.poll() is None:
            now=time.perf_counter()-started;m=Memory();m.cb=ctypes.sizeof(m)
            if psapi.GetProcessMemoryInfo(int(child._handle),ctypes.byref(m),m.cb):
                peak=max(peak,m.private);samples.write(json.dumps({'seconds':round(now,3),'private_bytes':m.private,'working_set_bytes':m.working})+'\n');samples.flush()
            if now-last>=15:
                last=now;lines=(out/'stderr.txt').read_text(encoding='utf-8',errors='replace').splitlines()
                print(json.dumps({'seconds':round(now,1),'private_mib':round(m.private/1024**2,2),'last_progress':lines[-1] if lines else None}),flush=True)
            time.sleep(1)
        child.wait()
    elapsed=time.perf_counter()-started
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');save(out/'save-after.json',after)
    lines=(out/'stderr.txt').read_text(encoding='utf-8',errors='replace').splitlines()
    report=None
    if (out/'stdout.json').stat().st_size:
        try:report=json.loads((out/'stdout.json').read_text(encoding='utf-8'))
        except json.JSONDecodeError:pass
    counters=[int(line.split()[1].split('=')[1]) for line in lines if line.startswith('MEASURE work=')]
    journal=out/'combined-en.audit';audit_result=inspect(journal) if journal.exists() else None
    current=protected();saved=json.loads((BASE/'protected-before.json').read_text(encoding='utf-8'))
    unchanged=current==saved
    measured=report.get('case',{}).get('budget',{}).get('used') if report else None
    result={'schema':'compact-completion-sizing-1','measurement_only':True,'case':'combined-en','runs':1,'returncode':child.returncode,'seconds':elapsed,'timed_out':timed_out,'initialization_completed':report.get('case',{}).get('initialization_passed',False) if report else False,'contract_passed':report.get('case',{}).get('contract_passed',False) if report else False,'measured_work':measured,'observed_work_lower_bound':measured if measured is not None else (counters[-1] if counters else 0),'sampled_peak_process_private_bytes':peak,'formal_work_limit':10000000,'formal_files_unchanged':unchanged,'save_files_unchanged':before['files']==after['files'],'audit':audit_result,'stdout_report':'stdout.json','stderr':'stderr.txt','first_unsupported_entry':report.get('case',{}).get('first_unsupported_entry') if report else (lines[-1] if lines else None),'game_started':False,'menu_navigation_tested':False}
    save(out/'result.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
    if not unchanged:raise RuntimeError('Formal protected files changed')

def continue_monitor(parent_pid, child_pid):
    """Keep the existing VM alive while holding its original finite watchdog.

    Only the explicitly identified Python supervisor is suspended. The native
    child keeps its own memory job and audit guard, and is never suspended or
    restarted. Resume the original supervisor on every exit path.
    """
    out=ROOT/'reports/compact-completion-measurement'
    query=f"Get-CimInstance Win32_Process -Filter 'ProcessId = {parent_pid} OR ProcessId = {child_pid}' | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    rows=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',query],encoding='utf-8'))
    by_pid={r['ProcessId']:r for r in rows}
    parent=by_pid[parent_pid];child=by_pid[child_pid]
    expected=BASE/'build/Release/authority-compact-measure.exe'
    if child['ParentProcessId']!=parent_pid or Path(child['ExecutablePath']).resolve()!=expected.resolve():raise RuntimeError('Measurement child identity mismatch')
    if 'measure_compact_completion.py run' not in parent['CommandLine']:raise RuntimeError('Measurement supervisor identity mismatch')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);nt=ctypes.WinDLL('ntdll');psapi=ctypes.WinDLL('psapi')
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    nt.NtSuspendProcess.argtypes=[ctypes.c_void_p];nt.NtSuspendProcess.restype=ctypes.c_long
    nt.NtResumeProcess.argtypes=[ctypes.c_void_p];nt.NtResumeProcess.restype=ctypes.c_long
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong]
    ph=kernel.OpenProcess(0x800|0x1000,False,parent_pid);ch=kernel.OpenProcess(0x100000|0x400|0x10,False,child_pid)
    if not ph or not ch:raise ctypes.WinError(ctypes.get_last_error())
    held=False;peak=0;start=time.perf_counter();last=0;state={'parent_pid':parent_pid,'child_pid':child_pid,'native_vm_restarted':False,'work_limit':None,'original_watchdog_seconds':900,'watchdog_held':False,'resumed':False}
    try:
        if nt.NtSuspendProcess(ph)!=0:raise RuntimeError('Cannot hold measurement supervisor')
        held=True;state['watchdog_held']=True;save(out/'watchdog-continuation.json',state)
        with (out/'memory-continuation.jsonl').open('x',encoding='utf-8') as samples:
            while kernel.WaitForSingleObject(ch,1000)==258:
                elapsed=time.perf_counter()-start;m=Memory();m.cb=ctypes.sizeof(m)
                if psapi.GetProcessMemoryInfo(ch,ctypes.byref(m),m.cb):
                    peak=max(peak,m.private);samples.write(json.dumps({'continuation_seconds':round(elapsed,3),'private_bytes':m.private,'working_set_bytes':m.working})+'\n');samples.flush()
                if elapsed-last>=15:
                    last=elapsed;lines=(out/'stderr.txt').read_text(encoding='utf-8',errors='replace').splitlines()
                    print(json.dumps({'continuation_seconds':round(elapsed,1),'private_mib':round(m.private/1024**2,2),'last_progress':lines[-1] if lines else None}),flush=True)
        state['child_finished']=True
    finally:
        state['sampled_peak_process_private_bytes']=peak;state['continuation_seconds']=time.perf_counter()-start
        if held:state['resumed']=nt.NtResumeProcess(ph)==0
        save(out/'watchdog-continuation.json',state);kernel.CloseHandle(ch);kernel.CloseHandle(ph)
    print(json.dumps(state),flush=True)

def finalize():
    out=ROOT/'reports/compact-completion-measurement'
    result=json.loads((out/'result.json').read_text(encoding='utf-8'))
    continuation=out/'watchdog-continuation.json'
    if continuation.exists():
        c=json.loads(continuation.read_text(encoding='utf-8'))
        if not c.get('resumed') or not c.get('child_finished'):raise RuntimeError('Supervisor handoff not finished')
        result['sampled_peak_process_private_bytes']=max(result['sampled_peak_process_private_bytes'],c['sampled_peak_process_private_bytes'])
        result['fixed_time_cutoff_disabled']=True
        result['native_vm_runs']=1
    prep=json.loads((BASE/'preparation.json').read_text(encoding='utf-8'))
    result['reused_objects_unchanged']=all(digest(ROOT/p)==h for p,h in prep['reused_objects'].items())
    if (out/'stdout.json').stat().st_size:
        native=json.loads((out/'stdout.json').read_text(encoding='utf-8'));case=native['case'];budget=case.get('budget',{})
        result['work_categories_sum_valid']=budget.get('used')==sum(budget.get('categories',{}).values())
        result['milestones']=case.get('milestones',[])
        result['largest_work_categories']=sorted(budget.get('categories',{}).items(),key=lambda v:v[1],reverse=True)[:12]
        result['final_dll_heap']=case.get('storage',{}).get('dll_managed_heap')
        result['world_effects']=case.get('world_effects')
        result['source_unchanged']=case.get('source_unchanged')
        result['exact_initialization_work']=next((m['work'] for m in result['milestones'] if m['phase']=='initialized'),None)
    raw=out/'combined-en.audit';packed=out/'combined-en.audit.gz'
    if raw.exists():
        raw_hash=digest(raw);raw_size=raw.stat().st_size;print('Compressing the single audit, bytes='+str(raw_size),flush=True)
        with raw.open('rb') as src,gzip.open(packed,'xb',compresslevel=1) as dst:shutil.copyfileobj(src,dst,length=1024*1024)
        verified=hashlib.sha256()
        with gzip.open(packed,'rb') as src:
            for chunk in iter(lambda:src.read(1024*1024),b''):verified.update(chunk)
        if verified.hexdigest()!=raw_hash:raise RuntimeError('Compressed audit round-trip mismatch')
        result['audit_transport']={'file':packed.name,'bytes':packed.stat().st_size,'sha256':digest(packed),'uncompressed_sha256':raw_hash,'uncompressed_bytes':raw_size,'round_trip_verified':True,'duplicate_raw_removed':False}
        if not raw.resolve().is_relative_to((ROOT/'reports').resolve()) or raw.parent.resolve()!=out.resolve():raise RuntimeError('Unsafe audit cleanup path')
        raw.unlink();result['audit_transport']['duplicate_raw_removed']=True
    result['formal_files_unchanged']=protected()==json.loads((BASE/'protected-before.json').read_text(encoding='utf-8'))
    save(out/'result.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('step',choices=['prepare','run','continue-monitor','finalize']);parser.add_argument('--parent-pid',type=int);parser.add_argument('--child-pid',type=int);args=parser.parse_args()
    if args.step=='prepare':prepare()
    elif args.step=='run':run()
    elif args.step=='continue-monitor':continue_monitor(args.parent_pid,args.child_pid)
    else:finalize()
