"""Require exact expansion, producer and version equality with the index candidate."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,write,expanded_incremental,cache_witnesses
def run(before,after,target):
    spec=json.loads((ROOT/'research/ui_incremental_oracle_index_v1.json').read_bytes());rows=[]
    for case in spec['cases']:
        name=case['id']+'-incremental.json';a=json.loads((before/name).read_bytes());b=json.loads((after/name).read_bytes())
        ia=a['trace']['incremental'];ib=b['trace']['incremental'];expanded=expanded_incremental(ib)
        normal=all(a.get(k)==b.get(k) for k in ['success','values','origins','error','value_graph','value_ids'])
        rows.append({'id':case['id'],'ordinary_and_all_producers_equal':normal,'all_expanded_evidence_and_versions_equal':ia==expanded,'logical_events':len(expanded['cache_events']),'descriptors':len(ib['cache_descriptors']),'capacity':ib['evidence_encoding'],'witness_checks':cache_witnesses(b['trace'])})
    result={'passed':all(c['ordinary_and_all_producers_equal'] and c['all_expanded_evidence_and_versions_equal'] for c in rows),'cases':rows,'logical_consumers_removed':False,'source_or_producer_ids_normalized':False,'work_limit':10000000,'baseline_runtime_sha256':json.loads((before/'oracle-result.json').read_bytes())['runtime_sha256'],'candidate_runtime_sha256':json.loads((after/'oracle-result.json').read_bytes())['runtime_sha256']}
    write(target,result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
    if not result['passed']:raise ValueError('Compressed evidence loses execution proof')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.before.resolve(),a.after.resolve(),a.output.resolve())
