"""Isolated uncapped-work x86 diagnostic. Does not change any acceptance runtime.

No elapsed-time cutoff. Only machine-wide low-memory/low-disk guards can cancel
the child. All semantic/source validation stays enabled. The x86 address space,
uint32 identities and format constraints still apply; these are not infinity.
"""
import argparse
import collections
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import zlib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build-audit-volume-measurement'
GEN = BASE / 'source'
ABI = 'ia-lua533-audit-volume-sizing-1'
U32 = '4294967294u'
MAX64 = (1 << 64) - 1


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def protected():
    folders = ['audit_volume_runtime', 'build-audit-volume/generated',
               'build-audit-volume/Release', 'research/slice3_ui_inputs']
    paths = [p for folder in folders for p in (ROOT / folder).rglob('*') if p.is_file()]
    paths += [ROOT / 'research' / n for n in ['ui_incremental_suite_10m_v1.json',
              'slice3_ui_context.lua', 'slice3_ui_resources.json']]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(paths))}


def prepare():
    BASE.mkdir(exist_ok=False)
    GEN.mkdir()
    save(BASE / 'protected-before.json', protected())
    inputs = {}
    # Small derived runtime sources only: no mod/resource copies or research ZIP.
    for p in (ROOT / 'build-audit-volume/generated').iterdir():
        if p.suffix in ['.h', '.hpp', '.inc', '.cpp']:
            inputs[p.name] = p
    for folder in ['init_profile_runtime', 'consumer_runtime', 'execution_audit_runtime',
                   'incremental_ui_runtime', 'bounded_ui_runtime', 'slice3_ui_runtime',
                   'incremental2_ui_runtime']:
        for p in (ROOT / folder).iterdir():
            if p.suffix in ['.h', '.hpp', '.inc'] and p.name not in inputs:
                inputs[p.name] = p
    inputs['wire_codec.hpp'] = ROOT / 'audit_volume_runtime/wire_codec.hpp'
    inputs['init_profile.cpp'] = ROOT / 'init_profile_runtime/init_profile.cpp'
    inputs['managed_heap.cpp'] = ROOT / 'compact_ui_runtime/managed_heap.cpp'
    changes = {}
    for name, path in inputs.items():
        original = path.read_text(encoding='utf-8')
        s = original.replace('ia-lua533-audit-volume-1', ABI)
        def change(old, new, count=1):
            nonlocal s
            if s.count(old) != count:
                raise RuntimeError(f'Overlay anchor mismatch {name}: {old!r}')
            s = s.replace(old, new)
        if name == 'bounded_cfg.hpp':
            change('constexpr uint64_t work_limit=10000000;', 'constexpr uint64_t work_limit=UINT64_MAX;')
            change('constexpr int block_limit=4096;', 'constexpr int block_limit=2147483646;')
        if name == 'ia_bounded.cpp':
            change('s.codes.size()>=8192', 's.codes.size()>=4294967294u')
            s = s.replace('{"block_limit",4096}', '{"block_limit",ia::bounded::block_limit}')
        if name in ['ia_trace.cpp', 'ia_graph.cpp', 'incremental.inc', 'bounded_views.inc', 'evidence_store.hpp']:
            s = s.replace('depth>24', 'depth>2147483646').replace('depth+memo.height>24', 'depth+memo.height>2147483646')
            s = s.replace('>16384', '>' + U32).replace('>=65536', '>=' + U32).replace('>65536', '>' + U32)
            s = s.replace('>=262144', '>=' + U32)
            if name in ['ia_trace.cpp', 'ia_graph.cpp', 'bounded_views.inc']:
                s = s.replace('2000000u', U32).replace('2000000', U32)
            if name == 'ia_trace.cpp':
                change('max_nodes=65536,max_walk=16384', 'max_nodes=4294967294u,max_walk=4294967294u')
                s = s.replace('origins.size()>1024', 'origins.size()>4294967294u')
                s = s.replace('frames.size()>256', 'frames.size()>4294967294u').replace('tail.size()>32', 'tail.size()>4294967294u')
            if name == 'ia_graph.cpp':
                change('std::bitset<262145> retired_views;',
                       'struct Retired {std::set<unsigned> ids;bool test(unsigned n)const{return ids.contains(n);}void set(unsigned n){ids.insert(n);}void reset(unsigned n){ids.erase(n);}} retired_views;')
            if name == 'evidence_store.hpp':
                change('static constexpr size_t descriptor_limit=65536,encoded_byte_limit=64*1024*1024;',
                       'static constexpr size_t descriptor_limit=4294967294u;static constexpr uint64_t encoded_byte_limit=UINT64_MAX;')
                change('size_t encoded_bytes{},cached_uses{};', 'uint64_t encoded_bytes{};size_t cached_uses{};')
            if name == 'incremental.inc':
                s = s.replace('s.walked-begin,24,', 's.walked-begin,2147483646,').replace('s.walked,24,', 's.walked,2147483646,')
        if name == 'compact_graph.hpp':
            change('512ull*1024*1024-(bytes_-old)', 'uint64_t(SIZE_MAX)-(bytes_-old)')
            change('total>8*1024*1024', 'total>UINT32_MAX-32u')
            change('sites_.size()>=65536', 'sites_.size()>=4294967294u')
        if name == 'managed_heap.cpp':
            change('constexpr size_t limit=512u*1024*1024;', 'constexpr size_t limit=SIZE_MAX;')
            s = s.replace('Compact managed heap limit exceeded (512 MiB)', 'Measurement allocation size overflow (x86 SIZE_MAX)')
        if name == 'audit_journal.hpp':
            change('record_limit=8*1024*1024', 'record_limit=UINT32_MAX-32u')
            change('if(!limit||limit>4ull*1024*1024*1024)', 'if(!limit)')
        if name == 'ui_backend_roots.cpp':
            change('roots_open(s,path,16ull*1024*1024);', 'roots_open(s,path,UINT64_MAX);')
        if name == 'mod_runtime_roots.cpp':
            change('++budget_>2000', '++budget_>4294967294u')
        if name == 'liveness.cpp':
            change('cache.size()>=65536', 'cache.size()>=4294967294u')
            change('seen.size()>4096', 'seen.size()>4294967294u')
        if name == 'resident_evidence.hpp':
            s = s.replace('64u*1024*1024', 'SIZE_MAX')
        if name == 'readsets.inc':
            s = s.replace('>=16384', '>=4294967294u').replace('>=262144', '>=4294967294u')
        if name == 'init_profile.cpp':
            change('p->page->limit=10000000;', 'p->page->limit=UINT64_MAX;')
        if name == 'consumer_real.cpp':
            change('q.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_PROCESS_MEMORY;q.ProcessMemoryLimit=SIZE_T(1024)*1024*1024;',
                   'q.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;')
            # Closing a job containing our own process would terminate before report output.
            s = s.replace('q.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;', 'q.BasicLimitInformation.LimitFlags=0;')
            change('ia_incremental_work_limit")()!=10000000', 'ia_incremental_work_limit")()!=UINT64_MAX')
            change('{"work_limit",10000000}', '{"work_limit",nullptr},{"measurement_only",true},{"formal_work_limit",10000000},{"work_rejection_disabled",true}')
            # Preserve exact work milestones; context->check is not replaced or weakened.
            change('bool ok=true;for(const auto& test:', 'item["initialization_work"]=trace?Json::parse(symbol<Text>(module,"ia_incremental2_ledger")(context->research_state()))["used"]:Json(nullptr);bool ok=true;for(const auto& test:')
        target = GEN / name
        target.write_text(s, encoding='utf-8')
        changes[name] = {'source': path.relative_to(ROOT).as_posix(), 'source_sha256': digest(path),
                         'sha256': digest(target), 'modified': s != original}
    formal = ROOT / 'build-ui-incremental2/compact'
    objects = [formal / 'ia_lua533_ui_compact.dir/Release' / (p.stem + '.obj')
               for p in sorted((formal / 'generated-lua').glob('*.c')) if p.stem not in ['lua', 'luac']]
    if not all(p.is_file() for p in objects):
        raise RuntimeError('Missing preserved Lua ABI objects')
    includes = ['native', 'third_party', 'incremental_ui_runtime', 'bounded_ui_runtime',
                'slice3_ui_runtime', 'incremental2_ui_runtime', 'consumer_runtime', 'execution_audit_runtime']
    cmake = '''cmake_minimum_required(VERSION 3.24)
project(AuditVolumeMeasurement LANGUAGES CXX)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
 message(FATAL_ERROR "Measurement requires Windows x86")
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
add_compile_options(/W3 /EHsc /utf-8)
add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN)
include_directories("${CMAKE_CURRENT_SOURCE_DIR}")
'''
    cmake += '\n'.join(f'include_directories("{(ROOT / d).as_posix()}")' for d in includes) + '\n'
    for name in ['authority_core', 'authority_lua_bridge']:
        cmake += f'add_library({name} STATIC IMPORTED)\nset_target_properties({name} PROPERTIES IMPORTED_LOCATION "{(ROOT / "build-ui-incremental-encoded/Release" / (name + ".lib")).as_posix()}")\n'
    cmake += 'set(EXTERNAL_OBJS\n' + '\n'.join('"' + p.as_posix() + '"' for p in objects) + ')\n'
    cmake += '''set_source_files_properties(${EXTERNAL_OBJS} PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)
add_library(ia_lua533_audit_volume_measure SHARED ${EXTERNAL_OBJS} managed_heap.cpp init_profile.cpp ia_trace.cpp ia_graph.cpp ia_bounded.cpp liveness.cpp)
target_compile_definitions(ia_lua533_audit_volume_measure PRIVATE LUA_BUILD_AS_DLL)
target_link_libraries(ia_lua533_audit_volume_measure PRIVATE authority_core bcrypt)
add_executable(authority-audit-volume-measure consumer_real.cpp private_lua_bridge.cpp ui_backend_roots.cpp mod_runtime_roots.cpp)
target_link_libraries(authority-audit-volume-measure PRIVATE authority_lua_bridge authority_core bcrypt psapi)
target_link_options(authority-audit-volume-measure PRIVATE /LARGEADDRESSAWARE /STACK:16777216)
'''
    (GEN / 'CMakeLists.txt').write_text(cmake, encoding='utf-8')
    save(BASE / 'derivation.json', {'schema': 'audit-volume-unlimited-overlay-1', 'abi': ABI,
         'changes': changes, 'reused_c_objects': {p.relative_to(ROOT).as_posix(): digest(p) for p in objects},
         'formal_work_limit': 10000000, 'formal_timeout_seconds': 5,
         'work_limit': None, 'timeout_seconds': None, 'journal_limit': None,
         'retained_limits': ['x86 address space', 'uint32 IDs and counters', 'uint64 work overflow',
                             'source and format validation', 'semantic rejection', 'bounded evictable consumer caches'],
         'machine_guards': {'minimum_available_ram_bytes': 512 * 1024**2,
                            'minimum_free_disk_bytes': 1024**3}})
    print(json.dumps({'prepared': str(BASE), 'derived_source_bytes': sum(p.stat().st_size for p in GEN.iterdir())}), flush=True)


class Memory(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
        (n, ctypes.c_size_t) for n in ['peak_working', 'working', 'peak_paged', 'paged',
            'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private']]


class GlobalMemory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
        (n, ctypes.c_ulonglong) for n in ['total_phys', 'avail_phys', 'total_page',
                                        'avail_page', 'total_virtual', 'avail_virtual', 'extended']]


def inspect_audit(path):
    """CRC verification in fixed chunks, no expansion/file-size ceiling or DOM."""
    from audit_wire import unpack, RAW, PACKED
    whole = hashlib.sha256()
    counts = collections.Counter()
    n = end = raw_bytes = stored_bytes = packed_count = 0
    error = None
    with path.open('rb') as f:
        while h := f.read(32):
            whole.update(h)
            if len(h) != 32:
                error = 'partial header'; break
            magic, channel, identity, length, seq, crc, hcrc = struct.unpack('<IIIIQII', h)
            if magic not in (RAW, PACKED) or seq != n + 1 or zlib.crc32(h[:28]) != hcrc:
                error = 'invalid header'; break
            left = length; actual = 0; payload = bytearray() if magic == PACKED else None
            while left:
                b = f.read(min(left, 65536))
                if not b:
                    error = 'partial payload'; break
                whole.update(b); actual = zlib.crc32(b, actual); left -= len(b)
                if payload is not None:
                    if length > 256 * 1024:
                        error = 'encoded record exceeds codec representation'; break
                    payload.extend(b)
            if error: break
            if actual != crc:
                error = 'invalid payload CRC'; break
            decoded = unpack(payload) if payload is not None else None
            raw_bytes += len(decoded) if decoded is not None else length
            stored_bytes += length; packed_count += magic == PACKED
            n += 1; counts[str(channel)] += 1; end += 32 + length
        # Include any incomplete tail in the original-file digest.
        while b := f.read(65536): whole.update(b)
    return {'complete_records': n, 'complete_record_bytes': end, 'file_bytes': path.stat().st_size,
            'file_sha256': whole.hexdigest(), 'tail_error': error, 'channels': dict(counts),
            'raw_payload_bytes': raw_bytes, 'stored_payload_bytes': stored_bytes,
            'compressed_records': packed_count, 'streamed_crc_verification': True}


def run(out, cases):
    from init_profile_page import ProfilePage
    from audit_baseline import audit
    out.mkdir(exist_ok=False)
    baseline = ROOT.parent / 'artifacts/authority-baseline-20261009'
    before = audit(baseline); save(out / 'save-before.json', before)
    initial = protected()
    binary = BASE / 'build/Release'
    dll = binary / 'ia_lua533_audit_volume_measure.dll'
    exe = binary / 'authority-audit-volume-measure.exe'
    derivation = json.loads((BASE / 'derivation.json').read_text(encoding='utf-8'))
    if any(digest(GEN / name) != entry['sha256'] for name, entry in derivation['changes'].items()):
        raise RuntimeError('Measurement overlay hash mismatch')
    psapi = ctypes.WinDLL('psapi'); kernel = ctypes.WinDLL('kernel32')
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Memory), ctypes.c_ulong]
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(GlobalMemory)]
    rows = []
    save(out / 'invocation.json', {'measurement_only': True, 'cases': cases, 'watchdog_seconds': None,
         'work_limit': None, 'formal_work_limit': 10000000, 'formal_timeout_seconds': 5,
         'runtime_sha256': digest(dll), 'exe_sha256': digest(exe),
         'derivation_sha256': digest(BASE / 'derivation.json'), 'abi': ABI,
         'machine_low_memory_floor': 512 * 1024**2, 'machine_low_disk_floor': 1024**3,
         'game_started': False})
    for case in cases:
        page = ProfilePage(); journal = out / (case + '.audit')
        env = os.environ.copy()
        for key in ['IA_INCREMENTAL_VERIFY', 'IA_AUDIT_WIRE_RAW', 'IA_AUDIT_IMMEDIATE']:
            env.pop(key, None)
        env['IA_COMPACT_AUDIT_FILE'] = str(journal)
        env['IA_INIT_PROFILE'] = page.name
        command = [str(exe), '--suite', str(dll), digest(dll), str(ROOT),
                   str(ROOT / 'research/ui_incremental_suite_10m_v1.json'), case, 'trace']
        stdout_path = out / (case + '.json'); stderr_path = out / (case + '.stderr.txt')
        start = time.perf_counter(); last_log = -15; peak = 0; reason = None; last = None
        print(json.dumps({'starting': case, 'work_limit': None, 'timeout_seconds': None}), flush=True)
        with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
            child = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr)
            save(out / 'active.json', {'case': case, 'pid': child.pid, 'parent_pid': os.getpid(), 'command': command})
            try:
                while child.poll() is None:
                    elapsed = time.perf_counter() - start
                    sample = page.read()
                    if sample:
                        sample['work_accounting_valid'] = sample['used'] == sum(sample['categories'].values()) and sample['limit'] == MAX64 and not (sample['flags'] & 2)
                        last = sample
                        if not sample['work_accounting_valid']:
                            reason = 'invalid work accounting'; child.kill(); break
                    m = Memory(); m.cb = ctypes.sizeof(m)
                    psapi.GetProcessMemoryInfo(int(child._handle), ctypes.byref(m), m.cb)
                    peak = max(peak, m.private, m.peak_pagefile)
                    g = GlobalMemory(); g.length = ctypes.sizeof(g)
                    if not kernel.GlobalMemoryStatusEx(ctypes.byref(g)):
                        raise ctypes.WinError()
                    disk = shutil.disk_usage(out).free
                    if g.avail_phys < 512 * 1024**2 or disk < 1024**3:
                        reason = 'machine low RAM guard' if g.avail_phys < 512 * 1024**2 else 'machine low disk guard'
                        child.kill(); break
                    if elapsed - last_log >= 15:
                        last_log = elapsed
                        summary = {'case': case, 'seconds': round(elapsed, 2), 'work': sample['used'] if sample else None,
                            'phase': sample['phase'] if sample else None, 'private_mib': round(m.private / 1024**2, 2),
                            'audit_mib': round(journal.stat().st_size / 1024**2, 2) if journal.exists() else 0,
                            'available_ram_mib': round(g.avail_phys / 1024**2, 2)}
                        save(out / 'progress.json', {**summary, 'profile': last})
                        print(json.dumps(summary), flush=True)
                    time.sleep(.25)
                child.wait(timeout=5)
            finally:
                if child.poll() is None:
                    child.kill(); child.wait(timeout=5)
                final = page.read()
                if final:
                    final['work_accounting_valid'] = final['used'] == sum(final['categories'].values()) and final['limit'] == MAX64 and not (final['flags'] & 2)
                    last = final
                page.close()
        elapsed = time.perf_counter() - start
        native = None; parse_error = None
        if stdout_path.stat().st_size:
            try: native = json.loads(stdout_path.read_text(encoding='utf-8'))
            except (ValueError, UnicodeError) as e: parse_error = str(e)
        item = native.get('case', {}) if native else {}
        with stderr_path.open('rb') as f:
            f.seek(max(0, stderr_path.stat().st_size - 8192))
            stderr_tail = f.read().decode('utf-8', errors='replace')
        row = {'id': case, 'seconds': elapsed, 'returncode': child.returncode, 'machine_guard': reason,
            'timed_out': False, 'native_report_parse_error': parse_error,
            'initialization_completed': item.get('initialization_passed', False),
            'contract_passed': item.get('contract_passed', False), 'work': item.get('budget', {}).get('used'),
            'initialization_work': item.get('initialization_work'), 'last_profile': last,
            'sampled_peak_private_bytes': peak, 'first_unsupported_entry': item.get('first_unsupported_entry'),
            'source_unchanged': item.get('source_unchanged'), 'world_effects': item.get('world_effects'),
            'stderr_tail': stderr_tail}
        if last:
            row['observed_work_lower_bound'] = last['used']
        if journal.exists():
            print(json.dumps({'verifying_audit': case, 'file_bytes': journal.stat().st_size}), flush=True)
            try:
                row['audit'] = inspect_audit(journal)
                metrics = item.get('storage', {}).get('journal', {})
                row['audit']['native_frontier_matches'] = (row['audit']['complete_record_bytes'] == metrics.get('durable_bytes')
                    and row['audit']['complete_records'] == metrics.get('durable_records')) if metrics else None
                save(out / (case + '-audit.json'), row['audit'])
                # Exact experiment-owned file only. Preserve the verification/hash instead of gigabytes.
                if journal.resolve().parent != out.resolve(): raise RuntimeError('Unsafe measurement audit path')
                journal.unlink(); row['audit_removed_after_verification'] = True
            except Exception as e:
                row['audit_inspection_error'] = str(e)
        rows.append(row); save(out / 'cases.json', rows)
        print(json.dumps({'finished': case, 'seconds': elapsed, 'returncode': child.returncode,
            'initialization_completed': row['initialization_completed'], 'work': row['work'],
            'observed_work_lower_bound': row.get('observed_work_lower_bound'),
            'first_unsupported_entry': row['first_unsupported_entry'], 'machine_guard': reason}), flush=True)
        if reason: break
    after = audit(baseline); save(out / 'save-after.json', after)
    result = {'schema': 'audit-volume-unlimited-measurement-1', 'measurement_only': True,
        'work_limit': None, 'timeout_seconds': None, 'formal_work_limit': 10000000,
        'formal_timeout_seconds': 5, 'cases': rows,
        'formal_and_frozen_files_unchanged': initial == protected() == json.loads((BASE / 'protected-before.json').read_text()),
        'save_files_unchanged': before['files'] == after['files'],
        'reused_c_objects_unchanged': all(digest(ROOT / p) == h for p, h in json.loads((BASE / 'derivation.json').read_text())['reused_c_objects'].items()),
        'game_started': False, 'formal_acceptance_passed': False}
    save(out / 'result.json', result)
    print(json.dumps({'result': str(out / 'result.json'), 'all_initialized': len(rows) == len(cases) and all(r['initialization_completed'] and r['contract_passed'] for r in rows),
        'protected_unchanged': result['formal_and_frozen_files_unchanged'], 'saves_unchanged': result['save_files_unchanged']}), flush=True)
    if not result['formal_and_frozen_files_unchanged'] or not result['save_files_unchanged']:
        raise RuntimeError('Protected files changed')


def finalize(out):
    """Small summaries only; audited streams have already been verified and removed."""
    report = json.loads((out / 'result.json').read_text(encoding='utf-8'))
    for case in report['cases']:
        path = out / (case['id'] + '.json')
        native = None
        if path.stat().st_size:
            try: native = json.loads(path.read_text(encoding='utf-8'))['case']
            except ValueError: pass
        if native:
            budget = native.get('budget', {})
            case['work_accounting_valid'] = budget.get('used') == sum(budget.get('categories', {}).values())
            case['largest_work_categories'] = sorted(budget.get('categories', {}).items(), key=lambda kv: kv[1], reverse=True)[:12]
            storage = native.get('storage', {}); journal = storage.get('journal', {})
            case['dll_managed_heap'] = storage.get('dll_managed_heap')
            case['execution_audit_reads'] = journal.get('reads')
            case['journal_complete'] = journal.get('complete')
            if 'audit' in case:
                case['audit']['native_frontier_matches'] = (case['audit']['complete_record_bytes'] == journal.get('durable_bytes')
                    and case['audit']['complete_records'] == journal.get('durable_records'))
        case['module_initialization_milestone_seen'] = 'modules complete' in case.get('stderr_tail', '')
        case['completed_native_report'] = native is not None
    failed = [c for c in report['cases'] if not c['initialization_completed'] and c.get('completed_native_report')]
    uses = []
    for c in failed:
        native = json.loads((out / (c['id'] + '.json')).read_text(encoding='utf-8'))['case']
        records = next((r['records'] for r in native['storage']['journal']['volume']['channels'] if r['channel'] == 11), None)
        if records is not None:
            capacity = 0
            while capacity < records:
                capacity = max(capacity + capacity // 2, capacity + 1)
            next_capacity = max(capacity + capacity // 2, records + 1)
            uses.append({'id': c['id'], 'committed_use_records': records, 'msvc_vector_capacity': capacity,
                'next_capacity': next_capacity, 'element_bytes': 24, 'old_buffer_bytes': capacity * 24,
                'next_allocation_bytes': next_capacity * 24,
                'attempted_use_work': native['budget']['categories'].get('incremental_evidence_use'),
                'inference_only_not_allocator_instrumentation': True})
    report['resident_use_growth_analysis'] = uses
    save(out / 'result.json', report)
    lines = ['# Audit volume：取消人工资源配额的单次诊断', '',
        '本轮只运行 Windows x86 命令行初始化，不启动游戏、不修改模组或个人存档。', '',
        '独立 ABI：`' + ABI + '`。诊断 DLL 取消 1000 万工作量、5 秒时限、16 MiB 审计配额、512 MiB DLL 堆和 1 GiB 进程配额；扩大遍历与计数保护到其表示范围。',
        '仍保留来源/资源/操作校验、32 位地址空间、定宽 ID、格式限制及可驱逐缓存。系统剩余内存低于 512 MiB 或磁盘低于 1 GiB 时停止，以免耗尽整机资源。', '',
        '正式运行时及正式 1000 万/5 秒验收保持原样。本结果不是正式门槛通过，也没有验证菜单导航、绘制捕获、世界奖励投影或真实联机。', '',
        '| 案例 | 初始化 | 冻结契约 | 运行秒数 | 完整初始化工作量 | 总工作量 | 私有内存峰值 MiB | 审计 MiB |',
        '|---|---|---|---:|---:|---:|---:|---:|']
    for c in report['cases']:
        lines.append('| ' + ' | '.join([c['id'], '通过' if c['initialization_completed'] else '失败',
            '通过' if c['contract_passed'] else '失败', f"{c['seconds']:.3f}",
            str(c['initialization_work']) if c['initialization_work'] is not None else '未完成',
            str(c['work']), f"{c['sampled_peak_private_bytes']/1024**2:.2f}",
            f"{c.get('audit', {}).get('file_bytes', 0)/1024**2:.2f}"]) + ' |')
    lines += ['', '运行秒数包含加载、契约检查、收尾与原生进程退出；不包含离线逐记录审计核对。初始化工作量在所有模组加载并检查成功后、契约检查前读取。失败项的总工作量只是达到失败点的工作量，不是完整加载需求。', '']
    for c in report['cases']:
        lines += ['## ' + c['id'], '',
            '- 首个失败：`' + str(c['first_unsupported_entry']) + '`',
            '- 机器保护：`' + str(c['machine_guard']) + '`；超时：`' + str(c['timed_out']) + '`。',
            '- 执行期间历史审计回读：`' + str(c.get('execution_audit_reads')) + '`。',
            '- 审计 CRC/解码尾部错误：`' + str(c.get('audit', {}).get('tail_error')) + '`；与原生持久化前沿一致：`' + str(c.get('audit', {}).get('native_frontier_matches')) + '`。',
            '- 审计 SHA256：`' + str(c.get('audit', {}).get('file_sha256')) + '`。大日志已校验并移除：`' + str(c.get('audit_removed_after_verification')) + '`。',
            '- DLL 堆：`' + json.dumps(c.get('dll_managed_heap'), separators=(',', ':')) + '`。', '']
    lines += ['## 常驻记录扩容线索', '',
        '失败两项的 channel 11 均提交 26,906,977 条使用记录，工作量记账均已尝试第 26,906,978 条。`ResidentUses::push_back` 先扩容再写审计，因此失败发生在未提交该条记录之前。',
        '本机 MSVC `<vector>` 的 `_Calculate_growth` 取旧容量加旧容量的一半。24 字节元素从容量 26,906,977 扩到 40,360,465，需要新申请 968,651,160 字节（923.78 MiB）；旧的 645,767,448 字节缓冲在搬移完成前仍占用地址空间。',
        '两次相同记录边界、两单位一次的使用记账、故障位置和当前分配器代码共同强烈支持向量扩容失败。没有新增分配级探针，不能把推算的申请大小写成直接观测值，也不能进一步断言具体地址碎片分布。',
        '分块存储可以减少连续扩容峰值，但仅更换容器仍会保留数千万条历史使用记录，不能解决常驻证据随执行增长的问题。', '',
        '## 保护与复现', '',
        '- 正式代码、二进制与冻结输入不变：`' + str(report['formal_and_frozen_files_unchanged']) + '`。',
        '- 存档审计不变：`' + str(report['save_files_unchanged']) + '`。没有自动恢复或覆盖存档。',
        '- 私有运行时保留 `personal-settings-authority-hud-v1`；本轮初始化不产生世界修改，也不能证明奖励投影功能已通过。',
        '- 入口：`python -B authority/tools/measure_audit_volume_completion.py run --output <新的空结果目录>`。',
        '- 当前派生源码与 CMake 在 `authority/build-audit-volume-measurement/source`；构建 `build` 中的 Release 目标。`derivation.json` 记录来源与派生文件哈希，`invocation.json` 记录实际二进制哈希。',
        '- 不打包或复制模组。日志核对逐记录执行，恒定缓冲；其耗时单独于上述原生运行秒数。', '']
    (ROOT / 'docs/AUDIT_VOLUME_UNLIMITED_RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps([{'id': c['id'], 'seconds': c['seconds'], 'work': c['work'],
        'initialization_work': c['initialization_work'], 'initialized': c['initialization_completed'],
        'contract': c['contract_passed'], 'peak_private_mib': c['sampled_peak_private_bytes'] / 1024**2,
        'unsupported': c['first_unsupported_entry'], 'stderr': c.get('stderr_tail'),
        'audit_bytes': c.get('audit', {}).get('file_bytes')} for c in report['cases']], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'run', 'finalize'])
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/audit-volume-unlimited-v1')
    parser.add_argument('--case', action='append')
    args = parser.parse_args()
    if args.phase == 'prepare': prepare()
    elif args.phase == 'finalize': finalize(args.output.resolve())
    else: run(args.output.resolve(), args.case or ['mcm-zh', 'eid-zh', 'combined-zh'])
