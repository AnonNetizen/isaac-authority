"""Repeat bounded tracking gates, ordinary Lua comparison, and preserved model regressions."""
import argparse, gc, hashlib, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_slice3_ui_research import verify_inputs, preserved, HISTORY
from run_trace_research import verify_pristine
from audit_baseline import audit
from validate import validate
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def invoke(cmd,target,timeout=300):
    with target.open('xb') as out,target.with_suffix('.stderr.txt').open('xb') as err:
        p=subprocess.run([str(x) for x in cmd],stdout=out,stderr=err,timeout=timeout)
    if p.returncode:raise RuntimeError(f'Process failed {p.returncode}: {target}')
    return json.loads(target.read_bytes())
def sources():
    result={}
    for name in ['native','bounded_ui_runtime','slice3_ui_runtime','tools','docs']:
        for p in (ROOT/name).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:result[p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ['CMakeLists.txt','research/ui_bounded_suite_v4.json']:result[name]=digest(ROOT/name)
    return result
def old_files():
    result=preserved().copy()
    for name in ['slice3_ui_runtime','build-slice3-ui-release/Release']:
        for p in (ROOT/name).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:result[p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ['research/slice3_ui_contract_suite_v7.json','reports/slice3-ui-delivery.json','artifacts/isaac-authority-slice3-ui-0.1.0.zip']:result[name]=digest(ROOT/name)
    return result
def outcome(r):
    return [{k:c.get(k) for k in ('id','case_kind','initialization_passed','contract_passed','compatibility_passed','diagnostic_passed','observations','world','source_unchanged','host_stack_restored','post_refusal_execution_blocked')} for c in r['cases']]
def run(binary,game,output,history,history_evidence=None):
    output.mkdir(exist_ok=False,parents=True)
    before={'sources':sources(),'binaries':{p.name:digest(p) for p in binary.iterdir() if p.suffix in ('.exe','.dll')},'preserved':old_files(),'inputs':verify_inputs(ROOT,game),'lua':verify_pristine(),'audit':audit(ROOT.parent/'artifacts/authority-baseline-20261009')}
    write(output/'before.json',before)
    structural=invoke([binary/'authority-bounded-cfg-tests.exe'],output/'cfg-tests.json')
    if not structural['passed']:raise ValueError('CFG differential failed')
    suite=ROOT/'research/ui_bounded_suite_v4.json';defs=json.loads(suite.read_text())
    runs={};full_equal={};contracts={};costs=[]
    for label,reference in [('reference',True),('candidate',False)]:
        dll=binary/('ia_lua533_reference.dll' if reference else 'ia_lua533_ui_bounded.dll')
        first=None
        for number in (1,2):
            print(f'{label} {number}',flush=True)
            report=invoke([binary/'authority-ui-bounded-research.exe','--suite-reference' if reference else '--suite',dll,digest(dll),ROOT/'research/slice3_ui_inputs',ROOT,suite],output/f'{label}-{number}.json')
            if any(not c['source_unchanged'] or not c['host_stack_restored'] for c in report['cases']):raise ValueError('Cleanup boundary failed')
            if number==1:first=outcome(report)
            elif outcome(report)!=first:raise ValueError('Repeated functional outcomes differ')
            if not reference:
                if not report['safety_diagnostics_passed']:raise ValueError('Refusal safety failed')
                for c in report['cases']:
                    w=c['execution_dependencies']['runtime']['bounded_work']
                    if w['used']>2000000 or sum(w['categories'].values())!=w['used']:raise ValueError('Ledger escaped budget')
                    if w['failure'] and not c.get('post_refusal_execution_blocked'):raise ValueError('Terminal refusal resumed')
                    if number==1:costs.append({'id':c['id'],'used':w['used'],'categories':w['categories'],'first_unsupported_entry':c['first_unsupported_entry'],'post_refusal_execution_blocked':c.get('post_refusal_execution_blocked'),'cfg':w['codes']})
            del report;gc.collect()
        runs[label]=first
        full_equal[label]=digest(output/f'{label}-1.json')==digest(output/f'{label}-2.json')
    for ref,candidate,definition in zip(runs['reference'],runs['candidate'],defs['cases'],strict=True):
        if definition.get('case_kind','functional')=='functional':
            if not ref['compatibility_passed']:raise ValueError('Reference ordinary Lua contract failed: '+ref['id'])
            if candidate['compatibility_passed'] and candidate['observations']!=ref['observations']:raise ValueError('Candidate changed ordinary result')
    boundaries=[]
    for name,exe,flag,dll,expected in [
        ('game-refusal','authority-trace-research.exe','--suite',binary/'ia_lua533_ui_bounded.dll','Bounded UI requires its standalone runner; game integration refused'),
        ('old-ui-abi-refusal','authority-ui-bounded-research.exe','--suite',ROOT/'build-slice3-ui-release/Release/ia_lua533_slice3_ui.dll','UI candidate ABI required'),
        ('instrumented-reference-refusal','authority-ui-bounded-research.exe','--suite-reference',binary/'ia_lua533_ui_bounded.dll','Reference must use unmodified Lua')]:
        p=subprocess.run([str(binary/exe),flag,str(dll),digest(dll),str(ROOT/'research/slice3_ui_inputs'),str(ROOT),str(suite)],capture_output=True,timeout=20)
        passed=p.returncode==1 and expected in p.stderr.decode(errors='replace')
        if not passed:raise ValueError('Entry boundary failed: '+name+' '+p.stderr.decode(errors='replace'))
        boundaries.append({'id':name,'passed':passed,'stderr':p.stderr.decode(errors='replace')})
    original={}
    if history_evidence:
        earlier=json.loads(history_evidence.read_text())
        if digest(binary/'authority-trace-research.exe')!=earlier['binaries']['authority-trace-research.exe']:raise ValueError('Historical runner changed')
        original=earlier['original_suites']
        if sum(c['cases'] for c in original.values())!=166:raise ValueError('Historical evidence incomplete')
        for manifest,mode in HISTORY:
            if digest(ROOT/'build-slice3-release/Release'/('ia_lua533_'+mode+'.dll'))!=original[manifest]['runtime_sha256']:raise ValueError('Historical runtime changed')
    if history:
        for manifest,mode in HISTORY:
            print('Preserved '+manifest,flush=True);dll=ROOT/'build-slice3-release/Release'/('ia_lua533_'+mode+'.dll')
            r=invoke([binary/'authority-trace-research.exe','--suite',dll,digest(dll),game,ROOT,ROOT/'research'/manifest],output/(Path(manifest).stem+'.json'),1200)
            prior=json.loads((ROOT/'reports/slice3-final-verified'/(Path(manifest).stem+'-1.json')).read_bytes())
            if not r['diagnostic_passed'] or r['cases']!=prior['cases']:raise ValueError('Preserved case evidence changed: '+manifest)
            original[manifest]={'cases':len(r['cases']),'case_evidence_identical':True,'runtime_sha256':digest(dll)}
            del r,prior;gc.collect()
    print('Shared baseline checks',flush=True)
    regression=validate(binary,game/'Lua5.3.3r.dll');write(output/'regression.json',regression)
    after={'sources':sources(),'binaries':{p.name:digest(p) for p in binary.iterdir() if p.suffix in ('.exe','.dll')},'preserved':old_files(),'inputs':verify_inputs(ROOT,game),'audit':audit(ROOT.parent/'artifacts/authority-baseline-20261009')}
    write(output/'after.json',after)
    for key in ('sources','binaries','preserved','inputs'):
        if before[key]!=after[key]:raise ValueError('Inputs changed during test: '+key)
    def save(a):return [(c['file'],c['current_sha256']) for c in a['files']]
    if save(before['audit'])!=save(after['audit']):raise ValueError('Personal saved data changed')
    passed=[c['id'] for c in runs['candidate'] if c['compatibility_passed']]
    failed=[c['id'] for c in runs['candidate'] if c['case_kind']=='functional' and not c['compatibility_passed']]
    result={'schema':'isaac-bounded-ui-validation-1','abi':'ia-lua533-slice3-ui-bounded-1','suite_sha256':digest(suite),'binaries':before['binaries'],'structural_tests':structural,'cases':len(defs['cases']),'functional_passed':passed,'functional_failed':failed,'safe_refusal_cases':sum(c['case_kind']=='safety' for c in runs['candidate']),'functional_outcomes_repeat_identically':True,'full_evidence_repeat_identically':full_equal,'ordinary_results_match_reference':True,'initialization_contract_gate_passed':not failed,'entry_boundaries':boundaries,'costs':costs,'original_suites':original,'personal_files_unchanged':len(before['audit']['files']),'installed_inputs_unchanged':True,'historical_artifacts_unchanged':True,'game_process_used':False,'draw_capture_or_menu_navigation_implemented':False,'transaction_recovery_tested':False,'budget_scope':'strict 2000000 per private context lifetime; error-only cleanup untracked after terminal refusal; future execution prohibited'}
    write(output/'validation.json',result);print(json.dumps({k:result[k] for k in ('functional_passed','functional_failed','full_evidence_repeat_identically','initialization_contract_gate_passed')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--history',action='store_true');p.add_argument('--history-evidence',type=Path);a=p.parse_args();run(a.binary.resolve(),a.game.resolve(),a.output.resolve(),a.history,a.history_evidence)
