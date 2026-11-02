"""Preserve the 5M candidate and freeze the explicitly authorized 10M profile."""
import copy, json, shutil, sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT, digest, write, preserved
from audit_baseline import audit
from run_slice3_ui_research import verify_inputs

def run():
    output=ROOT/'reports/ui-incremental-10m-baseline'
    output.mkdir(parents=True,exist_ok=False)
    selected=[]
    for folder in ['incremental_ui_runtime','build-ui-incremental-factored-release/Release']:
        selected.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    selected.extend(ROOT/name for name in ['tools/build.ps1','tools/run_incremental_ui.py','tools/run_incremental_boundaries.py','tools/measure_incremental_budget.py','research/ui_incremental_suite_5m_v3.json','research/ui_incremental_oracle_v5.json','research/ui_incremental_boundaries_v2.json','reports/ui-incremental-optimization-final.json'])
    files={}
    for source in sorted(selected):
        relative=source.relative_to(ROOT).as_posix();target=output/'files'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if digest(source)!=digest(target):raise ValueError('Snapshot copy mismatch')
        files[relative]=digest(source)
    old_package=ROOT/'artifacts/isaac-authority-ui-incremental-0.1.4.zip'
    if digest(old_package)!='e95f24f0c97e2308b3bd25ff6dc77ae2b5465c02d7f3f7e77de5905cb885a1b0':raise ValueError('Historical 0.1.4 package changed')
    write(output/'snapshot.json',{'files':files,'old_package_sha256':digest(old_package),'historical_files_preserved':preserved(),'old_work_limit':5000000,'new_work_limit':10000000})
    write(output/'save-audit-before.json',audit(ROOT.parent/'artifacts/authority-baseline-20261009'))
    write(output/'frozen-inputs.json',verify_inputs(ROOT,Path(r'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth')))

    previous=ROOT/'research/ui_incremental_suite_5m_v3.json'
    suite=json.loads(previous.read_bytes())
    suite['limits']['exploration_work']=10000000
    suite['purpose']='Explicitly authorized 10M cap experiment; identical tracking algorithm and frozen MCM/EID source/resources; all other limits unchanged'
    suite['previous_manifest_sha256']=digest(previous)
    suite['authorized_work_limit_change']={'from':5000000,'to':10000000,'reason':'User requested: 改成1000万上限试试会不会超','expectation_changes':'Original two 5M parser diagnostics become functional at 10M with their original code and reference return values. Two independent 10M terminal-refusal tests added. No mod source or view rule changed.'}
    for case in suite['cases']:
        if case['id'] in ['parser-5m-cap-refusal','caught-5m-budget-cannot-resume']:
            case['case_kind']='functional';del case['expected_unsupported']
    for original_id,new_id in [('parser-5m-cap-refusal','parser-10m-cap-refusal'),('caught-5m-budget-cannot-resume','caught-10m-budget-cannot-resume')]:
        case=copy.deepcopy(next(c for c in suite['cases'] if c['id']==original_id))
        case['id']=new_id;case['case_kind']='safety'
        case['expected_unsupported']='Bounded UI work budget exceeded: parser_token'
        case['checks'][0]['id']=new_id
        case['checks'][0]['code']=case['checks'][0]['code'].replace('load(text);load(text)','load(text);load(text);load(text);load(text)')
        suite['cases'].append(case)
    new_real=ROOT/'research/ui_incremental_suite_10m_v1.json';write(new_real,suite)
    for name in ['oracle','boundaries']:
        source=ROOT/('research/ui_incremental_oracle_v5.json' if name=='oracle' else 'research/ui_incremental_boundaries_v2.json')
        candidate=json.loads(source.read_bytes());candidate['work_limit']=10000000
        candidate['previous_sha256']=digest(source)
        candidate['budget_profile_note']='Only the authorized work cap changes from 5M to 10M; all original programs, expectations and structural limits are unchanged.'
        write(ROOT/f'research/ui_incremental_{name}_10m_v1.json',candidate)
    result={'snapshot_files':len(files),'suite_cases':len(suite['cases']),'real_suite_sha256':digest(new_real),'old_package_preserved':True,'game_process_used':False}
    write(output/'preparation.json',result);print(json.dumps(result))

if __name__=='__main__':run()
