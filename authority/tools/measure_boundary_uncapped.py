"""Explicit one-off uncapped execution measurement of the current boundary runtime.

No work/record/memory quota or wall-clock watchdog in the measurement child.
Keep semantic refusals, source hashes, x86 representation and the original Lua VM.
Do not use the retired full tracer or claim missing SDK contracts are implemented.
"""
import argparse,copy,ctypes,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_bound_values as b
import run_boundary_handoff as old
import verify_bound_values
ROOT=b.ROOT;BASE=ROOT/'build-bound-measurement';GEN=BASE/'source';MANIFEST=BASE/'measurement.json'
EXE=BASE/'Release/authority-bound-measure.exe'
ABI='ia-lua533-bound-measure-1';MAX64=2**64-1

def change(s,a,v,count=1):
    if s.count(a)!=count:raise RuntimeError('Measurement anchor mismatch: '+a[:100])
    return s.replace(a,v)

def prepare():
    verify_bound_values.main();BASE.mkdir(exist_ok=False);GEN.mkdir()
    before=b.protected();old.save(BASE/'protected-before.json',before)
    inputs={n:ROOT/'build-bound-value/generated'/n for n in ['boundary.cpp','write_barrier.hpp','write_barrier.cpp','read_hooks.c']}
    for n in ['source_capture.cpp','source_capture.hpp','source_bridge.c','source_emit.cpp','source_api.h']:inputs[n]=ROOT/'bound_value_runtime'/n
    changes={}
    for n,p in inputs.items():
        original=p.read_text(encoding='utf-8');s=original
        if n=='boundary.cpp':
            s=change(s,'constexpr uint64_t limit=10000000;','constexpr uint64_t limit=UINT64_MAX;')
            s=change(s,'{"limit",limit}','{"limit",nullptr},{"counter_representation_max",limit}')
            for cond,msg in [('prototypes.size()>=1024','Prototype metadata capacity exceeded'),('cells.size()>=1024','Upvalue metadata capacity exceeded'),('fields.size()>=1024','Field observation capacity exceeded'),('callbacks.size()>=256','Callback registry capacity exceeded'),('draw_sites.size()>=128','Draw plan site capacity exceeded'),('draw_prototypes.size()>=64||dumped.size()>524288-draw_prototype_bytes','Draw prototype pool capacity exceeded'),('depth>24','JSON depth unsupported'),('text.size()>65536||draws.size()>=1024','Draw queue exceeds contract')]:
                fragment=f'if({cond})throw std::runtime_error("{msg}");';s=change(s,fragment,'',2 if cond in ['cells.size()>=1024','depth>24']else 1)
            s=change(s,'for(int level=0;level<32;++level)','for(int level=0;;++level)')
            s=change(s,'if(n>262144-data.size())return 1;','')
            s=change(s,'if(manifest.at("work_limit")!=limit||manifest.at("timeout_seconds")!=5)throw std::runtime_error("Formal limits required");','if(!manifest.at("work_limit").is_null()||!manifest.at("timeout_seconds").is_null()||!manifest.value("measurement_only",false))throw std::runtime_error("Explicit measurement manifest required");')
            start=s.index('    HANDLE job=CreateJobObjectW(');end=s.index('\n',start);s=s[:start]+'    HANDLE job=nullptr;'+s[end:]
            s=change(s,'int wmain(int argc,wchar_t** argv){SetErrorMode','int wmain(int argc,wchar_t** argv){Ledger budget;auto start=std::chrono::steady_clock::now();SetErrorMode')
            s=change(s,'    Ledger budget;auto start=std::chrono::steady_clock::now();Session session','    Session session')
            s=change(s,'{"private_commit_bytes",mem.PrivateUsage}','{"private_commit_bytes",mem.PrivateUsage},{"peak_private_commit_bytes",mem.PeakPagefileUsage},{"measurement_only",true},{"resource_quotas_enabled",false},{"wall_clock_watchdog_seconds",nullptr}')
            s=change(s,'throw std::runtime_error("Unknown module contract")','throw std::runtime_error("Unknown module contract: "+bytes(L,1))')
            tail='}catch(const std::exception& e){std::cerr<<e.what()<<\'\\n\';return 1;}}'
            replacement='}catch(const std::exception&e){PROCESS_MEMORY_COUNTERS_EX mem{};mem.cb=sizeof(mem);GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&mem),sizeof(mem));std::cout<<Json{{"abi","'+ABI+'"},{"measurement_only",true},{"completed",false},{"first_unsupported_entry",e.what()},{"budget",budget.report()},{"seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()},{"peak_private_commit_bytes",mem.PeakPagefileUsage},{"full_trace_enabled",false},{"game_started",false}}.dump()<<\'\\n\';return 1;}}'
            s=change(s,tail,replacement)
            s=s.replace('--bound-value-suite','--measure-suite').replace('ia-lua533-bound-values-1',ABI)
        elif n=='write_barrier.hpp':
            guards=[('cells.size()>=1024','Write cell capacity exceeded'),('key.text.size()>4096','Write field key capacity exceeded'),('tables.size()>=1024','Write table capacity exceeded'),('field_count>=1024','Write field capacity exceeded'),('!consumers.count(id)&&consumers.size()>=256','Consumer capacity exceeded'),('tables.size()>=1024','Read table capacity exceeded'),('pending->deps.size()>=1024','Consumer dependency capacity exceeded'),('live_read_entries>=16384','Consumer total read entry capacity exceeded'),('source.length>4096','Read key capacity exceeded'),('key.size()>4096||size>4096','Consumer external token size exceeded'),('pending->external.size()>=1024','Consumer external dependency capacity exceeded')]
            for cond,msg in guards:s=change(s,f'if({cond})throw std::runtime_error("{msg}");','',2 if cond=='live_read_entries>=16384'else 1)
            s=change(s,'if(k.kind==0||(k.kind==2&&k.length>4096))return;','if(k.kind==0)return;')
            s=change(s,'{"read_entry_limit",16384}','{"read_entry_limit",nullptr}')
        elif n=='source_capture.cpp':
            a='void*live[32];int n=ia_source_live_frames(L,live,32);if(n<0)throw std::runtime_error("Source live frame capacity exceeded");'
            v='int n=ia_source_live_frames(L,nullptr,0);std::vector<void*>live(static_cast<size_t>(n));if(ia_source_live_frames(L,live.data(),n)!=n)throw std::runtime_error("Source frame census changed");'
            s=change(s,a,v);s=change(s,'std::find(live,live+n,i->first)==live+n','std::find(live.begin(),live.end(),i->first)==live.end()')
            for cond,msg in [('v.length>65536','Source scalar byte capacity exceeded'),('frames.size()>=32&&!frames.count(info.frame)','Source live frame capacity exceeded'),('stats->records>=4096||bytes>262144-stats->bytes','Source observation capacity exceeded'),('sites.size()>=128||entries>16384-snapshot_entries','Source draw snapshot capacity exceeded')]:s=change(s,f'if({cond})throw std::runtime_error("{msg}");','')
        elif n=='source_bridge.c':
            s=change(s,'if(n>=capacity)return -1;frames[n++]=ci;','if(frames){if(n>=capacity)return -1;frames[n]=ci;}++n;')
        target=GEN/n;target.write_text(s,encoding='utf-8',newline='\n');changes[n]=dict(source=p.relative_to(ROOT).as_posix(),source_sha256=old.digest(p),sha256=old.digest(target),modified=s!=original)
    cmake=(ROOT/'bound_value_runtime/CMakeLists.txt').read_text(encoding='utf-8').split('add_executable(authority-verify-values')[0]
    cmake=change(cmake,'${CMAKE_CURRENT_SOURCE_DIR}/..','${CMAKE_CURRENT_SOURCE_DIR}/../..')
    cmake=change(cmake,'set(GEN "${IA_ROOT}/build-bound-value/generated")','set(GEN "${CMAKE_CURRENT_SOURCE_DIR}")')
    cmake=cmake.replace('authority-bound-values','authority-bound-measure').replace('project(BoundValues','project(BoundMeasurement')
    (GEN/'CMakeLists.txt').write_text(cmake,encoding='utf-8')
    cases=copy.deepcopy(json.loads(b.MANIFEST.read_text(encoding='utf-8'))['cases'])
    for c in cases:
        c['measurement_group']='current-model'
        if c['kind']=='native-rejection':
            for step in c['steps']:step.pop('expect_error',None)
    fixtures={
      'million-reads':"local m=RegisterMod('Million Reads',1)\nlocal cfg=require('json').decode(m:LoadData())\nlocal total=0\nm:AddCallback(2,function()for i=1,1000000 do total=total+cfg.amount end;Isaac.RenderText('total='..total,cfg.x,0)end)\n",
      'many-fields':"local m=RegisterMod('Many Fields',1)\nlocal t={} for i=1,20000 do t[i]=i end\nlocal total=0\nm:AddCallback(2,function()for i=1,20000 do total=total+t[i]end;Isaac.RenderText('total='..total,0,0)end)\n",
      'long-key-aba':"local m=RegisterMod('Long Key ABA',1)\nlocal key=string.rep('k',8192);local t={[key]=1}\nm:AddCallback(2,function()local a=t[key];rawset(t,key,2);rawset(t,key,1);Isaac.RenderText('aba='..a..'/'..t[key],0,0)end)\n",
      'forty-frames':"local m=RegisterMod('Forty Frames',1)\nlocal function deep(n)if n==0 then Isaac.RenderText('deep',0,0)else deep(n-1);local keep=n end end\nm:AddCallback(2,function()deep(40)end)\n",
      'many-draws':"local m=RegisterMod('Many Draws',1)\nm:AddCallback(2,function()for i=1,257 do Isaac.RenderText('draw',i,0)end end)\n"}
    for name,code in fixtures.items():
        p=GEN/(name+'.lua');p.write_text(code,encoding='utf-8');cases.append(dict(id=name,source=p.relative_to(ROOT).as_posix(),source_sha256=old.digest(p),stores=[old.store(1,17,'en'),old.store()],steps=[b.cap()],measurement_group='finite-stress'))
    suite=json.loads((ROOT/'research/ui_incremental_suite_10m_v1.json').read_text(encoding='utf-8'));expected={}
    for c in suite['cases']:
        for mod in c['mods']:
            for name,h in mod['sha256'].items():expected[str(Path('research/slice3_ui_inputs')/mod['root']/name).replace('\\','/')]=h
    for name,h in expected.items():assert old.digest(ROOT/name)==h
    real=[('real-mcm','research/slice3_ui_inputs/mods/mod_config_menu_cn_2494192799/main.lua'),('real-eid','research/slice3_ui_inputs/mods/external item descriptions_836319872/main.lua')]
    for name,source in real:cases.append(dict(id=name,source=source,source_sha256=old.digest(ROOT/source),stores=['{}','{}'],steps=[],measurement_group='frozen-real-entry'))
    # Same unchanged files in load order; the first unsupported operation ends
    # the attempt. The independent EID case above is still always executed.
    name,source=real[0];cases.append(dict(id='real-combined',source=source,source_sha256=old.digest(ROOT/source),extra_sources=[dict(source=real[1][1],sha256=old.digest(ROOT/real[1][1]))],stores=['{}','{}'],steps=[],measurement_group='frozen-real-entry'))
    s=(GEN/'boundary.cpp').read_text(encoding='utf-8')
    anchor='Json steps=Json::array();'
    extra='for(auto&extra:def.value("extra_sources",Json::array())){auto p=std::filesystem::canonical(root/ia::wide(extra.at("source").get<std::string>()));if(p.lexically_relative(root).empty()||*p.lexically_relative(root).begin()==L"..")throw std::runtime_error("Extra source outside root");auto source=read(p);if(ia::sha256_bytes(source)!=extra.at("sha256").get<std::string>())throw std::runtime_error("Extra frozen source hash mismatch");session.host->execute(source,"@"+extra.at("source").get<std::string>());session.personal->execute(source,"@"+extra.at("source").get<std::string>());}Json steps=Json::array();'
    s=change(s,anchor,extra);(GEN/'boundary.cpp').write_text(s,encoding='utf-8');changes['boundary.cpp']['sha256']=old.digest(GEN/'boundary.cpp')
    old.save(MANIFEST,dict(schema='uncapped-boundary-execution-measurement-1',measurement_only=True,work_limit=None,timeout_seconds=None,process_memory_limit=None,record_caps=None,full_trace_enabled=False,semantic_checks_preserved=True,cases=cases))
    control=json.loads(MANIFEST.read_text(encoding='utf-8'));control['work_limit']=10000000;control['timeout_seconds']=5;old.save(BASE/'formal-control.json',control)
    old.save(BASE/'derivation.json',dict(abi=ABI,formal_final_sha256=old.digest(ROOT/'reports/bound-values-final.json'),lua_rebuilt=False,lua_sha256=old.digest(ROOT/'build-read-set/Release/read_lua.lib'),changes=changes,cmake_sha256=old.digest(GEN/'CMakeLists.txt'),frozen_real_files=expected))
    assert before==b.protected();print(json.dumps(dict(prepared=True,cases=len(cases),work_quota=None,timeout=None,memory_quota=None,record_caps=None)))

class Memory(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t)for n in ['peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private']]

def invoke(case,out,formal=False):
    exe=b.EXE if formal else EXE;manifest=BASE/'formal-control.json'if formal else MANIFEST
    stem=case['id']+('-formal'if formal else '-uncapped');raw=out/(stem+'.json.tmp');err=out/(stem+'.stderr.tmp');start=time.perf_counter();samples=[];peak=0;timed_out=False
    psapi=ctypes.WinDLL('psapi',use_last_error=True);getmem=psapi.GetProcessMemoryInfo;getmem.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong];getmem.restype=ctypes.c_int
    with raw.open('xb')as stdout,err.open('xb')as stderr:
        child=subprocess.Popen([str(exe),'--bound-value-suite'if formal else '--measure-suite',str(ROOT),str(manifest),case['id'],'boundary'],stdout=stdout,stderr=stderr)
        try:
            next_note=start+3
            while child.poll()is None:
                mem=Memory();mem.cb=ctypes.sizeof(mem)
                if getmem(int(child._handle),ctypes.byref(mem),mem.cb):peak=max(peak,mem.private,mem.peak_pagefile)
                now=time.perf_counter()
                if formal and now-start>=5:timed_out=True;child.kill();break
                if now>=next_note:
                    samples.append(dict(seconds=now-start,private_bytes=mem.private));print(json.dumps(dict(id=case['id'],formal=formal,running_seconds=round(now-start,2),private_mib=round(mem.private/1024**2,2))),flush=True);next_note=now+3
                time.sleep(.05)
        except BaseException:
            child.kill();child.wait();raise
        child.wait()
    data=raw.read_bytes();errors=err.read_bytes();report=None
    if data:
        try:report=json.loads(data)
        except ValueError:pass
    archived=[]
    for p,content in [(raw,data),(err,errors)]:
        packed=p.with_suffix('.gz');packed.write_bytes(gzip.compress(content,mtime=0));assert gzip.decompress(packed.read_bytes())==content;archived.append(dict(path=packed.name,sha256=old.digest(packed),raw_sha256=hashlib.sha256(content).hexdigest(),raw_bytes=len(content),bytes=packed.stat().st_size));p.unlink()
    return dict(returncode=child.returncode,timed_out=timed_out,seconds=time.perf_counter()-start,sampled_peak_private_bytes=peak,memory_samples=samples,stderr_tail=errors[-8192:].decode('utf-8',errors='replace'),report=report,archives=archived)

def run(out):
    verify_bound_values.main();before=b.protected();derivation=json.loads((BASE/'derivation.json').read_text(encoding='utf-8'))
    for name,v in derivation['changes'].items():assert old.digest(GEN/name)==v['sha256']
    for name,h in derivation['frozen_real_files'].items():assert old.digest(ROOT/name)==h
    spec=json.loads(MANIFEST.read_text(encoding='utf-8'))
    for c in spec['cases']:assert old.digest(ROOT/c['source'])==c['source_sha256']
    out.mkdir(exist_ok=False,parents=True);saves=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');start=time.perf_counter();rows=[]
    for c in spec['cases']:
        print(json.dumps(dict(start=c['id'],group=c['measurement_group'])),flush=True)
        formal=invoke(c,out,True)if c['measurement_group']=='finite-stress'or c['id']=='payload-capacity'else None
        measured=invoke(c,out);report=measured['report'];completed=measured['returncode']==0 and report is not None
        if report is not None:
            assert not report['full_trace_enabled']and not report['game_started'];assert report['budget']['used']==sum(report['budget']['categories'].values())and report['budget']['limit']is None
            measured['native_work']=report['budget']['used'];measured['native_seconds']=report['seconds'];measured['native_peak_private_bytes']=report.get('peak_private_commit_bytes')
        row=dict(id=c['id'],group=c['measurement_group'],completed=completed,first_unsupported_entry=(report or{}).get('first_unsupported_entry'),formal_control=formal,measurement=measured)
        old.save(out/(c['id']+'-summary.json'),{**row,'measurement':{k:v for k,v in measured.items()if k!='report'},'formal_control':({k:v for k,v in formal.items()if k!='report'}if formal else None)})
        rows.append(row);print(json.dumps(dict(id=c['id'],completed=completed,work=measured.get('native_work'),seconds=round(measured['seconds'],4),peak_mib=round((measured.get('native_peak_private_bytes')or measured['sampled_peak_private_bytes'])/1024**2,2),unsupported=row['first_unsupported_entry'])),flush=True)
    after=old.audit(ROOT.parent/'artifacts/authority-baseline-20261009');protected_unchanged=before==b.protected();assert protected_unchanged and saves['files']==after['files']
    result=dict(schema='uncapped-boundary-execution-result-1',abi=ABI,measurement_only=True,work_quota=None,timeout_seconds=None,process_memory_quota=None,record_caps=None,semantic_checks_preserved=True,full_trace_enabled=False,expression_verifier_run=False,work_unit='current boundary ledger, not old full tracer',seconds=time.perf_counter()-start,cases=rows,formal_files_unchanged=protected_unchanged,save_files_unchanged=True,frozen_real_files_unchanged=all(old.digest(ROOT/p)==h for p,h in derivation['frozen_real_files'].items()),game_started=False,binary_sha256=old.digest(EXE),manifest_sha256=old.digest(MANIFEST),derivation_sha256=old.digest(BASE/'derivation.json'),driver_sha256=old.digest(Path(__file__)))
    old.save(out/'result.json',result);print(json.dumps(dict(finished=True,cases=len(rows),seconds=result['seconds'],completed=sum(r['completed']for r in rows),formal_unchanged=True)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','run']);p.add_argument('--output',type=Path,default=ROOT/'reports/boundary-uncapped-20261016');a=p.parse_args()
    if a.phase=='prepare':prepare()
    else:run(a.output.resolve())
