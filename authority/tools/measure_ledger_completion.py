"""Uncapped work diagnostic of the current candidate; formal gates are untouched.

Time, private memory, disk and representation guards are explicit. Cache bounds
and every semantic/source/resource check stay enabled. No game process is used.
"""
import argparse,ctypes,hashlib,json,os,shutil,struct,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import measure_audit_volume_completion as old
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build-ledger-measurement';GEN=BASE/'source'
ABI='ia-lua533-ledger-sizing-1';FORMAL='ia-lua533-ledger-cache-1'
MAX64=(1<<64)-1;U32='4294967294u'
TIMEOUT=120;PROCESS_LIMIT=2*1024**3;AUDIT_LIMIT=1024**3
digest=old.digest;save=old.save

def protected():
    paths=[]
    for folder in ['ledger_cache_runtime','build-ledger-cache/generated','build-ledger-cache/Release','research/slice3_ui_inputs']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file())
    paths.extend(ROOT/'research'/n for n in ['ui_incremental_suite_10m_v1.json','slice3_ui_context.lua','slice3_ui_resources.json'])
    return {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(set(paths))}

def prepare():
    BASE.mkdir(exist_ok=False);GEN.mkdir();save(BASE/'protected-before.json',protected())
    inputs={p.name:p for p in (ROOT/'build-ledger-cache/generated').iterdir() if p.suffix in ['.h','.hpp','.inc','.cpp']}
    for folder in ['init_profile_runtime','consumer_runtime','execution_audit_runtime','incremental_ui_runtime','bounded_ui_runtime','slice3_ui_runtime','incremental2_ui_runtime']:
        for p in (ROOT/folder).iterdir():
            if p.suffix in ['.h','.hpp','.inc'] and p.name not in inputs:inputs[p.name]=p
    inputs['wire_codec.hpp']=ROOT/'audit_volume_runtime/wire_codec.hpp'
    inputs['init_profile.cpp']=ROOT/'init_profile_runtime/init_profile.cpp'
    inputs['managed_heap.cpp']=ROOT/'compact_ui_runtime/managed_heap.cpp'
    changes={}
    for name,path in inputs.items():
        original=path.read_text(encoding='utf-8');s=original.replace(FORMAL,ABI)
        def change(a,b,count=1):
            nonlocal s
            if s.count(a)!=count:raise RuntimeError('Overlay anchor mismatch: '+name+': '+a)
            s=s.replace(a,b)
        if name=='bounded_cfg.hpp':
            change('constexpr uint64_t work_limit=10000000;','constexpr uint64_t work_limit=UINT64_MAX;')
            change('constexpr int block_limit=4096;','constexpr int block_limit=2147483646;')
        if name=='ia_bounded.cpp':
            change('s.codes.size()>=8192','s.codes.size()>=4294967294u')
            s=s.replace('{"block_limit",4096}','{"block_limit",ia::bounded::block_limit}')
        if name in ['ia_trace.cpp','ia_graph.cpp','incremental.inc','bounded_views.inc','evidence_store.hpp']:
            s=s.replace('depth>24','depth>2147483646').replace('depth+memo.height>24','depth+memo.height>2147483646')
            s=s.replace('>16384','>'+U32).replace('>=65536','>='+U32).replace('>65536','>'+U32).replace('>=262144','>='+U32)
            if name in ['ia_trace.cpp','ia_graph.cpp','bounded_views.inc']:s=s.replace('2000000u',U32).replace('2000000',U32)
            if name=='ia_trace.cpp':
                change('max_nodes=65536,max_walk=16384','max_nodes=4294967294u,max_walk=4294967294u')
                s=s.replace('origins.size()>1024','origins.size()>4294967294u').replace('frames.size()>256','frames.size()>4294967294u').replace('tail.size()>32','tail.size()>4294967294u')
            if name=='ia_graph.cpp':
                change('std::bitset<262145> retired_views;','struct Retired {std::set<unsigned> ids;bool test(unsigned n)const{return ids.contains(n);}void set(unsigned n){ids.insert(n);}void reset(unsigned n){ids.erase(n);}} retired_views;')
            if name=='evidence_store.hpp':
                change('static constexpr size_t descriptor_limit=65536,encoded_byte_limit=64*1024*1024;','static constexpr size_t descriptor_limit=4294967294u;static constexpr uint64_t encoded_byte_limit=UINT64_MAX;')
                change('size_t count{},definitions{},encoded_bytes{},cached_uses{},bytes{},peak_bytes{},payload_bytes{},peak_payload{};','uint64_t encoded_bytes{};size_t count{},definitions{},cached_uses{},bytes{},peak_bytes{},payload_bytes{},peak_payload{};')
            if name=='incremental.inc':
                s=s.replace('s.walked-begin,24,','s.walked-begin,2147483646,').replace('s.walked,24,','s.walked,2147483646,')
                s=s.replace('{"descriptor_limit",65536}','{"descriptor_limit",IncEvidenceStore::descriptor_limit}')
        if name=='compact_graph.hpp':
            change('512ull*1024*1024-(bytes_-old)','uint64_t(SIZE_MAX)-(bytes_-old)')
            change('total>8*1024*1024','total>UINT32_MAX-32u')
            change('sites_.size()>=65536','sites_.size()>=4294967294u')
        if name=='managed_heap.cpp':
            change('constexpr size_t limit=512u*1024*1024;','constexpr size_t limit=SIZE_MAX;')
            s=s.replace('Compact managed heap limit exceeded (512 MiB)','Measurement x86 allocation-size overflow')
        if name=='audit_journal.hpp':
            change('record_limit=8*1024*1024','record_limit=UINT32_MAX-32u')
        if name=='ui_backend_roots.cpp':change('roots_open(s,path,16ull*1024*1024);','roots_open(s,path,1024ull*1024*1024);')
        if name=='mod_runtime_roots.cpp':change('++budget_>2000','++budget_>4294967294u')
        if name=='liveness.cpp':
            change('cache.size()>=65536','cache.size()>=4294967294u')
            change('seen.size()>4096','seen.size()>4294967294u')
        if name=='readsets.inc':s=s.replace('>=16384','>=4294967294u').replace('>=262144','>=4294967294u')
        if name=='init_profile.cpp':change('p->page->limit=10000000;','p->page->limit=UINT64_MAX;')
        if name=='consumer_real.cpp':
            change('q.ProcessMemoryLimit=SIZE_T(1024)*1024*1024;','q.ProcessMemoryLimit=SIZE_T(2048)*1024*1024;')
            change('ia_incremental_work_limit")()!=10000000','ia_incremental_work_limit")()!=UINT64_MAX')
            change('{"work_limit",10000000}','{"work_limit",nullptr},{"measurement_only",true},{"formal_work_limit",10000000},{"work_rejection_disabled",true}')
            change('bool ok=true;for(const auto& test:','item["initialization_work"]=trace?Json::parse(symbol<Text>(module,"ia_incremental2_ledger")(context->research_state()))["used"]:Json(nullptr);bool ok=true;for(const auto& test:')
        p=GEN/name;p.write_text(s,encoding='utf-8');changes[name]={'source':path.relative_to(ROOT).as_posix(),'source_sha256':digest(path),'sha256':digest(p),'modified':s!=original}
    formal=ROOT/'build-ui-incremental2/compact'
    objects=[formal/'ia_lua533_ui_compact.dir/Release'/(p.stem+'.obj') for p in sorted((formal/'generated-lua').glob('*.c')) if p.stem not in ['lua','luac']]
    if not all(p.is_file() for p in objects):raise RuntimeError('Missing preserved Lua ABI objects')
    includes=['native','third_party','incremental_ui_runtime','bounded_ui_runtime','slice3_ui_runtime','incremental2_ui_runtime','consumer_runtime','execution_audit_runtime']
    cmake='''cmake_minimum_required(VERSION 3.24)
project(LedgerMeasurement LANGUAGES CXX)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
 message(FATAL_ERROR "Measurement requires Windows x86")
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
add_compile_options(/W3 /EHsc /utf-8)
add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN)
include_directories("${CMAKE_CURRENT_SOURCE_DIR}")
'''
    cmake+='\n'.join(f'include_directories("{(ROOT/d).as_posix()}")' for d in includes)+'\n'
    for name in ['authority_core','authority_lua_bridge']:
        cmake+=f'add_library({name} STATIC IMPORTED)\nset_target_properties({name} PROPERTIES IMPORTED_LOCATION "{(ROOT/"build-ui-incremental-encoded/Release"/(name+".lib")).as_posix()}")\n'
    cmake+='set(EXTERNAL_OBJS\n'+'\n'.join('"'+p.as_posix()+'"' for p in objects)+')\n'
    cmake+='''set_source_files_properties(${EXTERNAL_OBJS} PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)
add_library(ia_lua533_ledger_measure SHARED ${EXTERNAL_OBJS} managed_heap.cpp init_profile.cpp ia_trace.cpp ia_graph.cpp ia_bounded.cpp liveness.cpp)
target_compile_definitions(ia_lua533_ledger_measure PRIVATE LUA_BUILD_AS_DLL)
target_link_libraries(ia_lua533_ledger_measure PRIVATE authority_core bcrypt)
add_executable(authority-ledger-measure consumer_real.cpp private_lua_bridge.cpp ui_backend_roots.cpp mod_runtime_roots.cpp)
target_link_libraries(authority-ledger-measure PRIVATE authority_lua_bridge authority_core bcrypt psapi)
target_link_options(authority-ledger-measure PRIVATE /LARGEADDRESSAWARE /STACK:16777216)
'''
    (GEN/'CMakeLists.txt').write_text(cmake,encoding='utf-8')
    save(BASE/'derivation.json',{'schema':'ledger-unlimited-work-overlay-1','abi':ABI,'formal_work_limit':10000000,'formal_timeout_seconds':5,'work_limit':None,'watchdog_seconds':TIMEOUT,'process_memory_limit':PROCESS_LIMIT,'audit_limit':AUDIT_LIMIT,'evidence_cache_bytes':8388608,'evidence_cache_entries':8192,'changes':changes,'reused_c_objects':{p.relative_to(ROOT).as_posix():digest(p) for p in objects},'remaining_limits':['x86 address space','uint32 identities and event fields','uint64 work count','semantic/source/resource validation','bounded evictable encoding and consumer caches','120 second watchdog','2 GiB process job','1 GiB audit file']})
    print(json.dumps({'prepared':str(BASE),'source_bytes':sum(p.stat().st_size for p in GEN.iterdir())}),flush=True)

def run(out,cases):
    from init_profile_page import ProfilePage
    from audit_baseline import audit
    out.mkdir(exist_ok=False,parents=True);initial=protected();before=audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    derivation=json.loads((BASE/'derivation.json').read_text(encoding='utf-8'))
    for name,entry in derivation['changes'].items():
        if digest(GEN/name)!=entry['sha256']:raise RuntimeError('Overlay hash mismatch '+name)
    if initial!=json.loads((BASE/'protected-before.json').read_text(encoding='utf-8')):raise RuntimeError('Formal baseline changed after overlay creation')
    binary=BASE/'build/Release';dll=binary/'ia_lua533_ledger_measure.dll';exe=binary/'authority-ledger-measure.exe'
    psapi=ctypes.WinDLL('psapi');kernel=ctypes.WinDLL('kernel32')
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(old.Memory),ctypes.c_ulong];kernel.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(old.GlobalMemory)]
    save(out/'invocation.json',{'measurement_only':True,'abi':ABI,'cases':cases,'work_limit':None,'watchdog_seconds':TIMEOUT,'process_memory_limit':PROCESS_LIMIT,'audit_limit':AUDIT_LIMIT,'dll_sha256':digest(dll),'exe_sha256':digest(exe),'derivation_sha256':digest(BASE/'derivation.json'),'tool_sha256':digest(Path(__file__)),'game_started':False})
    rows=[]
    for case in cases:
        page=ProfilePage();journal=out/(case+'.audit');env=os.environ.copy()
        for key in ['IA_INCREMENTAL_VERIFY','IA_CONSUMER_VERIFY','IA_INIT_PRESENCE_VERIFY','IA_LEDGER_VERIFY','IA_LEDGER_LEGACY_LOOKUP','IA_EVIDENCE_KEEP_HISTORY','IA_EVIDENCE_CACHE_BYTES','IA_EVIDENCE_CACHE_ENTRIES','IA_AUDIT_WIRE_RAW','IA_AUDIT_IMMEDIATE','IA_INIT_EVIDENCE_COLLISION']:env.pop(key,None)
        env['IA_INIT_PROFILE']=page.name;env['IA_COMPACT_AUDIT_FILE']=str(journal)
        command=[str(exe),'--suite',str(dll),digest(dll),str(ROOT),str(ROOT/'research/ui_incremental_suite_10m_v1.json'),case,'trace']
        stdout_path=out/(case+'-native.json');stderr_path=out/(case+'.stderr.txt');start=time.perf_counter();last_log=-15;last=None;peak=0;reason=None;points=[]
        print(json.dumps({'starting':case,'work_limit':None,'watchdog_seconds':TIMEOUT}),flush=True)
        with stdout_path.open('xb') as stdout,stderr_path.open('xb') as stderr:
            child=subprocess.Popen(command,env=env,stdout=stdout,stderr=stderr)
            save(out/'active.json',{'case':case,'pid':child.pid,'parent_pid':os.getpid(),'command':command})
            try:
                while child.poll() is None:
                    elapsed=time.perf_counter()-start;sample=page.read()
                    if sample:
                        sample['work_accounting_valid']=sample['used']==sum(sample['categories'].values()) and sample['limit']==MAX64 and not(sample['flags']&2);last=sample
                        if not sample['work_accounting_valid']:reason='invalid work accounting';child.kill();break
                    m=old.Memory();m.cb=ctypes.sizeof(m)
                    if psapi.GetProcessMemoryInfo(int(child._handle),ctypes.byref(m),m.cb):peak=max(peak,m.private,m.peak_pagefile)
                    g=old.GlobalMemory();g.length=ctypes.sizeof(g)
                    if not kernel.GlobalMemoryStatusEx(ctypes.byref(g)):raise ctypes.WinError()
                    if elapsed>=TIMEOUT:reason='120 second watchdog'
                    elif m.private>=PROCESS_LIMIT:reason='2 GiB private memory guard'
                    elif g.avail_phys<1024**3:reason='machine available RAM below 1 GiB'
                    elif shutil.disk_usage(out).free<2*1024**3:reason='machine free disk below 2 GiB'
                    elif journal.exists() and journal.stat().st_size>AUDIT_LIMIT:reason='audit file safety guard'
                    elif stdout_path.stat().st_size>1024**2 or stderr_path.stat().st_size>65536:reason='bounded diagnostic output guard'
                    if reason:child.kill();break
                    if elapsed-last_log>=15:
                        last_log=elapsed;summary={'case':case,'seconds':round(elapsed,2),'work':sample['used'] if sample else None,'phase':sample['phase'] if sample else None,'private_mib':round(m.private/1024**2,2),'audit_mib':round(journal.stat().st_size/1024**2,2) if journal.exists() else 0}
                        points.append(summary);save(out/'progress.json',{**summary,'profile':last});print(json.dumps(summary),flush=True)
                    time.sleep(.2)
                child.wait(timeout=5)
            finally:
                if child.poll() is None:child.kill();child.wait(timeout=5)
                final=page.read()
                if final:
                    final['work_accounting_valid']=final['used']==sum(final['categories'].values()) and final['limit']==MAX64 and not(final['flags']&2);last=final
                page.close()
        elapsed=time.perf_counter()-start;native=None;parse_error=None
        if stdout_path.stat().st_size:
            try:native=json.loads(stdout_path.read_text(encoding='utf-8'))
            except (ValueError,UnicodeError) as error:parse_error=str(error)
        item=native.get('case',{}) if native else {};budget=item.get('budget',{})
        with stderr_path.open('rb') as f:f.seek(max(0,stderr_path.stat().st_size-8192));stderr_tail=f.read().decode('utf-8',errors='replace')
        row={'id':case,'seconds':elapsed,'returncode':child.returncode,'guard':reason,'initialization_completed':item.get('initialization_passed',False),'contract_passed':item.get('contract_passed',False),'initialization_work':item.get('initialization_work'),'total_work':budget.get('used'),'observed_work_lower_bound':(last or {}).get('used'),'last_profile':last,'sampled_peak_private_bytes':peak,'first_unsupported_entry':item.get('first_unsupported_entry'),'stderr_tail':stderr_tail,'native_report_parse_error':parse_error,'progress':points,'world_effects':item.get('world_effects'),'evidence_lifetime':item.get('evidence_lifetime'),'dll_managed_heap':item.get('storage',{}).get('dll_managed_heap'),'execution_audit_reads':item.get('storage',{}).get('journal',{}).get('reads'),'work_accounting_valid':budget.get('used')==sum(budget.get('categories',{}).values()) if budget else (last or {}).get('work_accounting_valid'),'largest_work_categories':sorted(budget.get('categories',(last or {}).get('categories',{})).items(),key=lambda p:-p[1])[:16]}
        if journal.exists():
            print(json.dumps({'verifying_audit':case,'bytes':journal.stat().st_size}),flush=True);row['audit']=old.inspect_audit(journal)
            metrics=item.get('storage',{}).get('journal',{});row['audit']['native_frontier_matches']=(row['audit']['complete_record_bytes']==metrics.get('durable_bytes') and row['audit']['complete_records']==metrics.get('durable_records')) if metrics else None
            if journal.is_symlink() or journal.resolve().parent!=out.resolve():raise RuntimeError('Unsafe measurement audit path')
            journal.unlink();row['audit_removed_after_verification']=True
        rows.append(row);save(out/'cases.json',rows)
        print(json.dumps({'finished':case,'seconds':elapsed,'initialized':row['initialization_completed'],'initialization_work':row['initialization_work'],'total_work':row['total_work'],'lower_bound':row['observed_work_lower_bound'],'guard':reason,'unsupported':row['first_unsupported_entry']}),flush=True)
        if reason and ('machine' in reason or 'invalid' in reason):break
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    result={'schema':'ledger-unlimited-work-measurement-1','measurement_only':True,'work_limit':None,'watchdog_seconds':TIMEOUT,'process_memory_limit':PROCESS_LIMIT,'audit_limit':AUDIT_LIMIT,'formal_work_limit':10000000,'formal_timeout_seconds':5,'cases':rows,'formal_and_frozen_files_unchanged':initial==protected(),'save_files_unchanged':before['files']==after['files'],'save_audit_before':before,'save_audit_after':after,'reused_c_objects_unchanged':all(digest(ROOT/p)==h for p,h in derivation['reused_c_objects'].items()),'game_started':False,'formal_acceptance_passed':False}
    save(out/'result.json',result)
    for name in ['active.json','progress.json','cases.json']:
        p=out/name
        if p.exists():p.unlink()
    assert result['formal_and_frozen_files_unchanged'] and result['save_files_unchanged'] and result['reused_c_objects_unchanged']
    print(json.dumps({'result':str(out/'result.json'),'all_initialized':len(rows)==len(cases) and all(r['initialization_completed'] and r['contract_passed'] for r in rows),'protected_unchanged':True,'saves_unchanged':True}),flush=True)

def finalize(out):
    path=out/'result.json';r=json.loads(path.read_text(encoding='utf-8'))
    assert r['formal_and_frozen_files_unchanged'] and r['save_files_unchanged'] and r['reused_c_objects_unchanged']
    assert protected()==json.loads((BASE/'protected-before.json').read_text(encoding='utf-8'))
    for c in r['cases']:
        assert c['work_accounting_valid']
        assert c['audit_removed_after_verification'] and not (out/(c['id']+'.audit')).exists()
        native_path=out/(c['id']+'-native.json');c['native_output_bytes']=native_path.stat().st_size;c['completed_native_report']=c['native_output_bytes']>0
        if c['initialization_completed']:
            assert c['initialization_work'] is not None and c['initialization_work']<=c['total_work']
            assert c['contract_passed'] and c['audit']['native_frontier_matches'] and c['audit']['tail_error'] is None
            assert c['world_effects']==[] and c['execution_audit_reads']==0
            life=c['evidence_lifetime'];assert not life['keep_history'] and life['resident_use_slots']<=1 and life['accounted_resident_bytes']<=8388608 and life['resident_entries']<=8192
    binaries={p.name:digest(p) for p in (BASE/'build/Release').iterdir() if p.suffix in ['.exe','.dll','.lib']}
    cleanup=[];build=(BASE/'build').resolve()
    assert build==Path('D:/Coding/ISAAC/authority/build-ledger-measurement/build').resolve()
    for p in build.rglob('*'):
        if p.is_file() and p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk']:
            assert not p.is_symlink() and p.resolve().is_relative_to(build)
            cleanup.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p),'basis':'regenerable private measurement C++ objects; imported formal Lua objects are outside this directory'})
    for c in r['cases']:
        native_path=out/(c['id']+'-native.json');stderr_path=out/(c['id']+'.stderr.txt')
        if not c['native_output_bytes']:cleanup.append({'path':native_path.relative_to(ROOT).as_posix(),'bytes':0,'sha256':digest(native_path),'basis':'empty native capture recorded explicitly in completed result'})
        if stderr_path.read_bytes()==c['stderr_tail'].encode('utf-8'):
            cleanup.append({'path':stderr_path.relative_to(ROOT).as_posix(),'bytes':stderr_path.stat().st_size,'sha256':digest(stderr_path),'basis':'exact full stderr bytes retained as stderr_tail in completed result'})
    for entry in cleanup:
        p=ROOT/entry['path'];assert digest(p)==entry['sha256'];p.unlink()
    assert binaries=={p.name:digest(p) for p in (BASE/'build/Release').iterdir() if p.suffix in ['.exe','.dll','.lib']}
    r['binary_sha256']=binaries;r['cleanup']={'files':cleanup,'released_bytes':sum(c['bytes'] for c in cleanup),'audit_bytes_removed':sum(c['audit']['file_bytes'] for c in r['cases']),'remaining_audits':0}
    r['inputs']={'tools/measure_ledger_completion.py':digest(Path(__file__)),'build-ledger-measurement/derivation.json':digest(BASE/'derivation.json'),'research/ui_incremental_suite_10m_v1.json':digest(ROOT/'research/ui_incremental_suite_10m_v1.json')}
    save(path,r)
    lines=['# 当前运行时：取消工作量上限的临时测量','',
        '本轮取消计数和相关遍历上限，沿用当前紧凑证据和记账缓存。正式 1000 万上限、5 秒验收没有修改。Windows x86，仅命令行；没有启动游戏、修改旧模组或个人存档。','',
        '本次不是无限资源运行：每项最多 120 秒，2 GiB 进程内存、1 GiB 审计文件；系统可用 RAM 低于 1 GiB、磁盘低于 2 GiB 时停止。32 位表示范围、来源/语义/资源校验、8 MiB/8192 项证据缓存及其他可驱逐缓存仍保留。','',
        '| 案例 | 初始化/契约 | 完整初始化工作量 | 含检查收尾总量 | 原生进程秒 | 私有内存峰值 MiB |','|---|---|---:|---:|---:|---:|']
    for c in r['cases']:
        complete=c['initialization_completed'] and c['contract_passed']
        lines.append(f"| {c['id']} | {'通过' if complete else '未完成'} | {c['initialization_work'] if complete else '未测到'} | {c['total_work'] if c['total_work'] is not None else '至少 '+str(c['observed_work_lower_bound'])} | {c['seconds']:.3f} | {c['sampled_peak_private_bytes']/1024**2:.2f} |")
    lines+=['','初始化工作量在真实模组加载、检查成功后且契约检查前读取；总量包含契约、根检查和收尾。秒数含加载、检查和进程退出，不含离线审计核验。峰值来自进程内存查询，完整运行另保留 DLL 堆和有界缓存统计。',
        '未完成项的观测值只是下限，不能外推完整需求。由于缓存容量和内存保护仍存在，不能把本次结果称为无限内存实验，也不能当作正式门槛通过。','']
    for c in r['cases']:
        lines += ['## '+c['id'],'',f"- 停止原因：{c['guard'] or c['first_unsupported_entry'] or '正常完成'}。",f"- 最后有效工作量：{c['observed_work_lower_bound']}；采样记账校验：{c['work_accounting_valid']}。",f"- 审计：{c['audit']['file_bytes']} 字节，SHA256 `{c['audit']['file_sha256']}`；尾部：{c['audit']['tail_error']}；原生持久化前沿一致：{c['audit']['native_frontier_matches']}。",'- 审计原文件已核验删除；完整收费分类、阶段与内存采样保留在结果 JSON。','']
    lines+=['## 保留与复现','',
        f"正式源码/二进制、冻结模组和个人存档哈希不变。清理本测量构建中间文件 {r['cleanup']['released_bytes']} 字节，保留测量二进制、派生源码和哈希；没有 ZIP 或模组副本。",
        '独立 ABI：`'+ABI+'`。`authority/build-ledger-measurement/derivation.json` 逐文件记录派生差异与沿用的正式 Lua C ABI 对象。',
        '入口：`python -B authority/tools/measure_ledger_completion.py run --output <新的空目录>`；使用固定冻结清单，不依赖游戏进程。当前结果：`authority/reports/ledger-unlimited-v1/result.json`。']
    doc=ROOT/'docs/LEDGER_UNLIMITED_RESULTS.md';doc.write_text('\n'.join(lines)+'\n',encoding='utf-8');r['inputs'][doc.relative_to(ROOT).as_posix()]=digest(doc);save(path,r)
    print(json.dumps({'cases':[{'id':c['id'],'initialized':c['initialization_completed'],'initialization_work':c['initialization_work'],'total_work':c['total_work'],'lower_bound':c['observed_work_lower_bound'],'seconds':c['seconds'],'guard':c['guard'],'unsupported':c['first_unsupported_entry']} for c in r['cases']],'cleanup_bytes':r['cleanup']['released_bytes'],'protected_unchanged':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','run','finalize']);p.add_argument('--output',type=Path,default=ROOT/'reports/ledger-unlimited-v1');p.add_argument('--case',action='append');a=p.parse_args()
    if a.phase=='prepare':prepare()
    elif a.phase=='finalize':finalize(a.output.resolve())
    else:run(a.output.resolve(),a.case or ['mcm-zh','eid-zh','combined-zh'])
