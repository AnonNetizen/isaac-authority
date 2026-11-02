"""Gated command-line origin oracle, ordinary Lua equivalence, and real initialization."""
import argparse,gc,hashlib,json,os,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def real_manifest(work_limit):
    names={2000000:'ui_incremental_suite_v1.json',5000000:'ui_incremental_suite_5m_v3.json',10000000:'ui_incremental_suite_10m_v1.json'}
    return ROOT/'research'/names[work_limit]
def invoke(command,p,verify=False):
    env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None)
    if verify:env['IA_INCREMENTAL_VERIFY']='1'
    with p.open('xb') as out,p.with_suffix('.stderr.txt').open('xb') as err:
        result=subprocess.run([str(c) for c in command],stdout=out,stderr=err,timeout=600,env=env)
    if result.returncode:raise RuntimeError(f'{p}: process {result.returncode}; inspect stderr')
    return json.loads(p.read_bytes())
class EvidenceEvents:
    """Lossless logical sequence; avoids holding an expanded real prefix in RAM."""
    def __init__(self,incremental):
        self.incremental=incremental;self.direct=incremental.get('cache_events')
        if self.direct is not None:return
        if incremental['schema']!='isaac-incremental-versions-5':raise ValueError('Unknown evidence format')
        self.descriptors=incremental['cache_descriptors'];self.uses=incremental['cache_uses'];meta=incremental['evidence_encoding']
        if meta['schema']!='isaac-evidence-descriptors-1' or meta['logical_events']!=len(self.uses) or len(self.descriptors)>65536 or len(self.uses)>10000000 or meta['encoded_byte_limit']!=64*1024*1024 or not 0<=meta['encoded_bytes']<=meta['encoded_byte_limit']:raise ValueError('Encoded evidence capacity mismatch')
        encoded=sum(len(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())*2 for d in self.descriptors)+24*len(self.uses)
        if encoded!=meta['encoded_bytes']:raise ValueError('Encoded evidence byte accounting differs')
        for d in self.descriptors:
            if set(d)&{'event','epoch','site_ref','logical_walk_before','logical_walk_after'}:raise ValueError('Use operands leaked into descriptor')
    def __len__(self):return len(self.direct) if self.direct is not None else len(self.uses)
    def __getitem__(self,index):
        if self.direct is not None:return self.direct[index]
        if not 0<=index<len(self.uses):raise IndexError(index)
        u=self.uses[index]
        if len(u)!=5 or any(type(v)!=int for v in u):raise ValueError('Unknown evidence use operands')
        descriptor,epoch,site,before,after=u
        if not 1<=descriptor<=len(self.descriptors) or not 0<=site<=len(self.incremental['cache_sites']) or not -(1<<63)<=epoch<(1<<63):raise ValueError('Unresolved use identity or context')
        if (before==-1)!=(after==-1) or (before!=-1 and not (0<=before<=16384 and 0<=after<=16384)):raise ValueError('Invalid logical walk operands')
        result=dict(self.descriptors[descriptor-1]);result['event']=index+1;result['epoch']=epoch
        if site:result['site_ref']=site
        if before!=-1:result['logical_walk_before']=before;result['logical_walk_after']=after
        return result
def expanded_incremental(incremental):
    if 'cache_events' in incremental:return incremental
    result=dict(incremental)
    for name in ['cache_descriptors','cache_uses','evidence_encoding']:result.pop(name)
    result['schema']='isaac-incremental-versions-4';result['cache_events']=list(EvidenceEvents(incremental));return result
def cache_witnesses(trace):
    events=EvidenceEvents(trace['incremental']);checks=0
    for index,event in enumerate(events,1):
        if event['event']!=index:raise ValueError('Non-contiguous cache evidence')
        if 'site_ref' in event:
            sites=trace['incremental']['cache_sites'];site=event['site_ref']
            if not 1<=site<=len(sites) or set(sites[site-1])!={'source_sha256','prototype','instruction','activation'}:raise ValueError('Unknown or incomplete evidence site')
        if event['operation'].endswith('_cache_hit'):
            at=event['completed_walk_event']
            if not 1<=at<index:raise ValueError('Cache reused incomplete/future traversal')
            before=events[at-1]
            if before['object']!=event['object']:raise ValueError('Cache identity witness mismatch')
            if before['operation'] in ['complete_root_mark','complete_scalar_leaf_mark']:
                if before['sources']!=event['sources']:raise ValueError('Mark source witness mismatch')
                if 'coverage_version' in event:
                    if before.get('coverage_version')!=event['coverage_version']:raise ValueError('Destructive write invalidated marking witness')
                    changed=before['root_version']!=event['root_version']
                    if changed!=event['monotone_extensions_since_completion']:raise ValueError('Monotone marking evidence mismatch')
                elif before['root_version']!=event['root_version']:raise ValueError('Cache version witness mismatch')
                if event['operation']=='leaf_mark_cache_hit':
                    if before['operation']!='complete_scalar_leaf_mark' or not before['no_nested_objects'] or not before['no_cycle_cut']:raise ValueError('Incomplete scalar leaf proof')
                    if event['logical_visits']!=before['logical_visits'] or event['height']!=before['height']:raise ValueError('Leaf traversal witness changed')
                    if event['depth']+event['height']>24 or event['logical_walk_after']>16384 or event['logical_walk_after']!=event['logical_walk_before']+event['logical_visits']-1:raise ValueError('Leaf cache bypassed structural budget')
            elif before['root_version']!=event['root_version']:raise ValueError('Aggregate version witness mismatch')
            checks+=1
    return checks
def oracle(binary,output,work_limit=5000000,manifest=None):
    manifest=manifest or ROOT/'research/ui_incremental_oracle_v3.json'
    spec=json.loads(manifest.read_bytes());records=[]
    runtimes={'reference':(binary/'ia_lua533_reference.dll','plain',False),'full':(ROOT/'build-ui-bounded-release/Release/ia_lua533_ui_bounded.dll','trace',False),'incremental':(binary/'ia_lua533_ui_incremental.dll','trace',True)}
    total_checks=0;hits=0;proof_equal=[];repeat_equal=[];witnesses=0;producer_equal=[]
    for case in spec['cases']:
        print('Oracle '+case['id'],flush=True);source=ROOT/case['file']
        if digest(source)!=case['sha256']:raise ValueError('Frozen oracle source changed')
        reports={}
        for name,(dll,mode,verify) in runtimes.items():
            reports[name]=invoke([binary/'authority-trace-research.exe','--evaluate',dll,digest(dll),source,mode],output/(case['id']+'-'+name+'.json'),verify)
        values=[{k:r.get(k) for k in ['success','values','error']} for r in reports.values()]
        matched=values[0]==values[1]==values[2]
        origins=reports['full'].get('origins')==reports['incremental'].get('origins')
        candidate=reports['incremental'];inc=candidate['trace']['incremental'];cost=candidate['trace']['bounded_work']
        second=invoke([binary/'authority-trace-research.exe','--evaluate',binary/'ia_lua533_ui_incremental.dll',digest(binary/'ia_lua533_ui_incremental.dll'),source,'trace'],output/(case['id']+'-incremental-repeat.json'),True)
        exact=candidate==second;repeat_equal.append(exact);witnesses+=cache_witnesses(candidate['trace'])+cache_witnesses(second['trace'])
        producers=candidate['value_graph']==second['value_graph'] and candidate['trace']['incremental']==second['trace']['incremental'];producer_equal.append(producers)
        if cost['limit']!=work_limit:raise ValueError('Compiled DLL work limit differs from requested profile')
        leaf_hits=inc.get('scalar_leaf_mark_cache_hits',0)
        passed=matched and origins and candidate['success'] and not cost['failure'] and cost['used']<=work_limit and cost['used']==sum(cost['categories'].values()) and inc['full_oracle_checks']>0 and leaf_hits>=case.get('minimum_scalar_leaf_hits',0)
        index=candidate['trace'].get('incremental_index',{})
        passed=passed and index.get('hash_moves',0)>=case.get('minimum_index_hash_moves',0) and index.get('updates',0)>=case.get('minimum_index_updates',0) and index.get('oracle_slot_checks',0)>=case.get('minimum_index_oracle_checks',0)
        encoded=inc.get('evidence_encoding',{})
        passed=passed and encoded.get('cached_descriptor_uses',0)>=case.get('minimum_cached_descriptor_uses',0)
        if 'evidence_encoding_requirements' in spec:
            required=spec['evidence_encoding_requirements']
            passed=passed and inc.get('schema')==required['runtime_schema'] and encoded.get('descriptor_limit')==required['descriptor_limit'] and encoded.get('encoded_byte_limit')==required['encoded_byte_limit'] and encoded.get('every_logical_use_charged') is True
        kind=case.get('case_kind','functional')
        if kind=='safety':passed=not candidate['success'] and not reports['full']['success'] and case['expected_unsupported'] in candidate.get('error','') and case['expected_unsupported'] in reports['full'].get('error','') and origins
        full_graph_equal=reports['full'].get('value_graph')==candidate.get('value_graph');proof_equal.append(full_graph_equal)
        total_checks+=inc['full_oracle_checks'];hits+=inc['mark_cache_hits']+inc['aggregate_cache_hits']
        records.append({'id':case['id'],'case_kind':kind,'compatibility_passed':kind=='functional' and passed,'passed':passed,'ordinary_result_equal':matched,'return_origins_equal':origins,'full_graph_equal':full_graph_equal,'complete_repeat_identical':exact,'complete_value_graph_and_cache_evidence_identical':producers,'oracle_checks':inc['full_oracle_checks'],'oracle_calls':inc['full_oracle_calls'],'mark_hits':inc['mark_cache_hits'],'aggregate_hits':inc['aggregate_cache_hits'],'scalar_leaf_hits':leaf_hits,'monotone_hits':inc.get('monotone_mark_cache_hits',0),'used':cost['used'],'first_failure':candidate.get('error'),'source_sha256':case['sha256']})
        del reports;gc.collect()
    upvalues={}
    for name,(dll,mode,verify) in runtimes.items():upvalues[name]=invoke([binary/'authority-incremental-upvalue-tests.exe',dll,digest(dll),mode],output/('upvalues-'+name+'.json'),verify)
    same_upvalue_values=[c['value'] for c in upvalues['reference']['observations']]==[c['value'] for c in upvalues['full']['observations']]==[c['value'] for c in upvalues['incremental']['observations']]
    same_upvalue_origins=[c['origins'] for c in upvalues['full']['observations']]==[c['origins'] for c in upvalues['incremental']['observations']]
    result={'schema':'isaac-incremental-oracle-result-1','runtime_sha256':digest(binary/'ia_lua533_ui_incremental.dll'),'suite_sha256':digest(manifest),'cases':records,'passed':all(c['passed'] for c in records) and all(producer_equal) and hits>0 and same_upvalue_values and same_upvalue_origins,'upvalue_c_api_equal':same_upvalue_values and same_upvalue_origins,'per_origin_checks':total_checks+upvalues['incremental']['trace']['incremental']['full_oracle_checks'],'cache_hits':hits,'cache_witness_checks':witnesses,'complete_repeat_identical_all':all(repeat_equal),'same_vm_full_walk_oracle':True,'oracle_work_charged':True,'complete_graph_equal_all':all(proof_equal),'work_limit':work_limit}
    result['complete_value_graph_and_cache_evidence_repeated_identically']=all(producer_equal)
    result['raw_budget_ledger_preserved']=True
    write(output/'oracle-result.json',result)
    print(json.dumps(result,ensure_ascii=False))
    return result
def outcomes(r):return [{k:c.get(k) for k in ('id','case_kind','initialization_passed','contract_passed','compatibility_passed','diagnostic_passed','observations','world','source_unchanged','host_stack_restored','post_refusal_execution_blocked')} for c in r['cases']]
def real(binary,output,work_limit=5000000):
    suite=real_manifest(work_limit);runner=binary/'authority-ui-incremental-research.exe'
    specs={'reference':(binary/'ia_lua533_reference.dll','--suite-reference'),'incremental':(binary/'ia_lua533_ui_incremental.dll','--suite')};results={};raw_equal={};costs={}
    for name,(dll,flag) in specs.items():
        first=None
        for repeat in [1,2]:
            print(f'Real {name} {repeat}',flush=True)
            r=invoke([runner,flag,dll,digest(dll),ROOT/'research/slice3_ui_inputs',ROOT,suite],output/f'{name}-{repeat}.json')
            if first is not None:
                if outcomes(r)!=outcomes(first):raise ValueError('Repeated functional outputs differ: '+name)
                raw_equal[name]=r['cases']==first['cases']
            else:first=r
            if name=='incremental':
                costs[repeat]={}
                for c in r['cases']:
                    b=c['execution_dependencies']['runtime']['bounded_work'];i=c['execution_dependencies']['runtime']['incremental']
                    if b['limit']!=work_limit or b['used']>work_limit or b['used']!=sum(b['categories'].values()):raise ValueError('Uncharged cost or mismatched budget')
                    cache_witnesses(c['execution_dependencies']['runtime'])
                    costs[repeat][c['id']]={'used':b['used'],'categories':b['categories'],'failure':b['failure'],'mark_hits':i['mark_cache_hits'],'aggregate_hits':i['aggregate_cache_hits'],'invalidations':i['invalidations'],'object_count':i['object_count']}
            if repeat==2:del r;gc.collect()
        results[name]=first
    reference={c['id']:c for c in results['reference']['cases']}
    for c in results['incremental']['cases']:
        if c['compatibility_passed'] and c['observations']!=reference[c['id']]['observations']:raise ValueError('Candidate functional output differs from unmodified Lua')
    result={'schema':'isaac-incremental-real-result-1','manifest_sha256':digest(suite),'runtime_sha256':digest(binary/'ia_lua533_ui_incremental.dll'),'functional_passed':[c['id'] for c in results['incremental']['cases'] if c['compatibility_passed']],'functional_failed':[c['id'] for c in results['incremental']['cases'] if c['case_kind']=='functional' and not c['compatibility_passed']],'safety_diagnostics_passed':results['incremental']['safety_diagnostics_passed'],'functional_outputs_repeated_identically':True,'complete_case_evidence_repeated_identically':raw_equal,'costs':costs,'work_limit':work_limit,'draw_capture_navigation_started':False,'game_process_used':False}
    write(output/'real-result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='costs'},ensure_ascii=False));return result
def preserved():
    before=json.loads((ROOT/'reports/ui-incremental-baseline.json').read_bytes())
    for name,expected in before.items():
        if digest(ROOT/name)!=expected:raise ValueError('Historical artifact changed '+name)
    return len(before)
def run(binary,output,phase,prior,work_limit=5000000,oracle_manifest=None):
    oracle_manifest=oracle_manifest or ROOT/'research/ui_incremental_oracle_v3.json'
    output.mkdir(parents=True,exist_ok=False);before=preserved();write(output/'preserved.json',{'files':before,'unchanged':True})
    if phase in ['oracle','all']:
        o=oracle(binary,output,work_limit,oracle_manifest)
        if not o['passed']:raise ValueError('Origin oracle gate failed; real initialization not started')
    else:
        proof=json.loads(prior.read_bytes()) if prior else {}
        if not proof.get('passed') or not proof.get('complete_value_graph_and_cache_evidence_repeated_identically') or proof.get('work_limit')!=work_limit or proof.get('runtime_sha256')!=digest(binary/'ia_lua533_ui_incremental.dll') or proof.get('suite_sha256')!=digest(oracle_manifest):raise ValueError('Passed origin and complete model evidence gate for this exact runtime/manifest/budget required')
    if phase in ['real','all']:real(binary,output,work_limit)
    preserved()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['oracle','real','all'],default='all');p.add_argument('--prior-oracle',type=Path);p.add_argument('--oracle-manifest',type=Path);p.add_argument('--work-limit',type=int,choices=[2000000,5000000,10000000],default=5000000);a=p.parse_args();run(a.binary.resolve(),a.output.resolve(),a.phase,a.prior_oracle,a.work_limit,a.oracle_manifest.resolve() if a.oracle_manifest else None)
