"""Reproduce verified package cases using relocated sources and local resource hashes."""
import argparse,json,os,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
from bundle_incremental_ui import digest,extract,write
def invoke(cmd,target,verify=False):
    env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None)
    if verify:env['IA_INCREMENTAL_VERIFY']='1'
    with target.open('xb') as out,target.with_suffix('.stderr.txt').open('xb') as err:
        result=subprocess.run([str(v) for v in cmd],stdout=out,stderr=err,timeout=600,env=env)
    if result.returncode:raise ValueError('Reproduction process failed '+str(target))
    return json.loads(target.read_bytes())
def functional(r):return [{k:c.get(k) for k in ['id','case_kind','initialization_passed','contract_passed','compatibility_passed','diagnostic_passed','observations','world','source_unchanged','host_stack_restored','post_refusal_execution_blocked']} for c in r['cases']]
def reproduce(archive,output):
    root,index=extract(archive,output/'unpacked');binary=root/'bin';source=root/'source';reports=output/'results';reports.mkdir()
    checks=[]
    for name,flag,dllname in [('reference','--suite-reference','ia_lua533_reference.dll'),('incremental','--suite','ia_lua533_ui_incremental.dll')]:
        dll=binary/dllname;r=invoke([binary/'authority-ui-incremental-research.exe',flag,dll,digest(dll),source/'research/slice3_ui_inputs',source,source/'research/ui_incremental_suite_v1.json'],reports/(name+'.json'))
        old=json.loads((root/'reports/ui-incremental-real-liveness'/(name+'-1.json')).read_bytes());same=functional(r)==functional(old)
        checks.append({'kind':'real','runtime':name,'functional_outcomes_equal':same,'complete_evidence_equal':r['cases']==old['cases']})
        if not same:raise ValueError('Relocated functional outcomes changed')
    spec=json.loads((source/'research/ui_incremental_oracle_v3.json').read_bytes());dll=binary/'ia_lua533_ui_incremental.dll';origin_checks=0
    for case in spec['cases']:
        fixture=source/case['file']
        if digest(fixture)!=case['sha256']:raise ValueError('Frozen fixture hash mismatch')
        r=invoke([binary/'authority-trace-research.exe','--evaluate',dll,digest(dll),fixture,'trace'],reports/(case['id']+'.json'),True)
        old=json.loads((root/'reports/ui-incremental-oracle-liveness'/(case['id']+'-incremental.json')).read_bytes())
        values=all(r.get(k)==old.get(k) for k in ['success','values','origins','error']);graph=r['value_graph']==old['value_graph'];cache=r['trace']['incremental']==old['trace']['incremental']
        origin_checks+=r['trace']['incremental']['full_oracle_checks'];checks.append({'id':case['id'],'kind':'oracle','functional_equal':values,'complete_value_graph_equal':graph,'complete_cache_evidence_equal':cache,'whole_report_equal':r==old})
        if not values or not graph or not cache:raise ValueError('Relocated model origin/proof changed')
    r=invoke([binary/'authority-incremental-upvalue-tests.exe',dll,digest(dll),'trace'],reports/'upvalues.json',True)
    old=json.loads((root/'reports/ui-incremental-oracle-liveness/upvalues-incremental.json').read_bytes());same=r['observations']==old['observations']
    if not same:raise ValueError('Relocated C API upvalue results changed')
    origin_checks+=r['trace']['incremental']['full_oracle_checks']
    for name,sha in index['files'].items():
        if digest(root/name)!=sha:raise ValueError('Extracted file changed during reproduction '+name)
    real_result=json.loads((root/'reports/ui-incremental-real-liveness/real-result.json').read_bytes())
    real_gate=not real_result['functional_failed'] and real_result['safety_diagnostics_passed']
    result={'schema':'isaac-incremental-reproduction-1','archive_sha256':digest(archive),'verified_files_before_and_after':len(index['files']),'checks':checks,'origin_checks':origin_checks,'c_api_upvalue_observations_equal':same,'game_process_used':False,'real_gate_passed':real_gate,'whole_evidence_equality_claimed':False,'model_complete_value_graph_and_cache_evidence_equal':all(c.get('complete_value_graph_equal',True) and c.get('complete_cache_evidence_equal',True) for c in checks)}
    write(reports/'reproduction.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();reproduce(a.archive.resolve(),a.output.resolve())
