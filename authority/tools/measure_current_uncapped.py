"""One-off uncapped measurement of the sealed compact/frozen-module runtime.

Only the derived executable loses resource quotas. Semantic refusals, x86 Lua,
frozen source checks and authority permissions stay enabled. No game SDK stubs.
Intentionally nonterminating quota tests are excluded, not declared passed.
"""
import argparse, copy, ctypes, gzip, hashlib, json, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
import run_frozen_modules as m
import verify_frozen_modules

ROOT = m.ROOT
BASE = ROOT / 'build-current-uncapped'
GEN = BASE / 'source'
EXE = BASE / 'Release/authority-current-measure.exe'
MANIFEST = BASE / 'measurement.json'
OUT = ROOT / 'reports/current-uncapped-20261016'
ABI = 'ia-lua533-current-measure-1'
old = m.old

def load(p):
    return json.loads(p.read_text(encoding='utf-8'))

def edit(s, a, b, count=1):
    if s.count(a) != count:
        raise RuntimeError('Measurement derivation anchor: ' + a[:100])
    return s.replace(a, b)

def protected():
    result = m.protected()
    v = load(ROOT / 'reports/frozen-modules-final.json')
    for group in ['inputs', 'binaries', 'frozen_files']:
        for name, h in v[group].items():
            assert old.digest(ROOT / name) == h, name
            result[name] = h
    for name in ['ACTIVE_RESEARCH.md', 'research/boundary_next.json', 'reports/frozen-modules-final.json']:
        result[name] = old.digest(ROOT / name)
    return result

def prepare():
    verify_frozen_modules.main()
    before = protected()
    BASE.mkdir(exist_ok=False)
    GEN.mkdir()
    inputs = {p.name: p for p in (ROOT / 'build-frozen-module/generated').iterdir()
              if p.suffix in ['.cpp', '.hpp', '.c', '.h']}
    for name in ['source_capture.cpp', 'source_capture.hpp']:
        inputs[name] = ROOT / 'compact_value_runtime' / name
    for name in ['frozen_modules.hpp', 'context_modules.inc']:
        inputs[name] = ROOT / 'module_runtime' / name
    changes = {}
    for name, path in inputs.items():
        original = path.read_text(encoding='utf-8')
        s = original
        if name == 'boundary.cpp':
            s = edit(s, 'constexpr uint64_t limit=10000000;', 'constexpr uint64_t limit=UINT64_MAX;')
            s = edit(s, '{"limit",limit}', '{"limit",nullptr},{"counter_representation_max",limit}')
            guards = [('prototypes.size()>=1024','Prototype metadata capacity exceeded',1),
                      ('cells.size()>=1024','Upvalue metadata capacity exceeded',2),
                      ('fields.size()>=1024','Field observation capacity exceeded',1),
                      ('callbacks.size()>=256','Callback registry capacity exceeded',1),
                      ('draw_sites.size()>=128','Draw plan site capacity exceeded',1),
                      ('draw_prototypes.size()>=64||dumped.size()>524288-draw_prototype_bytes','Draw prototype pool capacity exceeded',1),
                      ('depth>24','JSON depth unsupported',2),
                      ('text.size()>65536||draws.size()>=1024','Draw queue exceeds contract',1)]
            for condition, message, count in guards:
                s = edit(s, f'if({condition})throw std::runtime_error("{message}");', '', count)
            s = edit(s, 'for(int level=0;level<32;++level)', 'for(int level=0;;++level)')
            s = edit(s, 'if(n>262144-data.size())return 1;', '')
            s = edit(s, 'if(manifest.at("work_limit")!=limit||manifest.at("timeout_seconds")!=5)throw std::runtime_error("Formal limits required");',
                     'if(!manifest.at("work_limit").is_null()||!manifest.at("timeout_seconds").is_null()||!manifest.value("measurement_only",false))throw std::runtime_error("Explicit uncapped manifest required");')
            start = s.index('    HANDLE job=CreateJobObjectW(')
            end = s.index('\n', start)
            s = s[:start] + '    HANDLE job=nullptr;' + s[end:]
            s = edit(s, '{"private_commit_bytes",mem.PrivateUsage}', '{"private_commit_bytes",mem.PrivateUsage},{"peak_private_commit_bytes",mem.PeakPagefileUsage},{"measurement_only",true},{"resource_quotas_enabled",false},{"wall_clock_watchdog_seconds",nullptr}')
            s = edit(s, '}catch(const std::exception&e){std::cout<<Json',
                     '}catch(const std::exception&e){PROCESS_MEMORY_COUNTERS_EX mem{};mem.cb=sizeof(mem);GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&mem),sizeof(mem));std::cout<<Json')
            s = edit(s, '{"completed",false}', '{"completed",false},{"measurement_only",true},{"resource_quotas_enabled",false},{"peak_private_commit_bytes",mem.PeakPagefileUsage}')
            s = edit(s, 'CloseHandle(job);', 'if(job)CloseHandle(job);')
            s = s.replace('--module-suite', '--current-measure-suite').replace('ia-lua533-frozen-modules-1', ABI)
        elif name == 'write_barrier.hpp':
            guards = [('cells.size()>=1024','Write cell capacity exceeded'),
                      ('key.text.size()>4096','Write field key capacity exceeded'),
                      ('tables.size()>=1024','Write table capacity exceeded'),
                      ('field_count>=1024','Write field capacity exceeded'),
                      ('!consumers.count(id)&&consumers.size()>=256','Consumer capacity exceeded'),
                      ('tables.size()>=1024','Read table capacity exceeded'),
                      ('pending->deps.size()>=1024','Consumer dependency capacity exceeded'),
                      ('live_read_entries>=16384','Consumer total read entry capacity exceeded'),
                      ('source.length>4096','Read key capacity exceeded'),
                      ('key.size()>4096||size>4096','Consumer external token size exceeded'),
                      ('pending->external.size()>=1024','Consumer external dependency capacity exceeded')]
            for condition, message in guards:
                s = edit(s, f'if({condition})throw std::runtime_error("{message}");', '', 2 if condition=='live_read_entries>=16384' else 1)
            s = edit(s, 'if(k.kind==0||(k.kind==2&&k.length>4096))return;', 'if(k.kind==0)return;')
            s = edit(s, '{"read_entry_limit",16384}', '{"read_entry_limit",nullptr}')
        elif name == 'source_capture.cpp':
            s = edit(s, 'void*live[32];int n=ia_source_live_frames(L,live,32);if(n<0)throw std::runtime_error("Source live frame capacity exceeded");',
                     'int n=ia_source_live_frames(L,nullptr,0);std::vector<void*>live(static_cast<size_t>(n));if(ia_source_live_frames(L,live.data(),n)!=n)throw std::runtime_error("Source frame census changed");')
            s = edit(s, 'std::find(live,live+n,i->first)==live+n', 'std::find(live.begin(),live.end(),i->first)==live.end()')
            for condition, message, count in [('v.length>65536','Source scalar byte capacity exceeded',1),
                      ('frames.size()>=32&&!frames.count(i.frame)','Source live frame capacity exceeded',1),
                      ('stats->records>=4096||bytes>262144-stats->bytes','Source observation capacity exceeded',2),
                      ('sites.size()>=128||entries>16384-snapshot_entries','Source draw snapshot capacity exceeded',1)]:
                s = edit(s, f'if({condition})throw std::runtime_error("{message}");', '', count)
            s = edit(s, '{"original_record_and_byte_caps_preserved",true}', '{"original_record_and_byte_caps_preserved",false}')
        elif name == 'source_bridge.c':
            s = edit(s, 'if(n>=capacity)return -1;frames[n++]=ci;', 'if(frames){if(n>=capacity)return -1;frames[n]=ci;}++n;')
        elif name == 'frozen_modules.hpp':
            for condition in ['bytes>4*1024*1024||file_count>=4096||bytes>32*1024*1024-source_bytes',
                              'bytes>4*1024*1024||bytes>32*1024*1024-source_bytes']:
                s = edit(s, f'if({condition})throw std::runtime_error("Frozen module source capacity exceeded");', '')
        target = GEN / name
        target.write_text(s, encoding='utf-8', newline='\n')
        changes[name] = dict(source=path.relative_to(ROOT).as_posix(), source_sha256=old.digest(path), sha256=old.digest(target), modified=s!=original)
    cmake = (ROOT / 'module_runtime/CMakeLists.txt').read_text(encoding='utf-8')
    cmake = cmake.split('target_link_libraries(authority-modules PRIVATE fixed_lua)')[0] + '\ntarget_link_libraries(authority-modules PRIVATE fixed_lua)\n'
    cmake = edit(cmake, '${CMAKE_CURRENT_SOURCE_DIR}/..', '${CMAKE_CURRENT_SOURCE_DIR}/../..')
    cmake = edit(cmake, 'set(GEN "${IA_ROOT}/build-frozen-module/generated")', 'set(GEN "${CMAKE_CURRENT_SOURCE_DIR}")')
    cmake = edit(cmake, 'foreach(target authority-modules authority-modules-reference)', 'foreach(target authority-modules)')
    cmake = edit(cmake, '"${IA_ROOT}/compact_value_runtime/source_capture.cpp"', '"${GEN}/source_capture.cpp"')
    cmake = cmake.replace('authority-modules', 'authority-current-measure').replace('project(FrozenModuleBridge', 'project(CurrentUncappedMeasurement')
    (GEN / 'CMakeLists.txt').write_text(cmake, encoding='utf-8', newline='\n')
    cases = []
    def add(c, group):
        c = copy.deepcopy(c)
        c.update(id=group+'--'+c['id'], original_id=c['id'], measurement_group=group)
        if c.get('kind') == 'native-rejection':
            for step in c['steps']:
                step.pop('expect_error', None)
        cases.append(c)
    for c in load(ROOT / 'research/compact_values_v1.json')['cases']:
        add(c, 'compact')
    for c in load(m.MANIFEST)['cases']:
        if c['id'] != 'module-work-cap':
            add(c, 'modules')
    prior = load(ROOT / 'build-bound-measurement/measurement.json')
    for c in prior['cases']:
        if c['measurement_group'] == 'finite-stress':
            add(c, 'stress')
    c = copy.deepcopy(next(c for c in cases if c['id']=='stress--million-reads'))
    c.update(id='stress--million-reads-no-values', original_id='million-reads-no-values')
    c['steps'] = [dict(op='capture_reads', event=2, phase='presentation', input={})]
    cases.append(c)
    for c in load(m.REAL)['cases']:
        add(c, 'real')
    manifest = dict(schema='current-uncapped-measurement-1', measurement_only=True,
                    work_limit=None, timeout_seconds=None, process_memory_limit=None,
                    record_caps=None, full_trace_enabled=False, cases=cases,
                    excluded=[dict(suite=m.MANIFEST.relative_to(ROOT).as_posix(), id='module-work-cap', reason='deliberate infinite loop has no terminating uncapped measurement')])
    old.save(MANIFEST, manifest)
    control = copy.deepcopy(manifest)
    control.update(measurement_only=False, work_limit=10000000, timeout_seconds=5)
    old.save(BASE / 'formal-control.json', control)
    old.save(BASE / 'protected-before.json', before)
    old.save(BASE / 'derivation.json', dict(abi=ABI, changes=changes, cmake_sha256=old.digest(GEN/'CMakeLists.txt'),
        prior_final_sha256=old.digest(ROOT/'reports/frozen-modules-final.json'), lua_rebuilt=False,
        lua_sha256=old.digest(ROOT/'build-read-set/Release/read_lua.lib'), semantic_checks_preserved=True))
    assert before == protected()
    print(json.dumps(dict(prepared=True, cases=len(cases), quotas=None)))

class Memory(ctypes.Structure):
    _fields_ = [('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)] + [(n,ctypes.c_size_t) for n in ['peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private']]

def invoke(c, formal=False):
    exe = m.EXE if formal else EXE
    manifest = BASE / 'formal-control.json' if formal else MANIFEST
    start = time.perf_counter()
    samples = []
    peak = 0
    timed_out = False
    getmem = ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
    getmem.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
    getmem.restype = ctypes.c_int
    # Files avoid a pipe deadlock with a large final report; only one pair exists.
    raw = OUT / 'current.stdout.tmp'
    err = OUT / 'current.stderr.tmp'
    with raw.open('xb') as stdout, err.open('xb') as stderr:
        child = subprocess.Popen([str(exe),'--module-suite' if formal else '--current-measure-suite',str(ROOT),str(manifest),c['id'],'boundary'], stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            next_note = start+3
            while child.poll() is None:
                mem = Memory(); mem.cb = ctypes.sizeof(mem)
                if getmem(int(child._handle),ctypes.byref(mem),mem.cb):
                    peak = max(peak,mem.private,mem.peak_pagefile)
                now = time.perf_counter()
                if formal and now-start >= 5:
                    timed_out=True; child.kill(); break
                if now >= next_note:
                    samples.append(dict(seconds=now-start,private_bytes=mem.private))
                    print(json.dumps(dict(running=c['id'],formal=formal,seconds=round(now-start,2),private_mib=round(mem.private/1024**2,2))),flush=True)
                    next_note = now+3
                time.sleep(.025)
        except BaseException:
            child.kill(); child.wait(); raise
        child.wait()
    data, errors = raw.read_bytes(), err.read_bytes()
    try:
        report = json.loads(data)
    except ValueError:
        report = None
    result = dict(returncode=child.returncode,timed_out=timed_out,wall_seconds=time.perf_counter()-start,
        sampled_peak_private_bytes=peak,memory_samples=samples,report=report,
        stderr=errors.decode('utf-8',errors='replace'),stdout_sha256=hashlib.sha256(data).hexdigest(),stdout_bytes=len(data),
        invalid_stdout_hex=data.hex() if report is None else None,stderr_sha256=hashlib.sha256(errors).hexdigest())
    raw.unlink(); err.unlink()
    return result

def archived(path):
    return json.loads(gzip.decompress(path.read_bytes()))

def run():
    before = load(BASE / 'protected-before.json')
    assert before == protected()
    d = load(BASE / 'derivation.json')
    for name, v in d['changes'].items():
        assert old.digest(GEN/name)==v['sha256'] and old.digest(ROOT/v['source'])==v['source_sha256']
    assert old.digest(GEN/'CMakeLists.txt')==d['cmake_sha256']
    assert old.digest(ROOT/'build-read-set/Release/read_lua.lib')==d['lua_sha256']
    spec = load(MANIFEST)
    for c in spec['cases']:
        assert old.digest(ROOT/c['source']) == c['source_sha256']
    baselines = {
        'compact': {c['id']:c['reports'][1] for c in archived(ROOT/'reports/compact-values-v3/result.json.gz')['cases']},
        'modules': {c['id']:c['reports'][1] for c in archived(ROOT/'reports/frozen-modules-v4/result.json.gz')['cases']},
        'real': {c['id']:c['reports'][1] for c in archived(ROOT/'reports/frozen-modules-real-v3/result.json.gz')['cases']},
        'stress': {c['id']:c['measurement']['report'] for c in archived(ROOT/'reports/boundary-uncapped-20261016/result.json.gz')['cases'] if c['group']=='finite-stress'}}
    OUT.mkdir(exist_ok=False)
    saves = old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    rows = []
    start = time.perf_counter()
    for c in spec['cases']:
        print(json.dumps(dict(start=c['id'])),flush=True)
        control = invoke(c,True) if c['measurement_group']=='stress' or c['original_id']=='payload-capacity' else None
        measured = invoke(c)
        r = measured['report']
        checks = []
        def check(name, value):
            checks.append(dict(check=name, passed=bool(value)))
        check('structured-diagnostic',r is not None)
        if r is not None:
            check('quotas-open-tracing-closed',r['budget']['limit'] is None and not r['resource_quotas_enabled'] and not r['full_trace_enabled'] and not r['game_started'])
            check('work-accounting',r['budget']['used']==sum(r['budget']['categories'].values()))
            baseline = baselines[c['measurement_group']].get(c['original_id'])
            if baseline is not None and c['original_id'] not in ['payload-capacity','wire-encoding']:
                if 'semantic' in baseline:
                    check('unchanged-ordinary-results','semantic' in r and m.compact.b.draws.ordinary(r)==m.compact.b.draws.ordinary(baseline))
                else:
                    check('same-explicit-refusal',r.get('first_unsupported_entry')==baseline.get('first_unsupported_entry'))
            if c['original_id']=='payload-capacity':
                draws=r.get('steps',[{}])[0].get('draws',[])
                check('former-payload-cap-completed',measured['returncode']==0 and len(draws)==2 and all(len(bytes.fromhex(x['text_hex']))==65536 for x in draws))
            if c['original_id']=='wire-encoding':
                check('wire-byte-accounting',r['steps'][0]['wire_bytes_equal_json'] and r['steps'][0]['checked']==252)
            if c['original_id']=='million-reads-no-values':
                on=next(row['measurement']['report'] for row in rows if row['id']=='stress--million-reads')
                check('same-million-read-output',m.compact.b.draws.ordinary(on)==m.compact.b.draws.ordinary(r))
        completed=measured['returncode']==0 and r is not None and 'semantic' in r
        row=dict(id=c['id'],group=c['measurement_group'],completed=completed,checks=checks,
                 measurement_valid=all(x['passed'] for x in checks),measurement=measured,formal_control=control)
        rows.append(row)
        print(json.dumps(dict(id=c['id'],completed=completed,measurement_valid=row['measurement_valid'],work=(r or {}).get('budget',{}).get('used'),native_seconds=(r or {}).get('seconds'),peak_mib=round(((r or {}).get('peak_private_commit_bytes') or measured['sampled_peak_private_bytes'])/1024**2,3),unsupported=(r or {}).get('first_unsupported_entry'))),flush=True)
    assert before == protected()
    assert saves['files'] == old.audit(ROOT.parent/'artifacts/authority-baseline-20261009')['files']
    result=dict(schema='current-uncapped-result-1',measurement_only=True,abi=ABI,
        work_limit=None,timeout_seconds=None,process_memory_limit=None,record_caps=None,
        full_trace_enabled=False,game_started=False,expression_projection_verifier_run=False,
        automatic_projection_passed=False,formal_files_unchanged=True,frozen_sources_unchanged=True,save_files_unchanged=True,
        real_initialization_completed=all(row['completed'] for row in rows if row['group']=='real'),
        cases=rows,excluded=spec['excluded'],seconds=time.perf_counter()-start,
        binary_sha256=old.digest(EXE),manifest_sha256=old.digest(MANIFEST),driver_sha256=old.digest(Path(__file__)),
        derivation_sha256=old.digest(BASE/'derivation.json'))
    data=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    packed=OUT/'result.json.gz'
    packed.write_bytes(gzip.compress(data,mtime=0))
    assert gzip.decompress(packed.read_bytes())==data
    old.save(OUT/'summary.json',dict(schema='current-uncapped-summary-1',case_count=len(rows),
        measurement_valid=all(row['measurement_valid'] for row in rows),completed=sum(row['completed'] for row in rows),
        real_initialization_completed=result['real_initialization_completed'],
        formal_files_unchanged=True,save_files_unchanged=True,seconds=result['seconds'],
        report_sha256=old.digest(packed),raw_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(data),stored_bytes=packed.stat().st_size,
        cases=[dict(id=row['id'],completed=row['completed'],measurement_valid=row['measurement_valid'],
            work=(row['measurement']['report'] or {}).get('budget',{}).get('used'),
            native_seconds=(row['measurement']['report'] or {}).get('seconds'),
            peak_private_bytes=(row['measurement']['report'] or {}).get('peak_private_commit_bytes'),
            first_unsupported_entry=(row['measurement']['report'] or {}).get('first_unsupported_entry')) for row in rows]))
    print(json.dumps(dict(finished=True,cases=len(rows),completed=sum(row['completed'] for row in rows),measurement_valid=all(row['measurement_valid'] for row in rows),seconds=result['seconds'],report_bytes=packed.stat().st_size)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','run'])
    args=parser.parse_args()
    if args.phase=='prepare': prepare()
    else: run()
