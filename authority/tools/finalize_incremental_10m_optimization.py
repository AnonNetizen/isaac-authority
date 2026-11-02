"""Read-only preservation audit and final summary for the sequential 10M candidates."""
import json,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,write,preserved
from run_trace_research import verify_pristine
from run_slice3_ui_research import verify_inputs
from audit_baseline import audit

def run():
    reports=ROOT/'reports';verified={}
    for name in ['ui-incremental-10m-original-preserved','ui-incremental-index-preserved','ui-incremental-encoded-v1-preserved','ui-incremental-encoded-v2-preserved']:
        base=reports/name;files=json.loads((base/'files.json').read_bytes())
        for relative,sha in files.items():
            if digest(base/relative)!=sha:raise ValueError('Candidate snapshot changed: '+name+'/'+relative)
            if relative.startswith('build-') and digest(ROOT/relative)!=sha:raise ValueError('Historical binary changed: '+relative)
        verified[name]=len(files)
    candidates={}
    for name,folder in [('original','ui-incremental-10m-real-v2'),('index','ui-incremental-index-real'),('encoding-v1','ui-incremental-encoded-real'),('prefix-v2','ui-incremental-encoded-v2-real'),('final-v3','ui-incremental-encoded-v3-real')]:
        report=json.loads((reports/folder/'experiment.json').read_bytes());rows=[]
        for case in report['cases']:
            if case['id'] in report['functional_failed']:
                rows.append({'id':case['id'],'runs':[{'used':r['budget']['used'],'refusal':r['first_unsupported_entry'],'instructions':r['instructions'],'encoded':r.get('evidence_encoding'),'leading_costs':sorted(r['budget']['categories'].items(),key=lambda p:-p[1])[:6]} for r in case['runs']]})
        candidates[name]={'runtime_sha256':report['runtime_sha256'],'work_limit':report['work_limit'],'gate_passed':report['real_initialization_gate_passed'],'functional_passed':len(report['functional_passed']),'functional_failed':report['functional_failed'],'safety_diagnostics_passed':report['safety_diagnostics_passed'],'raw_refusal_stable':report['refusal_diagnostics_repeated_identically'],'timing_medians':report['timing_medians'],'actual_failures':rows,'report_sha256':digest(reports/folder/'experiment.json')}
    final=candidates['final-v3'];oracle=json.loads((reports/'ui-incremental-encoded-v3-oracle/oracle-result.json').read_bytes())
    proof=json.loads((reports/'ui-incremental-encoded-v3-proof.json').read_bytes());bounds=json.loads((reports/'ui-incremental-encoded-v3-boundaries/boundaries.json').read_bytes());unit=json.loads((reports/'ui-incremental-evidence-tests-v3.json').read_bytes())
    if not all([oracle['passed'],proof['passed'],bounds['passed'],unit['passed']]):raise ValueError('Component validation incomplete')
    binary=ROOT/'build-ui-incremental-encoded-v3-release/Release';binaries={}
    for name in ['ia_lua533_ui_incremental.dll','ia_lua533_reference.dll','authority-ui-incremental-research.exe','authority-trace-research.exe','authority-incremental-evidence-tests.exe','authority-incremental-boundary-tests.exe']:
        p=binary/name;data=p.read_bytes();pe=struct.unpack_from('<I',data,60)[0]
        if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x14c:raise ValueError('Expected x86 binary')
        binaries[name]=digest(p)
    if binaries['ia_lua533_ui_incremental.dll']!=final['runtime_sha256']:raise ValueError('Final report binary differs')
    old_package=digest(ROOT/'artifacts/isaac-authority-ui-incremental-0.1.4.zip')
    if old_package!='e95f24f0c97e2308b3bd25ff6dc77ae2b5465c02d7f3f7e77de5905cb885a1b0':raise ValueError('Historical package changed')
    save_before=json.loads((reports/'ui-incremental-10m-baseline/save-audit-before.json').read_bytes())
    save_after=audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    if [(c['file'],c['current_sha256']) for c in save_before['files']]!=[(c['file'],c['current_sha256']) for c in save_after['files']]:raise ValueError('Audited save/config originals changed')
    write(reports/'ui-incremental-10m-optimization-save-audit.json',save_after)
    result={'schema':'isaac-10m-incremental-optimization-final-1','work_limit':10000000,'view_rule':'personal-settings-authority-hud-v1','component_gate_passed':True,'real_initialization_gate_passed':final['gate_passed'],'oracle_cases':len(oracle['cases']),'per_origin_checks':oracle['per_origin_checks'],'all_expanded_consumers_and_producers_equal':proof['passed'],'model_producer_graph_and_encoded_evidence_repeat_stable':oracle['complete_value_graph_and_cache_evidence_repeated_identically'],'storage_capacity_tests':len(unit['cases']),'structural_tests':len(bounds['cases']),'snapshots_verified':verified,'historical_files_verified':preserved(),'pristine_lua':verify_pristine(),'frozen_inputs':verify_inputs(ROOT,Path(r'E:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth')),'audited_save_config_files_unchanged':31,'old_package_sha256':old_package,'binaries':binaries,'sources':{p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'incremental_ui_runtime').iterdir() if p.is_file()},'candidates':candidates,'capacity_policy':{'descriptors':65536,'sites':65536,'encoded_bytes':67108864,'logical_use_count_bounded_by_charged_10m_work':True,'original_65536_logical_use_cap_preserved':False},'game_started':False,'real_hud_or_menu_navigation_started':False,'new_overall_package_created':False,'next_step':'Immutable per-object field version snapshots and exact deltas, including proven shared increments; full expansion/origin oracle first; then liveness reuse. Keep work and encoded storage limits.'}
    result['audited_save_config_files_unchanged']=len(save_after['files'])
    result['save_config_audit_sha256']=digest(reports/'ui-incremental-10m-optimization-save-audit.json')
    write(reports/'ui-incremental-10m-optimization-final.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['candidates','sources','binaries']},ensure_ascii=False))

if __name__=='__main__':run()
