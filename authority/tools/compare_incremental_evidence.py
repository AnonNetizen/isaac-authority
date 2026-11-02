"""Compare complete evidence components; keep all original files and numerical IDs."""
import argparse,json
from pathlib import Path
def compare(folder):
    spec=json.loads((Path(__file__).resolve().parents[1]/'research/ui_incremental_oracle_v3.json').read_bytes());rows=[]
    for c in spec['cases']:
        a=json.loads((folder/(c['id']+'-incremental.json')).read_bytes());b=json.loads((folder/(c['id']+'-incremental-repeat.json')).read_bytes())
        rows.append({'id':c['id'],'whole_report_equal':a==b,'complete_value_graph_equal':a['value_graph']==b['value_graph'],'complete_cache_evidence_equal':a['trace']['incremental']==b['trace']['incremental'],'budget_ledger_equal':a['trace']['bounded_work']==b['trace']['bounded_work'],'return_origins_equal':a['origins']==b['origins'],'changed_top_level_components':[k for k in a if a[k]!=b[k]]})
    result={'schema':'isaac-incremental-evidence-comparison-1','cases':rows,'complete_value_graph_equal_all':all(c['complete_value_graph_equal'] for c in rows),'complete_cache_evidence_equal_all':all(c['complete_cache_evidence_equal'] for c in rows),'whole_report_equal_all':all(c['whole_report_equal'] for c in rows),'normalization_or_id_removal_used':False,'original_reports_preserved':True,'scope':'finite origin fixtures; no assertion about actual MCM/EID initialization or arbitrary execution ordering'}
    with (folder/'evidence-comparison.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);compare(p.parse_args().folder)
