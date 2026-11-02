"""One-off quota-free measurements of the sealed API-boundary prototype.

Only a derived x86 executable is changed. No game is launched, no asset is
copied, and no full-trace runtime is loaded. Deliberate infinite-loop tests
are excluded: they have no finite amount of work to measure.
"""
import argparse
import copy
import ctypes
import gzip
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
import run_font_metrics as fonts
import run_boundary_writes as writes

ROOT = fonts.ROOT
BASE = ROOT / 'build-font-measurement'
GEN = BASE / 'source'
OUT = ROOT / 'reports/font-uncapped-20261016'
EXE = BASE / 'Release/authority-font-measure.exe'
MANIFEST = BASE / 'measurement.json'
ABI = 'ia-lua533-font-measure-1'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def edit(text, before, after, count=1):
    if text.count(before) != count:
        raise RuntimeError('Derivation anchor differs: ' + before[:100])
    return text.replace(before, after)


def protection():
    """Pin sealed inputs, original binaries and all frozen Lua sources."""
    paths = {ROOT / 'ACTIVE_RESEARCH.md', ROOT / 'research/boundary_next.json'}
    pending = [ROOT / 'reports/font-metrics-final.json']
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        paths.add(path)
        record = load(path)
        for group in ['inputs', 'binaries', 'frozen_files', 'imported_libraries']:
            if isinstance(record.get(group), dict):
                for name, expected in record[group].items():
                    p = ROOT / name
                    if isinstance(expected, str) and p.is_file():
                        # Earlier seals can retain superseded failure snapshots.
                        # The current seal was independently verified; older
                        # referenced paths are protected at their current hash.
                        if path == ROOT / 'reports/font-metrics-final.json' and digest(p) != expected:
                            raise RuntimeError('Sealed input differs: ' + name)
                        paths.add(p)
                        if p.suffix == '.json' and 'final' in p.name and p.parent == ROOT / 'reports':
                            pending.append(p)
    paths.update((ROOT / 'research/slice3_ui_inputs').rglob('*.lua'))
    paths.update([fonts.CURRENT, fonts.REAL, writes.MANIFEST, fonts.EXE, fonts.REF])
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def strip_capacities(text):
    """Remove complete resource guards only, after splitting validity checks."""
    edits = []
    for match in re.finditer(r'\bif\(', text):
        depth, end = 1, match.end()
        while depth and end < len(text):
            if text[end] == '(':
                depth += 1
            elif text[end] == ')':
                depth -= 1
            end += 1
        body = re.match(r'\s*throw std::runtime_error\("([^"\n]*capacity exceeded[^"\n]*)"\);', text[end:])
        if body:
            edits.append((match.start(), end + body.end(), text[match.end():end - 1], body[1]))
    for start, end, _, _ in reversed(edits):
        text = text[:start] + text[end:]
    return text, [dict(condition=c, diagnostic=d) for _, _, c, d in edits]


def derive(name, text):
    if name in ['write_barrier.hpp', 'read_extensions.inc']:
        text = edit(text, 'if(key.size()>4096||size>4096)throw std::runtime_error("Consumer external token size exceeded");', '')
    if name == 'boundary.cpp':
        text = edit(text, 'constexpr uint64_t limit=10000000;', 'constexpr uint64_t limit=UINT64_MAX;')
        text = edit(text, '{"limit",limit}', '{"limit",nullptr},{"counter_representation_max",limit}')
        text = edit(text, 'for(int level=0;level<32;++level)', 'for(int level=0;;++level)')
        text = edit(text, 'if(n>262144-data.size())return 1;', '')
        text = edit(text, 'if(depth>24)throw std::runtime_error("JSON depth unsupported");', '', 2)
        text = edit(text, 'if(text.size()>65536||draws.size()>=1024)throw std::runtime_error("Draw queue exceeds contract");', '')
        text = edit(text, 'if(!c.sdk_arguments.is_array()||c.sdk_arguments.size()>16)', 'if(!c.sdk_arguments.is_array())')
        text = edit(text, 'if(manifest.at("work_limit")!=limit||manifest.at("timeout_seconds")!=5)throw std::runtime_error("Formal limits required");',
                    'if(!manifest.at("work_limit").is_null()||!manifest.at("timeout_seconds").is_null()||!manifest.value("measurement_only",false))throw std::runtime_error("Explicit measurement manifest required");')
        start = text.index('    HANDLE job=CreateJobObjectW(')
        end = text.index('\n', start)
        text = text[:start] + '    HANDLE job=nullptr;' + text[end:]
        text = edit(text, 'CloseHandle(job);', 'if(job)CloseHandle(job);')
        flags = '{"measurement_only",true},{"resource_quotas_enabled",false},{"wall_clock_watchdog_seconds",nullptr},{"peak_private_commit_bytes",mem.PeakPagefileUsage}'
        text = edit(text, '{"private_commit_bytes",mem.PrivateUsage}', '{"private_commit_bytes",mem.PrivateUsage},' + flags)
        text = edit(text, '}catch(const std::exception&e){channel.emit(Json',
                    '}catch(const std::exception&e){PROCESS_MEMORY_COUNTERS_EX mem{};mem.cb=sizeof(mem);GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&mem),sizeof(mem));channel.emit(Json')
        text = edit(text, '{"completed",false}', '{"completed",false},' + flags)
        text = text.replace('--font-suite', '--font-measure-suite').replace('ia-lua533-font-metrics-1', ABI)
    elif name == 'write_barrier.hpp':
        text = edit(text, 'if(k.kind==0||(k.kind==2&&k.length>4096))return;', 'if(k.kind==0)return;')
        text = edit(text, '{"read_entry_limit",16384}', '{"read_entry_limit",nullptr}')
    elif name == 'source_capture.cpp':
        text = edit(text, 'void*live[32];int n=ia_source_live_frames(L,live,32);if(n<0)throw std::runtime_error("Source live frame capacity exceeded");',
                    'int n=ia_source_live_frames(L,nullptr,0);std::vector<void*>live(static_cast<size_t>(n));if(ia_source_live_frames(L,live.data(),n)!=n)throw std::runtime_error("Source frame census changed");')
        text = edit(text, 'std::find(live,live+n,i->first)==live+n', 'std::find(live.begin(),live.end(),i->first)==live.end()')
        text = edit(text, '{"original_record_and_byte_caps_preserved",true}', '{"original_record_and_byte_caps_preserved",false}')
    elif name == 'source_bridge.c':
        text = edit(text, 'if(n>=capacity)return -1;frames[n++]=ci;', 'if(frames){if(n>=capacity)return -1;frames[n]=ci;}++n;')
    elif name in ['value_sdk_profile.hpp', 'sdk_profile.hpp']:
        text = edit(text, 'if(!role.is_object()||role.size()>256)', 'if(!role.is_object())')
    elif name == 'context_callbacks.inc':
        # Counters have observable metrics; retain increments when removing guards.
        text = edit(text, 'if(++events>256)throw std::runtime_error("Callback event capacity exceeded");', '++events;')
        text = edit(text, 'if(++entries>256||++total>256)throw std::runtime_error("Callback registry capacity exceeded");', '++entries;++total;')
        text = edit(text, 'if(framework_depth>=32)throw std::runtime_error("Callback forwarding depth exceeded");', '')
    elif name == 'font_profile.hpp':
        text = edit(text, 'if(fonts.size()>=64||a.at("files").empty()||a.at("files").size()>64)throw std::runtime_error("Font resource capacity exceeded");',
                    'if(a.at("files").empty())throw std::runtime_error("Empty Font dependency list");')
        text = edit(text, 'if(!bytes||bytes>4*1024*1024||!files.insert(n).second)throw std::runtime_error("Font dependency capacity exceeded");',
                    'if(!bytes||!files.insert(n).second)throw std::runtime_error("Invalid Font dependency");')
        text = edit(text, 'if(names.empty()||names.size()>64)throw std::runtime_error("Font page capacity exceeded");',
                    'if(names.empty())throw std::runtime_error("Empty Font page list");')
        text = edit(text, 'if(!out.line||out.base>out.line||!pages||pages>64||blocks.at(4).size()/20>65536)throw std::runtime_error("Font metric capacity exceeded");',
                    'if(!out.line||out.base>out.line||!pages)throw std::runtime_error("Invalid Font metrics");')
        text = edit(text, 'page.size()>4096||', '')
        text = edit(text, 'name.empty()||name.size()>4096||', 'name.empty()||')
    elif name == 'graphics_profile.hpp':
        text = edit(text, '||image.at("bytes").get<uint64_t>()>4*1024*1024', '')
    elif name == 'animation_profile.hpp':
        text = edit(text, 'if(!bytes||bytes>4*1024*1024)throw std::runtime_error("Packed proof range capacity exceeded");',
                    'if(!bytes)throw std::runtime_error("Empty packed proof range");')
    return strip_capacities(text)


def prepare():
    before = protection()
    BASE.mkdir(exist_ok=False)
    GEN.mkdir()
    # First include-directory match wins, just as in the sealed CMake project.
    dirs = ['build-font-metrics/generated', 'font_runtime', 'callback_runtime',
            'texture_runtime', 'sprite_state_runtime', 'engine_services_runtime',
            'value_object_runtime', 'sdk_runtime', 'object_runtime', 'module_runtime',
            'compact_value_runtime', 'read_set_runtime']
    inputs = {}
    for folder in dirs:
        for p in (ROOT / folder).iterdir():
            if p.suffix in ['.hpp', '.h', '.inc']:
                inputs.setdefault(p.name, p)
    for name, folder in [('boundary.cpp', dirs[0]), ('write_barrier.cpp', dirs[0]),
                         ('read_hooks.c', dirs[0]), ('source_bridge.c', dirs[0]),
                         ('source_emit.cpp', dirs[0]), ('source_capture.cpp', 'compact_value_runtime')]:
        inputs[name] = ROOT / folder / name
    derived = {}
    for name, p in inputs.items():
        original = p.read_text(encoding='utf-8')
        text, guards = derive(name, original)
        (GEN / name).write_text(text, encoding='utf-8', newline='\n')
        derived[name] = dict(source=p.relative_to(ROOT).as_posix(), source_sha256=digest(p),
                             sha256=digest(GEN / name), modified=text != original,
                             removed_capacity_guards=guards)
    cmake = (ROOT / 'font_runtime/CMakeLists.txt').read_text(encoding='utf-8')
    cmake = cmake.split('target_include_directories(authority-fonts-reference BEFORE')[0]
    cmake = edit(cmake, '${CMAKE_CURRENT_SOURCE_DIR}/..', '${CMAKE_CURRENT_SOURCE_DIR}/../..')
    cmake = edit(cmake, 'set(GEN "${IA_ROOT}/build-font-metrics/generated")', 'set(GEN "${CMAKE_CURRENT_SOURCE_DIR}")')
    cmake = edit(cmake, 'foreach(target authority-fonts authority-fonts-reference)', 'foreach(target authority-fonts)')
    cmake = edit(cmake, '"${IA_ROOT}/compact_value_runtime/source_capture.cpp"', '"${GEN}/source_capture.cpp"')
    cmake = cmake.replace('authority-fonts', 'authority-font-measure').replace('project(FontMetrics', 'project(FontUncappedMeasurement')
    # No PDB or incremental linker cache needed for this measurement executable.
    cmake = cmake.replace(' /Zi', '').replace(' target_link_options(${target} PRIVATE /DEBUG:FULL)', ' target_link_options(${target} PRIVATE /INCREMENTAL:NO)')
    (GEN / 'CMakeLists.txt').write_text(cmake, encoding='utf-8', newline='\n')
    cases = []

    def add(c, group):
        c = copy.deepcopy(c)
        c.update(group=group, original_id=c['id'], id=group + '--' + c['id'])
        cases.append(c)
        return c

    for case in load(fonts.CURRENT)['cases']:
        c = add(case, 'fonts')
        if case['id'] in ['reject-text-cap', 'reject-live-font-cap', 'reject-native-report-cap']:
            c['lifted_quota'] = case['id']
            c.pop('error', None)
            for step in c['steps']:
                step.pop('expect_error', None)
    for case in load(writes.MANIFEST)['cases']:
        if case['id'] == 'work-limit':
            continue
        c = add(case, 'writes')
        if case['id'] == 'field-capacity':
            c['lifted_quota'] = case['id']
            c['steps'][0].pop('expect_error')
    for case in load(ROOT / 'build-current-uncapped/measurement.json')['cases']:
        if case['measurement_group'] == 'stress':
            c = add(case, 'stress')
            c['id'] = case['id']
    for case in load(fonts.REAL)['cases']:
        add(case, 'real')
    spec = dict(schema='font-uncapped-measurement-1', measurement_only=True,
                work_limit=None, timeout_seconds=None, process_memory_limit=None,
                record_caps=None, full_trace_enabled=False, cases=cases,
                excluded=[dict(id='work-limit', reason='deliberate infinite loop has no finite endpoint')])
    save(MANIFEST, spec)
    save(BASE / 'protected-before.json', before)
    save(BASE / 'derivation.json', dict(abi=ABI, prior='research/font_metrics_candidate_v1.json',
         changes=derived, cmake_sha256=digest(GEN / 'CMakeLists.txt'),
         shared_libraries={n: digest(ROOT / n) for n in [
             'build-read-set/Release/read_lua.lib', 'build-boundary/Release/boundary_lua.lib',
             'build-ui-incremental-encoded/Release/authority_core.lib']},
         formal_limits_unchanged=True, lua_rebuilt=False,
         physical_constraints=['Windows x86 address space', 'available system resources',
                              'Lua/C++ representation and stack limits', 'uint64 work counter range']))
    assert before == protection()
    print(json.dumps(dict(prepared=True, cases=len(cases), files=len(derived),
                          removed_guards=sum(len(v['removed_capacity_guards']) for v in derived.values()))))


class Memory(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in ['peak_ws', 'ws', 'peak_paged', 'paged',
        'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private']]


def invoke(case):
    """Observe without timeout, job, output quota or temporary output files."""
    start = time.perf_counter()
    p = subprocess.Popen([str(EXE), '--font-measure-suite', str(ROOT), str(MANIFEST),
                          case['id'], 'boundary'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    buffers = [bytearray(), bytearray()]
    failures = []

    def drain(stream, target):
        try:
            while True:
                data = stream.read(65536)
                if not data:
                    break
                target.extend(data)
        except Exception as e:
            failures.append(repr(e))
        finally:
            stream.close()

    readers = [threading.Thread(target=drain, args=(s, b), daemon=True)
               for s, b in zip([p.stdout, p.stderr], buffers)]
    for t in readers:
        t.start()
    getmem = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    getmem.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    getmem.restype = ctypes.c_int
    peak, samples = 0, []
    next_note = start + 3
    try:
        while p.poll() is None:
            mem = Memory()
            mem.cb = ctypes.sizeof(mem)
            if getmem(int(p._handle), ctypes.byref(mem), mem.cb):
                peak = max(peak, mem.private, mem.peak_pagefile)
            now = time.perf_counter()
            if now >= next_note:
                sample = dict(seconds=now - start, private_bytes=mem.private)
                samples.append(sample)
                print(json.dumps(dict(running=case['id'], **sample)), flush=True)
                next_note = now + 3
            time.sleep(.01)
        p.wait()
    except BaseException:
        p.kill()
        p.wait()
        raise
    finally:
        for t in readers:
            t.join()
    data, error = map(bytes, buffers)
    try:
        report = json.loads(data)
    except ValueError:
        report = None
    return dict(returncode=p.returncode, wall_seconds=time.perf_counter() - start,
                sampled_peak_private_bytes=peak, memory_samples=samples, report=report,
                stdout_bytes=len(data), stdout_sha256=hashlib.sha256(data).hexdigest(),
                invalid_stdout_hex=data.hex() if report is None else None,
                stderr_hex=error.hex(), reader_failures=failures)


def archived(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def run():
    before = load(BASE / 'protected-before.json')
    assert before == protection()
    derivation = load(BASE / 'derivation.json')
    for name, v in derivation['changes'].items():
        assert digest(GEN / name) == v['sha256'] and digest(ROOT / v['source']) == v['source_sha256']
    assert digest(GEN / 'CMakeLists.txt') == derivation['cmake_sha256']
    assert all(digest(ROOT / p) == h for p, h in derivation['shared_libraries'].items())
    cases = load(MANIFEST)['cases']
    baselines = {('fonts', c['id']): c['reports'][1] for c in archived(ROOT / 'reports/font-metrics-v2/result.json.gz')['cases']}
    baselines.update({('real', c['id']): c['reports'][1] for c in archived(ROOT / 'reports/font-metrics-real-v2/result.json.gz')['cases']})
    baselines.update({('stress', c['id']): c['measurement']['report'] for c in archived(ROOT / 'reports/current-uncapped-20261016/result.json.gz')['cases'] if c['group'] == 'stress'})
    OUT.mkdir(exist_ok=False)
    rows = []
    start = time.perf_counter()
    # Real initialization repeats use fresh processes and unchanged frozen inputs.
    jobs = [(c, 1) for c in cases] + [(c, 2) for c in cases if c['group'] == 'real']
    for case, repeat in jobs:
        result = invoke(case)
        r = result['report']
        checks = []

        def check(name, passed):
            checks.append(dict(check=name, passed=bool(passed)))

        check('structured-result', r is not None and not result['reader_failures'])
        if r is not None:
            check('quotas-disabled-and-trace-off', r['measurement_only'] and not r['resource_quotas_enabled']
                  and r['budget']['limit'] is None and not r['full_trace_enabled'] and not r['game_started'])
            check('accounted-work', r['budget']['used'] == sum(r['budget']['categories'].values()))
            if case.get('lifted_quota'):
                check('former-resource-refusal-now-completes', result['returncode'] == 0 and 'semantic' in r)
                if case['lifted_quota'] == 'reject-live-font-cap':
                    check('all-live-fonts-kept', len(r['semantic']['font_states'][1]) == 1026)
                if case['lifted_quota'] == 'field-capacity':
                    check('all-selected-fields-recorded', len(r['steps'][0]['fields']) == 1025)
                if case['lifted_quota'] == 'reject-native-report-cap':
                    check('report-exceeded-formal-cap', result['stdout_bytes'] > 2 * 1024**2)
            elif case['group'] in ['fonts', 'real']:
                b = baselines[case['group'], case['original_id']]
                if 'semantic' in b:
                    check('ordinary-state-and-steps-unchanged', r.get('semantic') == b['semantic'] and r.get('steps') == b['steps'])
                else:
                    check('semantic-refusal-preserved', r.get('first_unsupported_entry') == b.get('first_unsupported_entry'))
                if 'diagnostic_hex' in case:
                    check('raw-diagnostics-unchanged', result['stderr_hex'] == case['diagnostic_hex'])
            elif case['group'] == 'writes':
                check('completed', result['returncode'] == 0 and 'semantic' in r)
                if 'semantic' in r:
                    checks.extend(writes.checks(case, r))
            elif case['group'] == 'stress':
                check('finite-workload-completed', result['returncode'] == 0 and 'semantic' in r)
                check('finite-output-unchanged', r.get('semantic') == baselines['stress', case['original_id']].get('semantic'))
            if repeat == 2:
                first = next(x['measurement']['report'] for x in rows if x['id'] == case['id'])
                check('repeat-same-state-steps-work', all(r.get(k) == first.get(k) for k in ['semantic', 'steps', 'budget']))
        row = dict(id=case['id'], repeat=repeat, group=case['group'], checks=checks,
                   measurement_valid=all(x['passed'] for x in checks),
                   completed=result['returncode'] == 0 and r is not None and 'semantic' in r,
                   measurement=result)
        rows.append(row)
        print(json.dumps(dict(id=row['id'], repeat=repeat, valid=row['measurement_valid'], completed=row['completed'],
              work=(r or {}).get('budget', {}).get('used'), seconds=(r or {}).get('seconds'),
              peak_mib=round(((r or {}).get('peak_private_commit_bytes') or result['sampled_peak_private_bytes']) / 1024**2, 3),
              failure=(r or {}).get('first_unsupported_entry'),
              failed_checks=[x['check'] for x in checks if not x['passed']])), flush=True)
        raw = json.dumps(dict(schema='font-uncapped-result-1', complete=len(rows) == len(jobs), cases=rows),
                         separators=(',', ':')).encode()
        (OUT / 'result.json.gz').write_bytes(gzip.compress(raw, mtime=0))
    assert before == protection()
    assert gzip.decompress((OUT / 'result.json.gz').read_bytes()) == raw
    summary = dict(schema='font-uncapped-summary-1', abi=ABI, cases=len(cases), executions=len(rows),
                   measurement_valid=all(x['measurement_valid'] for x in rows),
                   real_initialization_completed=all(x['completed'] for x in rows if x['group'] == 'real'),
                   formal_files_unchanged=True, game_started=False, full_trace_enabled=False,
                   quotas_enabled=False, seconds=time.perf_counter() - start,
                   binary_sha256=digest(EXE), manifest_sha256=digest(MANIFEST),
                   driver_sha256=digest(Path(__file__)), derivation_sha256=digest(BASE / 'derivation.json'),
                   result_sha256=digest(OUT / 'result.json.gz'), raw_sha256=hashlib.sha256(raw).hexdigest(),
                   stored_bytes=(OUT / 'result.json.gz').stat().st_size)
    save(OUT / 'summary.json', summary)
    print(json.dumps(summary), flush=True)
    return summary['measurement_valid']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'run'])
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare()
    else:
        sys.exit(0 if run() else 1)
