"""Verify cap-only generated code, preserved artifacts and completed 10M results."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,write

def run(output):
    baseline=ROOT/'reports/ui-incremental-10m-baseline'
    snapshot=json.loads((baseline/'snapshot.json').read_bytes())
    for name,sha in snapshot['files'].items():
        if digest(baseline/'files'/name)!=sha:raise ValueError('Saved 5M snapshot changed')
    old=ROOT/'build-ui-incremental-factored/incremental_ui_runtime/generated-lua'
    new=ROOT/'build-ui-incremental-10m/incremental_ui_runtime/generated-lua'
    names={p.name for p in old.iterdir() if p.is_file()}
    if names!={p.name for p in new.iterdir() if p.is_file()}:raise ValueError('Generated file list changed')
    differences=[name for name in sorted(names) if (old/name).read_bytes()!=(new/name).read_bytes()]
    if differences!=['bounded_cfg.hpp'] or (old/'bounded_cfg.hpp').read_bytes().replace(b'5000000',b'10000000')!=(new/'bounded_cfg.hpp').read_bytes():raise ValueError('Generated runtime changed beyond cap')
    algorithm_files=[]
    for name,sha in snapshot['files'].items():
        if name.startswith('incremental_ui_runtime/') and name not in ['incremental_ui_runtime/CMakeLists.txt','incremental_ui_runtime/prepare_lua.py']:
            if digest(ROOT/name)!=sha:raise ValueError('Tracking algorithm source changed')
            algorithm_files.append(name)
        if name.startswith('build-ui-incremental-factored-release/') or name.startswith('research/'):
            if digest(ROOT/name)!=sha:raise ValueError('Original 5M binary or frozen manifest changed')
    old_suite=json.loads((ROOT/'research/ui_incremental_suite_5m_v3.json').read_bytes())
    suite=json.loads((ROOT/'research/ui_incremental_suite_10m_v1.json').read_bytes())
    for case in old_suite['cases']:
        candidate=next(c for c in suite['cases'] if c['id']==case['id'])
        for key in ['mods','checks','options']:
            if candidate.get(key)!=case.get(key):raise ValueError('Original program/options/expectation changed')
    oracle=json.loads((ROOT/'reports/ui-incremental-10m-oracle/oracle-result.json').read_bytes())
    boundary=json.loads((ROOT/'reports/ui-incremental-10m-boundaries/boundaries.json').read_bytes())
    real=json.loads((output/'experiment.json').read_bytes())
    if not oracle['passed'] or not boundary['passed'] or len(real['cases'])!=24:raise ValueError('Required checks incomplete')
    cap_invariance=[]
    for case in oracle['cases']:
        filename=case['id']+'-incremental.json'
        before=json.loads((ROOT/'reports/ui-incremental-factored-oracle'/filename).read_bytes())
        after=json.loads((ROOT/'reports/ui-incremental-10m-oracle'/filename).read_bytes())
        ordinary={k:before.get(k) for k in ['success','values','error','origins']}=={k:after.get(k) for k in ['success','values','error','origins']}
        graph=before.get('value_graph')==after.get('value_graph')
        cache=before['trace']['incremental']==after['trace']['incremental']
        cap_invariance.append({'id':case['id'],'ordinary_values_errors_origins_equal':ordinary,'full_producer_graph_equal':graph,'full_cache_evidence_equal':cache})
    archive=ROOT/'artifacts/isaac-authority-ui-incremental-0.1.4.zip'
    if digest(archive)!=snapshot['old_package_sha256']:raise ValueError('Historical package changed')
    result={'schema':'isaac-incremental-10m-verification-1','generated_files':len(names),'generated_differences':differences,'generated_difference_is_only_work_cap':True,'algorithm_files_unchanged':algorithm_files,'old_binary_and_manifest_unchanged':True,'original_programs_preserved':len(old_suite['cases']),'snapshot_files_verified':len(snapshot['files']),'old_package_sha256':digest(archive),'model_oracle_passed':oracle['passed'],'per_origin_checks':oracle['per_origin_checks'],'model_cap_invariance':cap_invariance,'model_cap_invariance_all_equal':all(all(c[k] for k in ['ordinary_values_errors_origins_equal','full_producer_graph_equal','full_cache_evidence_equal']) for c in cap_invariance),'structural_boundaries_passed':boundary['passed'],'real_cases':len(real['cases']),'real_initialization_gate_passed':real['real_initialization_gate_passed'],'functional_passed':len(real['functional_passed']),'functional_failed':real['functional_failed'],'safety_diagnostics_passed':real['safety_diagnostics_passed'],'refusal_diagnostics_repeated_identically':real['refusal_diagnostics_repeated_identically'],'real_report_sha256':digest(output/'experiment.json'),'runtime_sha256':real['runtime_sha256'],'game_process_used':False}
    write(output/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['model_cap_invariance','algorithm_files_unchanged']},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
