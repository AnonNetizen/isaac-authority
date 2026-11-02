"""Run the frozen 10M cap experiment one case per process to bound host RAM."""
import argparse, copy, gc, json, statistics, sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT, digest, write, invoke, preserved, cache_witnesses, outcomes, real_manifest
from measure_incremental_budget import measure
from audit_baseline import audit
from run_slice3_ui_research import verify_inputs

LIMIT=10000000
REAL_IDS={'mcm-en','mcm-zh','eid-en','eid-zh','combined-en','combined-zh'}

def summarize(report):
    c=report['cases'][0];result=outcomes(report)[0]
    result['first_unsupported_entry']=c['first_unsupported_entry']
    result['raw_report_identity']={'runtime_sha256':report['runtime_sha256'],'suite_sha256':report['suite_sha256']}
    if 'execution_dependencies' in c:
        runtime=c['execution_dependencies']['runtime'];budget=runtime['bounded_work'];inc=runtime['incremental']
        if budget['limit']!=LIMIT or budget['used']>LIMIT or budget['used']!=sum(budget['categories'].values()):raise ValueError('Wrong work cap or uncharged work')
        result['budget']=budget
        result['instructions']=runtime.get('instructions')
        result['cache_witness_checks']=cache_witnesses(runtime)
        result['cache_counters']={key:inc.get(key) for key in ['mark_cache_hits','aggregate_cache_hits','scalar_leaf_mark_cache_hits','site_cache_hits','invalidations','object_count']}
        if 'evidence_encoding' in inc:result['evidence_encoding']=inc['evidence_encoding']
    return result

def run(binary,output,prior_oracle,oracle_manifest=None):
    dll=binary/'ia_lua533_ui_incremental.dll';suite=real_manifest(LIMIT)
    oracle_manifest=oracle_manifest or ROOT/'research/ui_incremental_oracle_10m_v1.json'
    proof=json.loads(prior_oracle.read_bytes())
    if not proof['passed'] or not proof['complete_value_graph_and_cache_evidence_repeated_identically'] or proof['work_limit']!=LIMIT or proof['runtime_sha256']!=digest(dll) or proof['suite_sha256']!=digest(oracle_manifest):raise ValueError('Exact 10M model gate required')
    output.mkdir(parents=True,exist_ok=False)
    baseline=ROOT/'reports/ui-incremental-10m-baseline';snap=json.loads((baseline/'snapshot.json').read_bytes())
    for name,sha in snap['files'].items():
        if digest(baseline/'files'/name)!=sha:raise ValueError('Preserved snapshot changed')
    frozen=verify_inputs(ROOT,Path(r'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth'))
    spec=json.loads(suite.read_bytes());rows=[];times=[]
    for case in spec['cases']:
        print('10M case '+case['id'],flush=True)
        subset=copy.deepcopy(spec);subset['cases']=[case]
        subset['parent_manifest_sha256']=digest(suite)
        subset['execution_note']='One exact frozen case per independent process; same limits/backend/options/code/checks, fresh host/context'
        manifest=output/(case['id']+'-suite.json');write(manifest,subset)
        reference=[];candidate=[];hashes=[]
        for repeat in [1,2]:
            path=output/f'{case["id"]}-reference-{repeat}.json'
            report=invoke([binary/'authority-ui-incremental-research.exe','--suite-reference',binary/'ia_lua533_reference.dll',digest(binary/'ia_lua533_reference.dll'),ROOT/'research/slice3_ui_inputs',ROOT,manifest],path)
            reference.append(summarize(report));del report;gc.collect()
        if reference[0]!=reference[1]:raise ValueError('Reference functional results changed')
        for repeat in [1,2]:
            if case['id'] in REAL_IDS:
                row=measure(binary,LIMIT,case['id'],repeat,output,inspect=summarize)
                candidate.append(row.pop('case_summary'));times.append(row)
                path=output/f'{LIMIT}-{case["id"]}-{repeat}.json'
            else:
                path=output/f'{case["id"]}-candidate-{repeat}.json'
                report=invoke([binary/'authority-ui-incremental-research.exe','--suite',dll,digest(dll),ROOT/'research/slice3_ui_inputs',ROOT,manifest],path)
                candidate.append(summarize(report));del report
            hashes.append(digest(path));gc.collect()
        functional_keys=['id','case_kind','initialization_passed','contract_passed','compatibility_passed','diagnostic_passed','observations','world','source_unchanged','host_stack_restored']
        functional_equal={k:candidate[0].get(k) for k in functional_keys}=={k:candidate[1].get(k) for k in functional_keys}
        refusal_equal={k:candidate[0].get(k) for k in ['first_unsupported_entry','post_refusal_execution_blocked']}=={k:candidate[1].get(k) for k in ['first_unsupported_entry','post_refusal_execution_blocked']}
        for actual in candidate:
            if actual['compatibility_passed'] and (actual['observations']!=reference[0]['observations'] or actual['world']!=reference[0]['world']):raise ValueError('Functional result differs from unmodified Lua')
            if not actual['source_unchanged'] or not actual['host_stack_restored']:raise ValueError('Source or host stack changed')
            if actual['first_unsupported_entry'] and 'Bounded UI work budget exceeded' in actual['first_unsupported_entry'] and not actual['post_refusal_execution_blocked']:raise ValueError('Budget fault can be resumed')
            if case.get('case_kind','functional')=='safety' and not actual['diagnostic_passed']:raise ValueError('Required safety refusal failed')
        row={'id':case['id'],'case_kind':case.get('case_kind','functional'),'reference':reference[0],'runs':candidate,'raw_report_sha256':hashes,'functional_outcomes_repeat_equal':functional_equal,'refusal_diagnostics_repeat_equal':refusal_equal,'complete_raw_reports_repeat_equal':hashes[0]==hashes[1]}
        rows.append(row);write(output/'progress.json',{'completed':len(rows),'total':len(spec['cases']),'cases':rows,'timing_samples':times})
        print(json.dumps({'id':case['id'],'compatibility_passed':candidate[0]['compatibility_passed'],'diagnostic_passed':candidate[0]['diagnostic_passed'],'work_used':[c['budget']['used'] for c in candidate],'failure':candidate[0]['first_unsupported_entry']},ensure_ascii=False),flush=True)

    save_after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-audit-after.json',save_after)
    before=json.loads((baseline/'save-audit-before.json').read_bytes())
    if [(c['file'],c['current_sha256']) for c in before['files']]!=[(c['file'],c['current_sha256']) for c in save_after['files']]:raise ValueError('Audited save/config originals changed')
    historical_unchanged=preserved()
    for name,sha in snap['files'].items():
        if name.startswith('build-ui-incremental-factored-release/') or name.startswith('research/'):
            if digest(ROOT/name)!=sha:raise ValueError('Original binary or manifest changed')
    frozen_after=verify_inputs(ROOT,Path(r'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth'))
    medians={}
    for case_id in sorted(REAL_IDS):
        samples=[c for c in times if c['case']==case_id]
        medians[case_id]={key:statistics.median(c[key] for c in samples) for key in ['seconds_traced_initialization_to_outcome','outcome_working_set_mib','peak_process_working_set_mib']}
    result={'schema':'isaac-incremental-10m-cap-experiment-1','work_limit':LIMIT,'runtime_sha256':digest(dll),'manifest_sha256':digest(suite),'oracle_report_sha256':digest(prior_oracle),'cases':rows,'functional_passed':[c['id'] for c in rows if all(r['compatibility_passed'] for r in c['runs']) and c['functional_outcomes_repeat_equal']],'functional_failed':[c['id'] for c in rows if c['case_kind']=='functional' and (not all(r['compatibility_passed'] for r in c['runs']) or not c['functional_outcomes_repeat_equal'])],'safety_diagnostics_passed':all(r['diagnostic_passed'] for c in rows if c['case_kind']=='safety' for r in c['runs']),'functional_outputs_repeated_identically':all(c['functional_outcomes_repeat_equal'] for c in rows),'refusal_diagnostics_repeated_identically':all(c['refusal_diagnostics_repeat_equal'] for c in rows),'timing_samples':times,'timing_medians':medians,'timing_scope':'after untraced bootstrap until initialization completes or refuses, excludes report serialization; two samples, not game frame cost','memory_scope':'host process working set at outcome, peak includes harness/resources/evidence/report','unchanged_historical_files':historical_unchanged,'save_config_baseline_files_unchanged':len(save_after['files']),'frozen_inputs_before':frozen,'frozen_inputs_after':frozen_after,'tracking_algorithm_changed':False,'other_limits_changed':False,'game_process_used':False,'draw_capture_navigation_started':False,'source_modification_required':False,'view_rule':'personal-settings-authority-hud-v1'}
    result['real_initialization_gate_passed']=all(c['functional_outcomes_repeat_equal'] and all(r['compatibility_passed'] for r in c['runs']) for c in rows if c['id'] in REAL_IDS)
    original=ROOT/'build-ui-incremental-10m-release/Release/ia_lua533_ui_incremental.dll'
    result['tracking_algorithm_changed']=digest(dll)!=digest(original)
    result['other_limits_changed']=any('evidence_encoding' in r for c in rows for r in c['runs'])
    if result['other_limits_changed']:result['evidence_capacity_note']='65,536 descriptors plus 64 MiB encoded payload/use bytes; every logical use remains charged under 10M. Original 65,536 logical-use cap retained only in historical runtime.'
    result['oracle_manifest_sha256']=digest(oracle_manifest)
    write(output/'experiment.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','timing_samples']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--prior-oracle',type=Path,required=True);p.add_argument('--oracle-manifest',type=Path);a=p.parse_args();run(a.binary.resolve(),a.output.resolve(),a.prior_oracle.resolve(),a.oracle_manifest.resolve() if a.oracle_manifest else None)
