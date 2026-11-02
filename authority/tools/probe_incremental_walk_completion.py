"""Temporary relaxed dependency-walk sizing; formal runtime and old probes stay intact."""
import argparse,json,os,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
import probe_incremental_completion as base
from run_incremental_ui import ROOT,digest,write

REPORT=ROOT/'reports/ui-incremental-walk-completion-sizing.json'
WALK=262144
DEPTH=256
WATCHDOG=600
original_write=base.write

def routed_write(path,value):
    if Path(path)==ROOT/'reports/ui-incremental-completion-sizing.json':path=REPORT
    original_write(path,value)
base.write=routed_write

def edit(path,old,new,count=None):
    text=path.read_text(encoding='utf-8');actual=text.count(old)
    if not actual or (count is not None and actual!=count):raise ValueError('Temporary walk patch mismatch: '+path.name+' '+old)
    path.write_text(text.replace(old,new),encoding='utf-8')
    return actual

def prepare(destination,work_limit,evidence_mib=512,graph_limit=262144,descriptor_limit=65536,compact=False):
    base.LIMIT=work_limit;base.prepare(destination)
    changes=[]
    def patch(relative,old,new,count=None):changes.append({'file':relative,'old':old,'new':new,'count':edit(destination/relative,old,new,count)})
    patch('generated/ia_trace.cpp','max_walk=16384',f'max_walk={WALK}',1)
    for relative in ['generated/ia_trace.cpp','generated/ia_graph.cpp','sources/incremental.inc']:
        patch(relative,'depth>24',f'depth>{DEPTH}')
    for relative in ['sources/incremental.inc','sources/evidence_store.hpp','generated/ia_graph.cpp','generated/bounded_views.inc']:
        patch(relative,'16384',str(WALK))
    patch('sources/incremental.inc','depth+memo.height>24',f'depth+memo.height>{DEPTH}',1)
    patch('sources/incremental.inc','s.walked-begin,24,',f's.walked-begin,{DEPTH},',1)
    patch('sources/incremental.inc','s.walked,24,',f's.walked,{DEPTH},',1)
    patch('CMakeLists.txt','/LARGEADDRESSAWARE)', '/LARGEADDRESSAWARE /STACK:16777216)',1)
    if evidence_mib!=512:
        patch('sources/evidence_store.hpp','encoded_byte_limit=512*1024*1024',f'encoded_byte_limit=size_t({evidence_mib})*1024*1024',1)
        patch('sources/runner.cpp','report["encoded_byte_limit"]=512*1024*1024;',f'report["encoded_byte_limit"]=uint64_t({evidence_mib})*1024*1024;',1)
    if descriptor_limit!=65536:
        patch('sources/evidence_store.hpp','descriptor_limit=65536',f'descriptor_limit={descriptor_limit}',1)
        patch('sources/incremental.inc','"descriptor_limit",65536','"descriptor_limit",IncEvidenceStore::descriptor_limit',1)
    if graph_limit!=262144:
        patch('generated/ia_graph.cpp','s.nodes.size()>=262144',f's.nodes.size()>={graph_limit}',1)
        patch('generated/ia_graph.cpp','s.uses.size()>=262144',f's.uses.size()>={graph_limit}',1)
    if compact:
        patch('sources/incremental.inc','    if(collected)for(const auto& [id,o]:x.objects)',
              '    if(getenv("IA_SIZING_COMPACT_CHECKPOINT"))return {{"measurement_only",true},{"evidence_collected",collected}};\n    if(collected)for(const auto& [id,o]:x.objects)',1)
        patch('generated/ia_graph.cpp','const char* ia_slice_graph(lua_State* L){auto& s=get(L);',
              'const char* ia_slice_graph(lua_State* L){auto& s=get(L);if(getenv("IA_SIZING_COMPACT_CHECKPOINT")){s.scratch=Json({{"failure",s.failure},{"measurement_only",true}}).dump();return s.scratch.c_str();}',1)
        with (destination/'generated/ia_trace.cpp').open('a',encoding='utf-8') as handle:handle.write('''
extern "C" const char* ia_slice_graph(lua_State* L);
extern "C" __declspec(dllexport) const char* ia_sizing_compare_checkpoints(lua_State* L){
    static std::string result;auto& b=ia_bounded_budget(L);
    auto delta=[](const auto& before,const auto& after){Json d=Json::object();for(const auto& [k,v]:after){auto it=before.find(k);auto prior=it==before.end()?0:it->second;if(v!=prior)d[k]=v-prior;}return d;};
    _putenv_s("IA_SIZING_COMPACT_CHECKPOINT","");auto before=b.categories;
    auto full=Json::parse(ia_trace_status(L));auto graph_full=Json::parse(ia_slice_graph(L));auto middle=b.categories;auto first=delta(before,middle);
    _putenv_s("IA_SIZING_COMPACT_CHECKPOINT","1");auto small=Json::parse(ia_trace_status(L));auto graph_small=Json::parse(ia_slice_graph(L));auto second=delta(middle,b.categories);
    bool equal=first==second&&full.at("failure")==small.at("failure")&&graph_full.at("failure")==graph_small.at("failure");
    result=Json({{"same_context",true},{"passed",equal},{"full_charge",first},{"compact_charge",second},{"full_and_compact_failures_equal",full.at("failure")==small.at("failure")&&graph_full.at("failure")==graph_small.at("failure")},{"final_work_used",b.used}}).dump();return result.c_str();
}
''')
        boundary_source=(ROOT/'incremental_ui_runtime/boundary_tests.cpp').read_text(encoding='utf-8')
        needle='        if(traced)report["trace"]=Json::parse(api.trace.status(L));'
        if boundary_source.count(needle)!=1:raise ValueError('Checkpoint probe source mismatch')
        boundary_source=boundary_source.replace(needle,needle+'''\n        if(traced){auto compare=reinterpret_cast<const char*(__cdecl*)(BridgeLuaState*)>(GetProcAddress(module,"ia_sizing_compare_checkpoints"));if(!compare)throw std::runtime_error("Same-context checkpoint comparison required");report["checkpoint_cost_comparison"]=Json::parse(compare(L));}''')
        (destination/'sources/checkpoint_tests.cpp').write_text(boundary_source,encoding='utf-8')
        with (destination/'CMakeLists.txt').open('a',encoding='utf-8') as handle:handle.write('''
add_executable(authority-sizing-checkpoint-tests sources/checkpoint_tests.cpp)
target_link_libraries(authority-sizing-checkpoint-tests PRIVATE authority_lua_bridge)
target_link_options(authority-sizing-checkpoint-tests PRIVATE /LARGEADDRESSAWARE /STACK:16777216)
''')
    with (destination/'generated/ia_graph.cpp').open('a',encoding='utf-8') as handle:handle.write('''
extern "C" __declspec(dllexport) const char* ia_initialization_graph_counts(){
    static std::string result;Json rows=Json::array();for(auto& [L,s]:states)if(s.enabled)rows.push_back({{"nodes",s.nodes.size()},{"consumption_records",s.uses.size()},{"storage_versions",s.storage.size()},{"failure",s.failure}});result=rows.dump();return result.c_str();}
''')
    patch('sources/runner.cpp','auto rows=Json::parse(sizing());if(rows.size()!=1)throw std::runtime_error("Sizing context is not unique");return rows.at(0);',
          'auto rows=Json::parse(sizing());if(rows.size()!=1)throw std::runtime_error("Sizing context is not unique");auto counter=reinterpret_cast<const char*(__cdecl*)()>(GetProcAddress(module,"ia_initialization_graph_counts"));if(!counter)throw std::runtime_error("Graph sizing counter required");auto graphs=Json::parse(counter());if(graphs.size()!=1)throw std::runtime_error("Graph sizing context is not unique");auto result=rows.at(0);result["graph_counts"]=graphs.at(0);return result;',1)
    # Measurements retain every walked value and charge; enrich only refusal text.
    patch('sources/incremental.inc','throw std::runtime_error("Trace marking budget exceeded");',
          'throw std::runtime_error("Trace marking budget exceeded: walked="+std::to_string(s.walked)+" depth="+std::to_string(depth)+" walk_limit='+str(WALK)+' depth_limit='+str(DEPTH)+'");',2)
    derivation=json.loads((destination/'derivation.json').read_bytes())
    derivation.update({'probe_logical_walk_limit':WALK,'probe_depth_limit':DEPTH,'probe_stack_bytes':16777216,'probe_encoded_byte_limit':evidence_mib*1024*1024,'probe_graph_node_limit':graph_limit,'probe_graph_use_limit':graph_limit,'probe_descriptor_limit':descriptor_limit,'compact_checkpoint_available':compact,'records_retained_in_runtime':True,'checkpoint_charges_preserved':True,'watchdog_seconds':WATCHDOG,'single_walk_limits_changed':True,'walk_patch_records':changes,'prior_probe_report_sha256':digest(ROOT/'reports/ui-incremental-completion-sizing.json'),'probe_tool_sha256':digest(Path(__file__))})
    write(destination/'derivation.json',derivation)
    # Increase only the independent runner's watchdog, never a work ledger.
    # Original run() uses 120 s; the wrapper supplies a measured 300 s timeout.

def boundaries(destination):
    binary=ROOT/'build-ui-incremental-encoded-v3-release/Release';dll=destination/'build/Release/ia_lua533_ui_incremental.dll'
    output=destination/'boundaries';output.mkdir(exist_ok=False);rows=[]
    derivation=json.loads((destination/'derivation.json').read_bytes())
    runner=destination/'build/Release/authority-sizing-checkpoint-tests.exe' if derivation.get('compact_checkpoint_available') else binary/'authority-incremental-boundary-tests.exe'
    for name in ['depth','walk']:
        path=output/(name+'.json');result=subprocess.run([str(runner),str(dll),digest(dll),'trace',name],capture_output=True,timeout=60)
        path.write_bytes(result.stdout);(output/(name+'.stderr')).write_bytes(result.stderr)
        if result.returncode:raise ValueError('Relaxed boundary process failed')
        report=json.loads(result.stdout);b=report['trace']['bounded_work']
        if not report['success'] or report.get('value')!=1 or b['failure'] or b['used']!=sum(b['categories'].values()):raise ValueError('Relaxed boundary did not complete faithfully')
        row={'id':name,'value':report['value'],'work_used':b['used'],'runtime_sha256':report['runtime_sha256'],'source_sha256':report['source_sha256'],'old_boundary_now_completed':True}
        derivation=json.loads((destination/'derivation.json').read_bytes())
        if derivation.get('compact_checkpoint_available'):
            proof=report['checkpoint_cost_comparison']
            if not proof['passed'] or not proof['same_context']:raise ValueError('Same-context compact checkpoint exact work ledger differs')
            row['checkpoint_cost_comparison']=proof
            row['compact_and_full_checkpoint_ledger_equal']=True
        rows.append(row)
    write(output/'boundary-result.json',{'measurement_only':True,'cases':rows,'formal_old_boundary_expectations_unchanged':True})
    print(json.dumps(rows),flush=True)

class SizingProcess(subprocess.Popen):
    def wait(self,timeout=None):
        return super().wait(timeout=WATCHDOG if timeout==120 else timeout)

def finalize(destination):
    base.LIMIT=json.loads((destination/'derivation.json').read_bytes())['probe_work_limit']
    base.finalize(destination)
    result=json.loads(REPORT.read_bytes());result['schema']='isaac-relaxed-walk-completion-sizing-1'
    result['probe_logical_walk_limit']=WALK;result['probe_depth_limit']=DEPTH;result['single_walk_limits_changed']=True
    result['relaxed_boundary_cases_completed']=len(json.loads((destination/'boundaries/boundary-result.json').read_bytes())['cases'])
    result['watchdog_seconds']=WATCHDOG
    result['probe_encoded_byte_limit']=result['derivation']['probe_encoded_byte_limit']
    result['compact_checkpoints_used']=result['derivation'].get('compact_checkpoint_available',False)
    write(destination/'results/completion-sizing.json',result);write(REPORT,result)

def recover(destination):
    """Recover only fully serialized case prefixes; never accept a crashed process."""
    output=destination/'results';path=output/'progress.json';rows=json.loads(path.read_bytes())
    for row in rows:
        if row['exit_code']==0 or row.get('sizing'):continue
        raw=(output/(row['id']+'.json')).read_text(encoding='utf-8',errors='strict')
        try:
            case,end=json.JSONDecoder().raw_decode(raw[raw.index('[')+1:])
            if case['id']!=row['id']:raise ValueError('Recovered case identity differs')
            for key in ['initialization_passed','contract_passed','first_unsupported_entry','after_modules','sizing','observations','world','source_unchanged','host_stack_restored']:row[key]=case.get(key)
            row['recovered_case_prefix']=True;row['process_completed']=False
            if row.get('sizing'):
                cost=row['sizing']
                if cost['work_used']!=sum(cost['categories'].values()):raise ValueError('Recovered prefix ledger differs')
        except json.JSONDecodeError:row['case_prefix_incomplete']=True
    write(path,rows)
    report_path=output/'completion-sizing.json'
    if report_path.exists():
        result=json.loads(report_path.read_bytes());result['cases']=rows;write(report_path,result);write(REPORT,result)
    print(json.dumps([{'id':r['id'],'exit_code':r['exit_code'],'work':r.get('sizing',{}).get('work_used'),'error':r.get('first_unsupported_entry'),'recovered':r.get('recovered_case_prefix',False)} for r in rows],ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','boundaries','run','finalize','recover']);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--probe-work-limit',type=int,choices=[100000000,250000000,500000000],default=100000000);parser.add_argument('--probe-evidence-mib',type=int,choices=[512,1024,1536,2048],default=512);parser.add_argument('--probe-graph-limit',type=int,choices=[262144,1048576],default=262144);parser.add_argument('--probe-descriptor-limit',type=int,choices=[65536,131072],default=65536);parser.add_argument('--compact-checkpoints',action='store_true');parser.add_argument('--cases',nargs='+',default=['eid-en','eid-zh','combined-en','combined-zh']);args=parser.parse_args();destination=args.directory.resolve()
    if args.phase=='prepare':prepare(destination,args.probe_work_limit,args.probe_evidence_mib,args.probe_graph_limit,args.probe_descriptor_limit,args.compact_checkpoints)
    elif args.phase=='boundaries':boundaries(destination)
    elif args.phase=='finalize':finalize(destination)
    elif args.phase=='recover':recover(destination)
    else:
        base.LIMIT=json.loads((destination/'derivation.json').read_bytes())['probe_work_limit']
        if json.loads((destination/'derivation.json').read_bytes()).get('compact_checkpoint_available'):os.environ['IA_SIZING_COMPACT_CHECKPOINT']='1'
        subprocess.Popen=SizingProcess
        base.run(destination,args.cases)
        finalize(destination)
