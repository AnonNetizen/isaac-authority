"""Repeat the UI initialization gate, preserving failures and original model suites."""
import argparse, json, struct, subprocess, sys
from pathlib import Path
from run_trace_research import ROOT, digest, write, verify_pristine, LUA_ARCHIVE_SHA
from validate import source_files, validate
from audit_baseline import audit

SUITE='slice3_ui_contract_suite_v7.json'
UI_BINS=('authority-slice3-ui-research.exe','ia_lua533_slice3_ui.dll','ia_lua533_reference.dll',
    'authority-trace-research.exe','ia_lua533_trace.dll','authority-tests.exe','authority-bridge-tests.exe',
    'authority-runtime-tests.exe','authority-resource-tests.exe','authority-suite-tests.exe',
    'isaac-authority.exe','isaac_authority_probe.dll')
HISTORY=(('runtime_suite.json','trace'),('trace_suite.json','trace'),('slice_suite.json','slice'),
    ('slice2_suite.json','slice2'),('slice3_suite_v3.json','slice3'))

def fingerprints(binary,root=ROOT):
    binaries={}
    for name in UI_BINS:
        p=binary/name;data=p.read_bytes();pe=struct.unpack_from('<I',data,60)[0]
        if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x14c:
            raise ValueError('Expected x86 PE: '+name)
        binaries[name]=digest(p)
    sources=set(source_files())
    sources.update(p for p in (root/'slice3_ui_runtime').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return binaries,{p.relative_to(root).as_posix():digest(p) for p in sorted(sources)}

def preserved(root=ROOT):
    entries=json.loads((root/'reports/slice3-ui-baseline.json').read_text())['files']
    for name,sha in entries.items():
        if digest(root/name)!=sha:raise ValueError('Previous Slice3 artifact changed: '+name)
    return entries

def verify_inputs(root,game=None):
    definition=json.loads((root/'research/slice3_ui_inputs.json').read_text())
    inputs=root/'research/slice3_ui_inputs';count=0
    for mod in definition['mods']:
        for base in (inputs,game) if game else (inputs,):
            actual={p.relative_to(base/mod['root']).as_posix():digest(p) for p in (base/mod['root']).rglob('*.lua')}
            if actual!=mod['sha256']:raise ValueError('Frozen mod changed: '+mod['root'])
        count+=len(mod['sha256'])
    for name,sha in definition['scripts'].items():
        if digest(inputs/name)!=sha or (game and digest(game/name)!=sha):raise ValueError('J460 script changed: '+name)
    resources=json.loads((root/'research/slice3_ui_resources.json').read_text())
    if resources['inputs_sha256']!=digest(root/'research/slice3_ui_inputs.json'):raise ValueError('Resource/source freeze mismatch')
    if game:
        for name,sha in resources['files_verified'].items():
            if digest(game/name)!=sha:raise ValueError('Local resource changed: '+name)
    return {'unmodified_mod_lua_files':count,'j460_script_files':len(definition['scripts']),
        'resource_entries':len(resources['resources']),'font_metric_files':sum('metrics' in x for x in resources['resources']),
        'local_resource_files_verified':len(resources['files_verified']) if game else 0,
        'resource_bytes_distributed':False,'frozen_metadata_used':True}

def run_ui(binary,root,output,reference=False):
    dll=binary/('ia_lua533_reference.dll' if reference else 'ia_lua533_slice3_ui.dll')
    cmd=[str(binary/'authority-slice3-ui-research.exe'),'--suite-reference' if reference else '--suite',
        str(dll),digest(dll),str(root/'research/slice3_ui_inputs'),str(root),str(root/'research'/SUITE)]
    with output.open('xb') as stream:
        p=subprocess.run(cmd,stdout=stream,stderr=subprocess.PIPE,timeout=180)
    if p.stderr:output.with_suffix('.stderr.txt').write_bytes(p.stderr)
    if p.returncode:raise RuntimeError('UI process failed: '+str(p.returncode)+' '+p.stderr.decode(errors='replace'))
    report=json.loads(output.read_text())
    for c in report['cases']:
        if not c['source_unchanged'] or not c['host_stack_restored']:raise ValueError('UI cleanup failed: '+c['id'])
    return report

def negative_entries(binary,previous,root,output):
    records=[];manifest=root/'research'/SUITE;inputs=root/'research/slice3_ui_inputs'
    tests=[('game-loader-refusal',binary/'authority-trace-research.exe','--suite',binary/'ia_lua533_slice3_ui.dll',
        'Slice3 UI requires its standalone runner; game integration refused'),
        ('previous-abi-refusal',binary/'authority-slice3-ui-research.exe','--suite',previous/'ia_lua533_slice3.dll','UI candidate ABI required'),
        ('instrumented-reference-refusal',binary/'authority-slice3-ui-research.exe','--suite-reference',binary/'ia_lua533_slice3_ui.dll','Reference must use unmodified Lua')]
    for name,exe,flag,dll,expected in tests:
        p=subprocess.run([str(exe),flag,str(dll),digest(dll),str(inputs),str(root),str(manifest)],capture_output=True,timeout=20)
        passed=p.returncode==1 and expected in p.stderr.decode(errors='replace')
        records.append({'id':name,'passed':passed,'returncode':p.returncode,'stderr':p.stderr.decode(errors='replace'),
            'runner_sha256':digest(exe),'runtime_sha256':digest(dll),'process_attach_attempted':False})
        if not passed:raise ValueError('Entry boundary failed: '+name)
    write(output/'entry-boundaries.json',records);return records

def run(binary,previous,game,output):
    output.mkdir(parents=True,exist_ok=False)
    before=fingerprints(binary);baseline=preserved();inputs=verify_inputs(ROOT,game);pristine=verify_pristine()
    save_baseline=ROOT.parent/'artifacts/authority-baseline-20261009'
    saves_before=audit(save_baseline);write(output/'save-audit-before.json',saves_before)
    reference=trace=None
    ui_reports={}
    for label,is_reference in (('reference',True),('candidate',False)):
        runs=[]
        for index in (1,2):
            print('UI '+label+' '+str(index),flush=True);target=output/(label+f'-{index}.json')
            runs.append(run_ui(binary,ROOT,target,is_reference))
        if runs[0]!=runs[1]:raise ValueError('UI repeated evidence differs: '+label)
        ui_reports[label]={'full_report_sha256':digest(output/(label+'-1.json')),'cases':len(runs[0]['cases'])}
        if is_reference:reference=runs[0]
        else:trace=runs[0]
    if not reference['initialization_contract_gate_passed'] or not reference['safety_diagnostics_passed']:
        raise ValueError('The unmodified Lua reference did not meet the frozen contract oracle')
    defs=json.loads((ROOT/'research'/SUITE).read_text());definitions={c['id']:c for c in defs['cases']}
    comparisons=[];unsupported=[];functional=[];safety=[]
    case_dir=output/'cases';case_dir.mkdir()
    for ref,actual in zip(reference['cases'],trace['cases'],strict=True):
        if ref['id']!=actual['id']:raise ValueError('Case order changed')
        write(case_dir/(actual['id']+'.json'),{'reference':ref,'candidate':actual})
        if actual['case_kind']=='safety':
            if not actual['diagnostic_passed']:raise ValueError('Safe refusal failed: '+actual['id'])
            safety.append(actual['id']);continue
        functional.append({'id':actual['id'],'compatibility_passed':actual['compatibility_passed'],
            'first_unsupported_entry':actual['first_unsupported_entry']})
        if actual['compatibility_passed']:
            if actual['observations']!=ref['observations']:raise ValueError('Ordinary Lua values changed: '+actual['id'])
            comparisons.append(actual['id'])
        elif actual['first_unsupported_entry']:unsupported.append(actual['first_unsupported_entry'])
    boundaries=negative_entries(binary,previous,ROOT,output)
    history={}
    for manifest,mode in HISTORY:
        dll=previous/('ia_lua533_'+mode+'.dll');targets=[]
        for index in (1,2):
            print('Historical '+manifest+' '+str(index),flush=True);target=output/(Path(manifest).stem+f'-{index}.json')
            with target.open('xb') as stream:
                p=subprocess.run([str(binary/'authority-trace-research.exe'),'--suite',str(dll),digest(dll),str(game),str(ROOT),str(ROOT/'research'/manifest)],stdout=stream,stderr=subprocess.PIPE,timeout=1200)
            if p.stderr:target.with_suffix('.stderr.txt').write_bytes(p.stderr)
            if p.returncode:raise ValueError('Original model suite process failed: '+manifest)
            report=json.loads(target.read_text())
            if not report['diagnostic_passed']:raise ValueError('Original model expected outcomes failed: '+manifest)
            historical=json.loads((ROOT/'reports/slice3-final-verified'/(Path(manifest).stem+'-1.json')).read_text())
            if report['cases']!=historical['cases']:raise ValueError('Historical case evidence changed: '+manifest)
            targets.append(target)
        if digest(targets[0])!=digest(targets[1]):raise ValueError('Historical repeat changed: '+manifest)
        history[manifest]={'cases':len(report['cases']),'mode':mode,'manifest_sha256':digest(ROOT/'research'/manifest),
            'runtime_sha256':digest(dll),'runner_sha256':digest(binary/'authority-trace-research.exe'),
            'full_report_sha256':digest(targets[0]),'repeated_identical':True,'original_case_evidence_identical':True}
    print('Shared-code baseline checks',flush=True)
    regression=validate(binary,game/'Lua5.3.3r.dll');write(output/'regression.json',regression)
    saves_after=audit(save_baseline);write(output/'save-audit-after.json',saves_after)
    def current(a):return [(r['file'],r['current_sha256']) for r in a['files']]
    if current(saves_after)!=current(saves_before):raise ValueError('Saved data changed during command-line validation')
    if fingerprints(binary)!=before or preserved()!=baseline or verify_inputs(ROOT,game)!=inputs:
        raise ValueError('Source/binary/installed input changed during validation')
    failed=[c['id'] for c in functional if not c['compatibility_passed']]
    result={'schema':'isaac-slice3-ui-research-1','research_version':'slice3-ui-0.1.0','private_abi':'ia-lua533-slice3-ui-1',
        'view_rule':'personal-settings-authority-hud-v1','suite':SUITE,'suite_sha256':digest(ROOT/'research'/SUITE),
        'binary_sha256':before[0],'source_sha256':before[1],'preserved_slice3_artifacts':baseline,'inputs':inputs,
        'lua_archive_sha256':LUA_ARCHIVE_SHA,'pristine_lua_files_verified':pristine,
        'original_source_root':str(ROOT),'original_game_root':str(game),'repeated_ui_reports':ui_reports,
        'unmodified_lua_contract_gate_passed':True,'ordinary_userdata_comparison_passed':comparisons,
        'functional_results':functional,'safe_refusal_cases':safety,'incompatible_functional_cases':failed,
        'first_unsupported_entries':list(dict.fromkeys(unsupported)),
        'initialization_contract_gate_passed':not failed,'conclusion':'candidate_failed_initialization_gate' if failed else 'candidate_passed_initialization_gate',
        'historical_suites':history,'historical_cases':sum(c['cases'] for c in history.values()),'entry_boundary_checks':len(boundaries),
        'baseline_regression_completed':True,'saved_data_files_audited':len(saves_before['files']),'saved_data_unchanged_during_validation':True,
        'game_binaries':{name:digest(game/name) for name in ('isaac-ng.exe','Lua5.3.3r.dll','Lua5.3.3f.dll')},
        'repeated_suites_identical':True,'game_process_used':False,'game_hooks_installed':False,'game_dll_replaced':False,
        'render_capture_passed':False,'trusted_real_menu_purpose_passed':False,'scripted_menu_navigation_passed':False,
        'full_ui_transaction_recovery_passed':False,'real_game_rendering_passed':False,'generic_mod_compatibility_passed':False,'playable':False,
        'limits':dict(defs['limits'],prototype_instructions=4096),
        'next_stages_status':'not entered: initialization gate failed' if failed else 'not implemented',
        'contract_scope':reference['contract_scope'],'safe_refusals_count_as_functional_compatibility':False}
    write(output/'validation.json',result)
    print(json.dumps({k:result[k] for k in ('conclusion','incompatible_functional_cases','first_unsupported_entries','historical_cases','saved_data_unchanged_during_validation')}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','previous','game','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*[getattr(a,n).resolve() for n in ('binary','previous','game','output')])
