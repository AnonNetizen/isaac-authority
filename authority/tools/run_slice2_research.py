"""Repeat slice2 functionality, refusals and unchanged 13/31/24 suites without a game."""
import argparse,json,os,re,struct,subprocess,sys,time
from pathlib import Path
from run_slice_research import ROOT,SLICE_BINS
from run_trace_research import digest,verify_pristine,write
from validate import source_files,validate
BINS=SLICE_BINS+('authority-slice2-research.exe','ia_lua533_slice2.dll')

def fingerprints(binary):
    hashes={}
    for name in BINS:
        path=binary/name;data=path.read_bytes();offset=struct.unpack_from('<I',data,0x3c)[0]
        if data[offset:offset+4]!=b'PE\0\0' or struct.unpack_from('<H',data,offset+4)[0]!=0x14c:raise ValueError('Expected x86 PE: '+name)
        hashes[name]=digest(path)
    return hashes,{p.relative_to(ROOT).as_posix():digest(p) for p in source_files()}

def baseline():
    records=json.loads((ROOT/'reports/slice2-baseline.json').read_text())['immutable_baseline']
    for name,sha in records.items():
        if digest(ROOT/name)!=sha:raise ValueError('Immutable historical artifact changed: '+name)
    return records

def run(binary,game,output,regression_lua=None):
    output.mkdir(parents=True,exist_ok=False);hashes,sources=fingerprints(binary);pristine=verify_pristine();previous=baseline()
    env=dict(os.environ,IA_TRACE_BINARY_DIR=str(binary),IA_TRACE_GAME_DIR=str(game));checks={}
    for name in ('test_slice2_runtime.py','test_slice2_suite.py','test_slice_runtime.py','test_slice_suite.py','test_trace_runtime.py','test_trace_suite.py'):
        start=time.perf_counter();p=subprocess.run([sys.executable,str(ROOT/'tests'/name)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=300)
        (output/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode:raise RuntimeError(name+' failed; see '+str(output/(name+'.log')))
        count=re.search(r'Ran (\d+) tests',p.stderr)
        if not count:raise RuntimeError('Missing test summary: '+name)
        checks[name]={'passed':int(count.group(1)),'elapsed_seconds':round(time.perf_counter()-start,6)}
    suites={}
    for manifest,dll,runner in [('runtime_suite.json','ia_lua533_trace.dll','authority-trace-research.exe'),('trace_suite.json','ia_lua533_trace.dll','authority-trace-research.exe'),('slice_suite.json','ia_lua533_slice.dll','authority-slice-research.exe'),('slice2_suite.json','ia_lua533_slice2.dll','authority-slice2-research.exe')]:
        repeated=[]
        for index in range(2):
            p=subprocess.run([str(binary/runner),'--suite',str(binary/dll),hashes[dll],str(game),str(ROOT),str(ROOT/'research'/manifest)],capture_output=True,text=True,encoding='utf-8',timeout=300)
            report=json.loads(p.stdout);write(output/(manifest.replace('.json','')+f'-{index+1}.json'),report)
            if p.returncode or not report['diagnostic_passed']:raise RuntimeError('Diagnostic failed: '+manifest+' '+p.stderr)
            repeated.append(report)
        if repeated[0]!=repeated[1]:raise RuntimeError('Repeated full report differs: '+manifest)
        suites[manifest]=repeated[0]
    cases=output/'cases';cases.mkdir()
    for case in suites['slice2_suite.json']['cases']:write(cases/(case['id']+'.json'),case)
    regression=None
    if regression_lua:regression=validate(binary,regression_lua);write(output/'regression.json',regression)
    if fingerprints(binary)!=(hashes,sources) or baseline()!=previous:raise RuntimeError('Sources or binaries changed during verification')
    definitions={c['id']:c for c in json.loads((ROOT/'research/slice2_suite.json').read_text())['cases']}
    functional=[];refusals=[];transactions=[]
    for c in suites['slice2_suite.json']['cases']:
        d=definitions[c['id']];kind=d.get('case_kind','functional')
        rejections=sum(f['outcome']=='reject' for f in c['frames'])
        item={'id':c['id'],'diagnostic_passed':c['passed'],'accepted_frames':len(c['frames'])-rejections,'rejected_frames':rejections,'compatibility_passed':c['compatibility_passed'],'first_unsupported_entry':c['first_unsupported_entry']}
        if kind=='safety':refusals.append(item)
        elif kind=='transaction':transactions.append(item)
        else:functional.append(item)
    failed=[c['id'] for c in functional if not c['compatibility_passed']]
    result={'schema':'isaac-execution-slice2-research-1','research_version':'slice2-0.1.0','private_abi':'ia-lua533-slice-2','standalone_only':True,'game_process_used':False,'game_hooks_installed':False,'game_dll_replaced':False,'native_world_committed':False,'playable':False,'generic_mod_compatibility_passed':False,'lua_archive_sha256':'5113c06884f7de453ce57702abaac1d618307f33f6789fa870e87a59d772aca2','pristine_lua_files_verified':pristine,'binary_sha256':hashes,'source_sha256':sources,'immutable_baseline':previous,'tests':checks,'manifest_sha256':{name:digest(ROOT/'research'/name) for name in suites},'repeated_suites_identical':True,'baseline_regression_completed':regression is not None,'functional_gate_passed':not failed,'incompatible_functional_cases':failed,'functional_results':functional,'safe_refusal_results':refusals,'transaction_results':transactions,'conclusion':'candidate_failed_generic_isolation_gate' if failed else 'candidate_gate_passed_for_model','mode_results':suites['slice2_suite.json']['mode_results'],'exploration_limits':{'paths':32,'unresolved_branches':8,'instructions':2000000},'historical_trace_gate_passed':suites['trace_suite.json']['trace_mode_gate_passed'],'historical_slice_gate_passed':suites['slice_suite.json']['slice_mode_gate_passed']}
    write(output/'validation.json',result)
    return {k:result[k] for k in ('conclusion','tests','functional_gate_passed','incompatible_functional_cases','repeated_suites_identical','baseline_regression_completed')}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary-dir',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--regression-lua',type=Path)
    a=p.parse_args();print(json.dumps(run(a.binary_dir.resolve(),a.game.resolve(),a.output_dir.resolve(),a.regression_lua.resolve() if a.regression_lua else None),indent=2))
