"""Reproduce the relocated 5M candidate, origin proofs and structural boundaries."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from bundle_incremental_optimization import extract
from run_incremental_ui import digest,invoke,write,outcomes,cache_witnesses

def reproduce(archive,output):
    root,index=extract(archive,output/'unpacked');binary=root/'bin';source=root/'source';reports=output/'results';reports.mkdir()
    rows=[];dll=binary/'ia_lua533_ui_incremental.dll'
    spec=json.loads((source/'research/ui_incremental_oracle_v5.json').read_bytes());checks=0
    for case in spec['cases']:
        print('Relocated oracle '+case['id'],flush=True);fixture=source/case['file']
        if digest(fixture)!=case['sha256']:raise ValueError('Relocated fixture changed')
        r=invoke([binary/'authority-trace-research.exe','--evaluate',dll,digest(dll),fixture,'trace'],reports/(case['id']+'.json'),True)
        old=json.loads((root/'reports/ui-incremental-factored-oracle'/(case['id']+'-incremental.json')).read_bytes())
        ordinary=all(r.get(k)==old.get(k) for k in ['success','values','origins','error','value_ids']);graph=r['value_graph']==old['value_graph'];cache=r['trace']['incremental']==old['trace']['incremental']
        b=r['trace']['bounded_work'];budget=b['limit']==5000000 and b['used']<=5000000 and b['used']==sum(b['categories'].values())
        checks+=r['trace']['incremental']['full_oracle_checks'];cache_witnesses(r['trace'])
        rows.append({'kind':'oracle','id':case['id'],'ordinary_equal':ordinary,'complete_graph_equal':graph,'complete_cache_equal':cache,'budget_valid':budget})
        if not all([ordinary,graph,cache,budget]):raise ValueError('Relocated model proof differs')
    r=invoke([binary/'authority-incremental-upvalue-tests.exe',dll,digest(dll),'trace'],reports/'upvalues.json',True)
    old=json.loads((root/'reports/ui-incremental-factored-oracle/upvalues-incremental.json').read_bytes())
    if r['observations']!=old['observations']:raise ValueError('Relocated C API upvalue differs')
    checks+=r['trace']['incremental']['full_oracle_checks']
    for case in json.loads((source/'research/ui_incremental_boundaries_v2.json').read_bytes())['cases']:
        r=invoke([binary/'authority-incremental-boundary-tests.exe',dll,digest(dll),'trace',case['id']],reports/(case['id']+'-boundary.json'))
        old=json.loads((root/'reports/ui-incremental-factored-boundaries'/(case['id']+'-candidate.json')).read_bytes())
        same=r['success']==old['success'] and r.get('error')==old.get('error') and r['trace']['incremental']==old['trace']['incremental']
        if not same:raise ValueError('Relocated structural boundary differs')
        rows.append({'kind':'boundary','id':case['id'],'complete_cache_and_refusal_equal':same})
    for name,flag,dllname in [('reference','--suite-reference','ia_lua533_reference.dll'),('incremental','--suite','ia_lua533_ui_incremental.dll')]:
        print('Relocated real '+name,flush=True);runtime=binary/dllname
        r=invoke([binary/'authority-ui-incremental-research.exe',flag,runtime,digest(runtime),source/'research/slice3_ui_inputs',source,source/'research/ui_incremental_suite_5m_v3.json'],reports/(name+'.json'))
        old=json.loads((root/'reports/ui-incremental-factored-real'/(name+'-1.json')).read_bytes());same=outcomes(r)==outcomes(old)
        rows.append({'kind':'real','runtime':name,'functional_outcomes_equal':same,'complete_evidence_equal':r['cases']==old['cases']})
        if not same:raise ValueError('Relocated real outcomes differ')
        del r,old
    for name,sha in index['files'].items():
        if digest(root/name)!=sha:raise ValueError('Package file changed during replay '+name)
    result={'passed':True,'archive_sha256':digest(archive),'verified_files_before_and_after':len(index['files']),'runtime_sha256':digest(dll),'checks':rows,'origin_checks':checks,'c_api_upvalue_equal':True,'model_complete_graph_and_cache_equal':True,'game_process_used':False,'real_gate_passed':False,'real_complete_evidence_equality_claimed':False}
    write(reports/'reproduction.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();reproduce(a.archive.resolve(),a.output.resolve())
