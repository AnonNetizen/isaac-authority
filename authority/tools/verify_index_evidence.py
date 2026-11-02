"""Compare every existing cache consumption and producer with the preserved 10M DLL."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,invoke,write,cache_witnesses
def run(after,output):
    output.mkdir(parents=True,exist_ok=False)
    spec=json.loads((ROOT/'research/ui_incremental_oracle_index_v1.json').read_bytes());rows=[]
    baseline=ROOT/'build-ui-incremental-10m-release/Release';dll=baseline/'ia_lua533_ui_incremental.dll'
    for case in spec['cases']:
        old_path=ROOT/'reports/ui-incremental-10m-oracle'/(case['id']+'-incremental.json')
        if old_path.is_file():old=json.loads(old_path.read_bytes())
        else:old=invoke([baseline/'authority-trace-research.exe','--evaluate',dll,digest(dll),ROOT/case['file'],'trace'],output/(case['id']+'-old.json'),True)
        new=json.loads((after/(case['id']+'-incremental.json')).read_bytes());a=old['trace']['incremental'];b=new['trace']['incremental']
        row={'id':case['id'],'ordinary_and_origins_equal':all(old.get(k)==new.get(k) for k in ['success','values','origins','error']),'full_producer_graph_equal':old.get('value_graph')==new.get('value_graph'),'all_cache_consumptions_and_versions_equal':a==b,'index_diagnostics':new['trace']['incremental_index'],'cache_witness_checks':cache_witnesses(new['trace'])};rows.append(row)
    result={'passed':all(all(c[k] for k in ['ordinary_and_origins_equal','full_producer_graph_equal','all_cache_consumptions_and_versions_equal']) for c in rows),'cases':rows,'baseline_runtime_sha256':digest(dll),'candidate_runtime_sha256':json.loads((after/'oracle-result.json').read_bytes())['runtime_sha256'],'work_limit':10000000,'source_or_producer_ids_normalized':False,'consumers_removed':False,'index_slot_oracle_independently_charged':True}
    write(output/'comparison.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
    if not result['passed']:raise ValueError('Index changed established execution evidence')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.after.resolve(),a.output.resolve())
