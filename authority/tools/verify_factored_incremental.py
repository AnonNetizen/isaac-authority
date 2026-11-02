"""Verify lossless site factoring against the unfactored completed model runs."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import write,digest,ROOT,cache_witnesses

def expand(incremental):
    sites=incremental.get('cache_sites',[]);events=[]
    for raw in incremental['cache_events']:
        event=dict(raw)
        if 'site_ref' in event:
            index=event.pop('site_ref')
            if not 1<=index<=len(sites):raise ValueError('Unresolved site reference')
            event['site']=sites[index-1]
        events.append(event)
    return events

def run(before,after,target):
    manifest=ROOT/'research/ui_incremental_oracle_v5.json';spec=json.loads(manifest.read_bytes());rows=[]
    for case in spec['cases']:
        old=json.loads((before/(case['id']+'-incremental.json')).read_bytes());new=json.loads((after/(case['id']+'-incremental.json')).read_bytes())
        a=old['trace']['incremental'];b=new['trace']['incremental']
        normal=all(old.get(k)==new.get(k) for k in ['success','values','origins','error','value_graph','value_ids'])
        events=a['cache_events']==expand(b);objects=a['objects']==b['objects']
        same_counts=all(a.get(k)==b.get(k) for k in ['mark_cache_hits','monotone_mark_cache_hits','scalar_leaf_mark_cache_hits','aggregate_cache_hits','invalidations','mutations','full_oracle_checks','full_oracle_calls'])
        row={'id':case['id'],'ordinary_origins_and_full_value_graph_equal':normal,'expanded_events_equal':events,'object_versions_equal':objects,'all_existing_counters_equal':same_counts,'site_intern_hits':b['site_intern_hits'],'cache_witness_checks':cache_witnesses(new['trace'])};rows.append(row)
    result={'passed':all(all(r[k] for k in ['ordinary_origins_and_full_value_graph_equal','expanded_events_equal','object_versions_equal','all_existing_counters_equal']) for r in rows),'cases':rows,'manifest_sha256':digest(manifest),'before_runtime_sha256':json.loads((before/'oracle-result.json').read_bytes())['runtime_sha256'],'after_runtime_sha256':json.loads((after/'oracle-result.json').read_bytes())['runtime_sha256'],'source_or_producer_ids_normalized':False,'evidence_consumptions_removed':False,'game_process_used':False}
    target.open('x',encoding='utf-8').write(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
    if not result['passed']:raise ValueError('Factoring changed ordinary computation or evidence')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.before.resolve(),a.after.resolve(),a.output.resolve())
