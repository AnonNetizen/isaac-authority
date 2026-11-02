"""Compare independent 5M processes at identical frozen source and limit."""
import argparse,json,statistics,sys
from pathlib import Path
sys.dont_write_bytecode=True
from measure_incremental_budget import measure
from run_incremental_ui import write

def run(baseline,candidate,output,runs):
    if not 1<=runs<=10:raise ValueError('Use 1 to 10 repeats')
    output.mkdir(parents=True,exist_ok=False)
    for name in ['baseline','candidate']:(output/name).mkdir()
    rows=[]
    for repeat in range(1,runs+1):
        for case in ['mcm-en','eid-en']:
            for name,binary in [('baseline',baseline),('candidate',candidate)]:
                row=measure(binary,5000000,case,repeat,output/name);row['variant']=name
                raw=json.loads((output/name/f'5000000-{case}-{repeat}.json').read_bytes())['cases'][0]
                t=raw['execution_dependencies']['runtime'];row['executed_lua_instructions']=t['instructions'];row['scalar_leaf_hits']=t['incremental'].get('scalar_leaf_mark_cache_hits',0)
                rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='markers'}),flush=True)
    summary={}
    for name in ['baseline','candidate']:
        summary[name]={}
        for case in ['mcm-en','eid-en']:
            samples=[r for r in rows if r['variant']==name and r['case']==case]
            summary[name][case]={k:statistics.median(r[k] for r in samples) for k in ['seconds_traced_initialization_to_outcome','outcome_working_set_mib','peak_process_working_set_mib','executed_lua_instructions','scalar_leaf_hits']}
            summary[name][case]['initialization_passed_all']=all(r['initialization_passed'] for r in samples)
    result={'schema':'isaac-incremental-optimization-comparison-1','work_limit':5000000,'samples':rows,'summary_medians':summary,'timing_scope':'after untraced bootstrap until initialization completes or refuses; excludes report serialization','memory_scope':'process working set at outcome; peak includes harness, resources and reporting','interpretation':'A cap refusal at a later instruction is progress evidence, not initialization success; elapsed times at different refusal points are not equal-work speedups. Lua table iteration may alter exact prefixes.','game_process_used':False,'oracle_enabled':False}
    write(output/'comparison.json',result);print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--runs',type=int,default=2);a=p.parse_args();run(a.baseline.resolve(),a.candidate.resolve(),a.output.resolve(),a.runs)
