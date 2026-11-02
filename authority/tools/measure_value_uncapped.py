"""One-off quota-free measurement; formal sources and limits remain immutable.

Finite model workloads and the three real frozen entry points only. Unknown
APIs and authority/provenance refusals remain enabled; no game process is used.
"""
import argparse, copy, gzip, hashlib, json, re, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
import run_value_objects as v
import measure_current_uncapped as prior

ROOT=v.ROOT; BASE=ROOT/'build-value-measurement'; GEN=BASE/'source'
EXE=BASE/'Release/authority-value-measure.exe'
OUT=ROOT/'reports/value-uncapped-20261016'
MANIFEST=BASE/'measurement.json'; ABI='ia-lua533-value-measure-1'
load=v.s.o.load; digest=v.old.digest; edit=prior.edit

def save(p,data):
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def protected():
    result=v.s.o.m.protected()
    for group in ['inputs','binaries','frozen_files']:
        result.update(load(ROOT/'reports/mod-sdk-final.json')[group])
    for folder in ['value_object_runtime','build-value-objects/generated']:
        for p in (ROOT/folder).iterdir():
            if p.is_file(): result[p.relative_to(ROOT).as_posix()]=digest(p)
    for p in [v.CURRENT,v.REAL,v.MANIFEST,v.EXE,v.REF,
              ROOT/'tools/run_value_objects.py',ROOT/'tools/run_value_regressions.py',
              ROOT/'reports/value-objects-v2/result.json.gz',
              ROOT/'reports/value-objects-real-v2/result.json.gz']:
        result[p.relative_to(ROOT).as_posix()]=digest(p)
    for name,h in result.items():
        assert digest(ROOT/name)==h,name
    return result

def remove_capacities(s):
    """Remove only a syntactically complete if/throw resource guard."""
    removed=[]; spans=[]
    for match in re.finditer(r'\bif\(',s):
        n=1;i=match.end()
        while i<len(s) and n:
            if s[i]=='(': n+=1
            elif s[i]==')': n-=1
            i+=1
        body=re.match(r'\s*throw std::runtime_error\("([^"\n]*capacity exceeded[^"\n]*)"\);',s[i:])
        if body:
            spans.append((match.start(),i+body.end()))
            removed.append(dict(condition=s[match.end():i-1],diagnostic=body[1]))
    for a,b in reversed(spans): s=s[:a]+s[b:]
    return s,removed

def prepare():
    before=protected(); BASE.mkdir(exist_ok=False); GEN.mkdir()
    inputs={p.name:p for p in (ROOT/'build-value-objects/generated').iterdir()
            if p.suffix in ['.c','.cpp','.h','.hpp','.inc']}
    for folder,names in [
        ('compact_value_runtime',['source_capture.cpp','source_capture.hpp']),
        ('module_runtime',['frozen_modules.hpp']),
        ('object_runtime',['object_catalog.hpp']),
        ('value_object_runtime',['value_profile.hpp','context_values.inc'])]:
        for name in names: inputs[name]=ROOT/folder/name
    changes={}
    for name,p in inputs.items():
        original=p.read_text(encoding='utf-8'); s=original
        if name=='boundary.cpp':
            s=edit(s,'constexpr uint64_t limit=10000000;','constexpr uint64_t limit=UINT64_MAX;')
            s=edit(s,'{"limit",limit}','{"limit",nullptr},{"counter_representation_max",limit}')
            s=edit(s,'if(depth>24)throw std::runtime_error("JSON depth unsupported");','',2)
            s=edit(s,'if(text.size()>65536||draws.size()>=1024)throw std::runtime_error("Draw queue exceeds contract");','')
            s=edit(s,'for(int level=0;level<32;++level)','for(int level=0;;++level)')
            s=edit(s,'if(n>262144-data.size())return 1;','')
            s=edit(s,'if(!c.sdk_arguments.is_array()||c.sdk_arguments.size()>16)throw std::runtime_error("SDK callback argument capacity exceeded");',
                   'if(!c.sdk_arguments.is_array())throw std::runtime_error("SDK callback arguments must be an array");')
            s=edit(s,'if(manifest.at("work_limit")!=limit||manifest.at("timeout_seconds")!=5)throw std::runtime_error("Formal limits required");',
                   'if(!manifest.at("work_limit").is_null()||!manifest.at("timeout_seconds").is_null()||!manifest.value("measurement_only",false))throw std::runtime_error("Explicit uncapped manifest required");')
            start=s.index('    HANDLE job=CreateJobObjectW(');end=s.index('\n',start)
            s=s[:start]+'    HANDLE job=nullptr;'+s[end:]
            s=edit(s,'CloseHandle(job);','if(job)CloseHandle(job);')
            flags='{"peak_private_commit_bytes",mem.PeakPagefileUsage},{"measurement_only",true},{"resource_quotas_enabled",false},{"wall_clock_watchdog_seconds",nullptr}'
            s=edit(s,'{"private_commit_bytes",mem.PrivateUsage}','{"private_commit_bytes",mem.PrivateUsage},'+flags)
            s=edit(s,'}catch(const std::exception&e){std::cout<<Json',
                   '}catch(const std::exception&e){PROCESS_MEMORY_COUNTERS_EX mem{};mem.cb=sizeof(mem);GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&mem),sizeof(mem));std::cout<<Json')
            s=edit(s,'{"completed",false}','{"completed",false},'+flags)
            s=s.replace('--value-suite','--value-measure-suite').replace('ia-lua533-value-objects-1',ABI)
        elif name=='write_barrier.hpp':
            s=edit(s,'if(k.kind==0||(k.kind==2&&k.length>4096))return;','if(k.kind==0)return;')
            s=edit(s,'{"read_entry_limit",16384}','{"read_entry_limit",nullptr}')
        elif name=='source_capture.cpp':
            s=edit(s,'void*live[32];int n=ia_source_live_frames(L,live,32);if(n<0)throw std::runtime_error("Source live frame capacity exceeded");',
                   'int n=ia_source_live_frames(L,nullptr,0);std::vector<void*>live(static_cast<size_t>(n));if(ia_source_live_frames(L,live.data(),n)!=n)throw std::runtime_error("Source frame census changed");')
            s=edit(s,'std::find(live,live+n,i->first)==live+n','std::find(live.begin(),live.end(),i->first)==live.end()')
            s=edit(s,'{"original_record_and_byte_caps_preserved",true}','{"original_record_and_byte_caps_preserved",false}')
        elif name=='source_bridge.c':
            s=edit(s,'if(n>=capacity)return -1;frames[n++]=ci;','if(frames){if(n>=capacity)return -1;frames[n]=ci;}++n;')
        elif name=='value_sdk_profile.hpp':
            s=edit(s,'if(!role.is_object()||role.size()>256)throw std::runtime_error("SDK store map capacity exceeded");',
                   'if(!role.is_object())throw std::runtime_error("SDK store map must be an object");')
        s,removed=remove_capacities(s)
        (GEN/name).write_text(s,encoding='utf-8',newline='\n')
        changes[name]=dict(source=p.relative_to(ROOT).as_posix(),source_sha256=digest(p),sha256=digest(GEN/name),removed_capacity_guards=removed)
    cmake=(ROOT/'value_object_runtime/CMakeLists.txt').read_text(encoding='utf-8')
    cmake=cmake.split('target_include_directories(authority-values-reference BEFORE')[0]
    cmake=edit(cmake,'${CMAKE_CURRENT_SOURCE_DIR}/..','${CMAKE_CURRENT_SOURCE_DIR}/../..')
    cmake=edit(cmake,'set(GEN "${IA_ROOT}/build-value-objects/generated")','set(GEN "${CMAKE_CURRENT_SOURCE_DIR}")')
    cmake=edit(cmake,'foreach(target authority-values authority-values-reference)','foreach(target authority-values)')
    cmake=edit(cmake,'"${IA_ROOT}/compact_value_runtime/source_capture.cpp"','"${GEN}/source_capture.cpp"')
    # GEN precedes all original include directories; unmodified native dependencies stay shared.
    cmake=cmake.replace('authority-values','authority-value-measure').replace('project(ValueObjects','project(ValueQuotaMeasurement')
    (GEN/'CMakeLists.txt').write_text(cmake,encoding='utf-8',newline='\n')
    cases=[]
    for c in load(v.CURRENT)['cases']:
        c=copy.deepcopy(c);c.update(group='model',original_id=c['id']);c['id']='model--'+c['id']
        if c['original_id']=='reject-live-cap':
            c.update(kind='functional',former_resource_limit=True);c.pop('error');c['steps'].append(dict(op='value_status'))
        cases.append(c)
    for c in load(ROOT/'build-current-uncapped/measurement.json')['cases']:
        if c['measurement_group']=='stress':
            c=copy.deepcopy(c);c['group']='finite-stress';cases.append(c)
    for c in load(v.REAL)['cases']:
        c=copy.deepcopy(c);c.update(group='real',original_id=c['id']);c['id']='real--'+c['id'];cases.append(c)
    spec=dict(schema='value-uncapped-measurement-1',measurement_only=True,work_limit=None,timeout_seconds=None,
              process_memory_limit=None,record_caps=None,full_trace_enabled=False,cases=cases,
              excluded=[dict(id='module-work-cap',reason='intentional infinite loop has no normal uncapped endpoint')])
    save(MANIFEST,spec);save(BASE/'protected-before.json',before)
    save(BASE/'derivation.json',dict(abi=ABI,changes=changes,cmake_sha256=digest(GEN/'CMakeLists.txt'),
         formal_limits_unchanged=True,lua_rebuilt=False,lua_sha256=digest(ROOT/'build-read-set/Release/read_lua.lib'),
         semantic_checks_preserved=True,physical_constraints=['Windows x86 address space','available system memory','Lua representation/stack limits','uint64 counter range']))
    assert before==protected()
    print(json.dumps(dict(prepared=True,cases=len(cases),capacity_guards_removed=sum(len(x['removed_capacity_guards'])for x in changes.values()))))

def read_gz(p):return json.loads(gzip.decompress(p.read_bytes()))

def run():
    before=load(BASE/'protected-before.json');assert before==protected()
    d=load(BASE/'derivation.json')
    for name,x in d['changes'].items():
        assert digest(GEN/name)==x['sha256'] and digest(ROOT/x['source'])==x['source_sha256']
    assert digest(GEN/'CMakeLists.txt')==d['cmake_sha256']
    spec=load(MANIFEST)
    prior.EXE=EXE;prior.MANIFEST=MANIFEST;prior.OUT=OUT
    # Reuse memory observer only. Its uncapped branch has neither timeout nor job quota.
    # The private CLI differs, so supply a local argument adapter to Popen below.
    popen=prior.subprocess.Popen
    def adapted(args,**kwargs):
        args=list(args);args[1]='--value-measure-suite';return popen(args,**kwargs)
    prior.subprocess.Popen=adapted
    baseline={('model',c['id']):c['reports'][1]for c in read_gz(ROOT/'reports/value-objects-v2/result.json.gz')['cases']}
    baseline.update({('real',c['id']):c['reports'][1]for c in read_gz(ROOT/'reports/value-objects-real-v2/result.json.gz')['cases']})
    baseline.update({('finite-stress',c['id']):c['measurement']['report']for c in read_gz(ROOT/'reports/current-uncapped-20261016/result.json.gz')['cases']if c['group']=='stress'})
    OUT.mkdir(exist_ok=False);rows=[];start=time.perf_counter()
    for c in spec['cases']:
        print(json.dumps(dict(start=c['id'])),flush=True);measured=prior.invoke(c)
        r=measured['report'];checks=[]
        def check(name,value):checks.append(dict(check=name,passed=bool(value)))
        check('structured-result',r is not None)
        if r is not None:
            check('open-quotas-closed-full-trace',r['budget']['limit'] is None and r['measurement_only']and not r['resource_quotas_enabled']and not r['full_trace_enabled']and not r['game_started'])
            check('work-accounting',r['budget']['used']==sum(r['budget']['categories'].values()))
            b=baseline.get((c['group'],c['original_id']if c['group']!='finite-stress'else c['id']))
            if c.get('former_resource_limit'):
                check('former-live-cap-completed',measured['returncode']==0 and r.get('steps',[{}])[-1].get('metadata',{}).get('live')==1040)
            elif b is not None:
                if 'semantic'in b:check('unchanged-ordinary-results','semantic'in r and v.s.o.m.compact.b.draws.ordinary(r)==v.s.o.m.compact.b.draws.ordinary(b))
                else:check('same-explicit-failure',r.get('first_unsupported_entry')==b.get('first_unsupported_entry'))
        row=dict(id=c['id'],group=c['group'],completed=measured['returncode']==0 and r is not None and 'semantic'in r,
                 measurement_valid=all(x['passed']for x in checks),checks=checks,measurement=measured)
        rows.append(row)
        print(json.dumps(dict(id=row['id'],completed=row['completed'],measurement_valid=row['measurement_valid'],work=(r or{}).get('budget',{}).get('used'),seconds=(r or{}).get('seconds'),peak_mib=round(((r or{}).get('peak_private_commit_bytes')or measured['sampled_peak_private_bytes'])/1024**2,3),first_unsupported=(r or{}).get('first_unsupported_entry'))),flush=True)
        # One compressed checkpoint is replaced, never duplicated per case.
        data=(json.dumps(dict(schema='value-uncapped-result-1',complete=len(rows)==len(spec['cases']),cases=rows),ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        (OUT/'result.json.gz').write_bytes(gzip.compress(data,mtime=0))
    assert before==protected()
    assert gzip.decompress((OUT/'result.json.gz').read_bytes())==data
    save(OUT/'summary.json',dict(schema='value-uncapped-summary-1',abi=ABI,cases=len(rows),measurement_valid=all(x['measurement_valid']for x in rows),
        completed=sum(x['completed']for x in rows),real_initialization_completed=all(x['completed']for x in rows if x['group']=='real'),
        formal_files_unchanged=True,game_started=False,full_trace_enabled=False,seconds=time.perf_counter()-start,
        binary_sha256=digest(EXE),manifest_sha256=digest(MANIFEST),driver_sha256=digest(Path(__file__)),derivation_sha256=digest(BASE/'derivation.json'),
        result_sha256=digest(OUT/'result.json.gz'),raw_sha256=hashlib.sha256(data).hexdigest(),stored_bytes=(OUT/'result.json.gz').stat().st_size,
        case_summary=[dict(id=x['id'],completed=x['completed'],measurement_valid=x['measurement_valid'],
            work=(x['measurement']['report']or{}).get('budget',{}).get('used'),seconds=(x['measurement']['report']or{}).get('seconds'),
            peak_private_bytes=(x['measurement']['report']or{}).get('peak_private_commit_bytes'),first_unsupported=(x['measurement']['report']or{}).get('first_unsupported_entry'))for x in rows]))
    print(json.dumps(dict(finished=True,cases=len(rows),measurement_valid=all(x['measurement_valid']for x in rows),real_initialization_completed=all(x['completed']for x in rows if x['group']=='real'))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','run']);a=p.parse_args()
    prepare()if a.phase=='prepare'else run()
