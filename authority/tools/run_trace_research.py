"""Repeat the standalone x86 dependency experiment; never launches or attaches to Isaac."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
from validate import source_files,validate

ROOT=Path(__file__).resolve().parents[1]
BINS=('authority-trace-research.exe','ia_lua533_trace.dll','ia_lua533_reference.dll',
      'authority-tests.exe','authority-bridge-tests.exe','authority-runtime-tests.exe',
      'authority-resource-tests.exe','authority-suite-tests.exe','isaac-authority.exe','isaac_authority_probe.dll')
LUA_ARCHIVE_SHA='5113c06884f7de453ce57702abaac1d618307f33f6789fa870e87a59d772aca2'
LUA_SOURCE_INDEX_SHA='a33e8a3c98d2d219b66b5d34ceb2d851c72aa4033ce4a3b2c5f3fc2ddc53326e'
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8') as out:json.dump(value,out,indent=2,ensure_ascii=True)
def verify_pristine():
    base=ROOT/'third_party/lua533';manifest=json.loads((base/'SOURCE.json').read_text())
    if digest(base/'SOURCE.json')!=LUA_SOURCE_INDEX_SHA:raise ValueError('Unpinned Lua source index')
    if manifest['archive_sha256']!=LUA_ARCHIVE_SHA:raise ValueError('Unexpected Lua source archive hash')
    for record in manifest['files']:
        path=(base/record['path']).resolve()
        if not path.is_relative_to(base.resolve()) or digest(path)!=record['sha256']:raise ValueError('Pristine source mismatch: '+record['path'])
    return len(manifest['files'])
def fingerprints(binary_dir):
    binary={}
    for name in BINS:
        path=binary_dir/name;data=path.read_bytes();offset=struct.unpack_from('<I',data,0x3c)[0]
        if data[offset:offset+4]!=b'PE\0\0' or struct.unpack_from('<H',data,offset+4)[0]!=0x14c:raise ValueError('Expected Windows x86 PE: '+name)
        binary[name]=digest(path)
    source={path.relative_to(ROOT).as_posix():digest(path) for path in source_files()}
    return binary,source
def run(binary_dir,game,output,regression_lua=None):
    output.mkdir(parents=True,exist_ok=False)
    binary,source=fingerprints(binary_dir);pristine=verify_pristine()
    env=dict(os.environ,IA_TRACE_BINARY_DIR=str(binary_dir),IA_TRACE_GAME_DIR=str(game))
    checks={}
    for name in ('test_trace_runtime.py','test_trace_suite.py'):
        start=time.perf_counter()
        process=subprocess.run([sys.executable,str(ROOT/'tests'/name)],capture_output=True,text=True,encoding='utf-8',env=env,timeout=90)
        (output/(name+'.log')).write_text(process.stdout+process.stderr,encoding='utf-8')
        if process.returncode:raise RuntimeError(name+' failed; see '+str(output/(name+'.log')))
        count=re.search(r'Ran (\d+) tests',process.stderr)
        if not count:raise RuntimeError('Missing test count')
        checks[name]={'passed':int(count.group(1)),'elapsed_seconds':round(time.perf_counter()-start,6)}
    runs=[];times=[]
    for index in range(2):
        start=time.perf_counter()
        process=subprocess.run([str(binary_dir/BINS[0]),'--suite',str(binary_dir/BINS[1]),binary[BINS[1]],str(game),str(ROOT),str(ROOT/'research/trace_suite.json')],capture_output=True,text=True,encoding='utf-8',timeout=45)
        report=json.loads(process.stdout);write(output/f'suite-{index+1}.json',report)
        if process.returncode or not report['diagnostic_passed']:raise RuntimeError('Suite diagnostic failed: '+process.stderr)
        runs.append(report);times.append(round(time.perf_counter()-start,6))
    if runs[0]!=runs[1]:raise RuntimeError('Repeated suite results differ')
    cases_dir=output/'cases';cases_dir.mkdir()
    for case in runs[0]['cases']:write(cases_dir/(case['id']+'.json'),case)
    regression=None
    if regression_lua is not None:
        regression=validate(binary_dir,regression_lua);write(output/'regression.json',regression)
    if fingerprints(binary_dir)!=(binary,source):raise RuntimeError('Sources or binaries changed while tests ran')
    gate=runs[0]['trace_mode_gate_passed']
    result={'schema':'isaac-execution-trace-research-1','research_version':'trace-0.1.0','standalone_only':True,
            'game_process_used':False,'game_hooks_installed':False,'game_dll_replaced':False,'native_world_committed':False,
            'old_presentation_retained':True,'historical_suite_sha256':digest(ROOT/'research/runtime_suite.json'),
            'manifest_sha256':digest(ROOT/'research/trace_suite.json'),'lua_archive_sha256':LUA_ARCHIVE_SHA,
            'pristine_lua_files_verified':pristine,'binary_sha256':binary,'source_sha256':source,
            'tests':checks,'repeated_suites_identical':True,'suite_elapsed_seconds':times,'mode_results':runs[0]['mode_results'],
            'expected_outcomes_passed':runs[0]['expected_outcomes_passed'],'unexpected_failures':runs[0]['failed'],'unverified_cases':runs[0]['skipped'],
            'trace_mode_gate_passed':gate,'conclusion':'candidate_gate_passed_for_model' if gate else 'candidate_failed_generic_isolation_gate',
            'generic_mod_compatibility_passed':False,'playable':False,'baseline_regression_completed':regression is not None,
            'failing_trace_gates':[c['id'] for c in runs[0]['cases'] if c['mode']=='trace' and not c['compatibility_passed']]}
    write(output/'validation.json',result)
    return {k:result[k] for k in ('conclusion','tests','expected_outcomes_passed','unexpected_failures','unverified_cases','repeated_suites_identical','trace_mode_gate_passed','baseline_regression_completed')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary-dir',type=Path,required=True);parser.add_argument('--game',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--regression-lua',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.binary_dir.resolve(),args.game.resolve(),args.output_dir.resolve(),args.regression_lua.resolve() if args.regression_lua else None),indent=2))
