"""Freeze evidence only after tests and unchanged historical suites repeat."""
import argparse,json,os,re,struct,subprocess,sys,time
from pathlib import Path
from run_slice2_research import BINS as PREVIOUS_BINS
from run_trace_research import ROOT,digest,verify_pristine,write,LUA_ARCHIVE_SHA
from validate import source_files,validate
from run_slice3_suite import run as suite_run
BINS=PREVIOUS_BINS+('authority-slice3-research.exe','ia_lua533_slice3.dll')

def fingerprints(binary):
    hashes={}
    for name in BINS:
        p=binary/name;data=p.read_bytes();offset=struct.unpack_from('<I',data,0x3c)[0]
        if data[offset:offset+4]!=b'PE\0\0' or struct.unpack_from('<H',data,offset+4)[0]!=0x14c:raise ValueError('Expected x86 PE: '+name)
        hashes[name]=digest(p)
    return hashes,{p.relative_to(ROOT).as_posix():digest(p) for p in source_files()}

def preserved():
    baseline=json.loads((ROOT/'reports/slice3-baseline.json').read_text())['files']
    for name,expected in baseline.items():
        if digest(ROOT/name)!=expected:raise ValueError('Preserved candidate changed: '+name)
    return baseline

def run(binary,game,output,lua):
    output.mkdir(parents=True,exist_ok=False);before=fingerprints(binary);history=preserved();pristine=verify_pristine()
    env=dict(os.environ,IA_TRACE_BINARY_DIR=str(binary),IA_TRACE_GAME_DIR=str(game));tests={}
    for name in ('test_slice3_runtime.py','test_slice3_suite.py','test_slice2_runtime.py','test_slice2_suite.py','test_slice_runtime.py','test_slice_suite.py','test_trace_runtime.py','test_trace_suite.py'):
        print('Testing '+name,flush=True);start=time.perf_counter()
        p=subprocess.run([sys.executable,str(ROOT/'tests'/name)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=600)
        (output/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode:raise RuntimeError('Test failed: '+name)
        count=re.search(r'Ran (\d+) tests',p.stderr);tests[name]={'passed':int(count.group(1)),'elapsed_seconds':round(time.perf_counter()-start,6)}
    matrix=[('runtime_suite.json','trace'),('trace_suite.json','trace'),('slice_suite.json','slice'),('slice2_suite.json','slice2'),('slice3_suite_v3.json','slice3')]
    suites={}
    for manifest,mode in matrix:
        reports=[]
        for n in (1,2):
            print('Repeating '+manifest+' '+str(n),flush=True)
            target=output/(Path(manifest).stem+f'-{n}.json')
            s=suite_run(binary,game,ROOT,ROOT/'research'/manifest,target,mode)
            if not s['diagnostic_passed']:raise RuntimeError('Diagnostic failed: '+manifest)
            reports.append(target)
        if digest(reports[0])!=digest(reports[1]):raise RuntimeError('Repeated full report changed: '+manifest)
        suites[manifest]={'cases':len(json.loads(reports[0].read_text())['cases']),'full_report_sha256':digest(reports[0]),'manifest_sha256':digest(ROOT/'research'/manifest)}
    print('Baseline regression',flush=True);regression=validate(binary,lua);write(output/'regression.json',regression)
    report=json.loads((output/'slice3_suite_v3-1.json').read_text());definitions={c['id']:c for c in json.loads((ROOT/'research/slice3_suite_v3.json').read_text())['cases']}
    cases=output/'cases';cases.mkdir();groups={'functional':[],'safety':[],'transaction':[]}
    for c in report['cases']:
        write(cases/(c['id']+'.json'),c);kind=definitions[c['id']].get('case_kind','functional')
        groups[kind].append({'id':c['id'],'diagnostic_passed':c['passed'],'compatibility_passed':c['compatibility_passed'],'first_unsupported_entry':c['first_unsupported_entry']})
    if fingerprints(binary)!=before or preserved()!=history:raise RuntimeError('Source or binary changed during validation')
    failed=[c['id'] for c in groups['functional'] if not c['compatibility_passed']]
    result={'schema':'isaac-execution-slice3-research-1','research_version':'slice3-0.1.0','private_abi':'ia-lua533-slice-3','view_rule':'personal-settings-authority-hud-v1',
        'standalone_only':True,'original_source_root':str(ROOT),'original_game_root':str(game),'game_process_used':False,'game_hooks_installed':False,'game_dll_replaced':False,'native_world_committed':False,'playable':False,'generic_mod_compatibility_passed':False,
        'lua_archive_sha256':LUA_ARCHIVE_SHA,'pristine_lua_files_verified':pristine,'binary_sha256':before[0],'source_sha256':before[1],'immutable_baseline':history,
        'tests':tests,'suites':suites,'repeated_suites_identical':True,'baseline_regression_completed':True,'functional_gate_passed':not failed,'incompatible_functional_cases':failed,
        'functional_results':groups['functional'],'safe_refusal_results':groups['safety'],'transaction_results':groups['transaction'],
        'conclusion':'candidate_failed_model_gate' if failed else 'candidate_gate_passed_for_model',
        'exploration_limits':{'paths':32,'unresolved_branches':8,'instructions':2000000},'real_mcm_eid_tested':False}
    write(output/'validation.json',result)
    print(json.dumps({'conclusion':result['conclusion'],'functional':len(groups['functional']),'safety':len(groups['safety']),'transactions':len(groups['transaction']),'tests':tests}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','game','output','lua'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*[getattr(a,n).resolve() for n in ('binary','game','output','lua')])
