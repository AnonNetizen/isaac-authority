"""Package the verified standalone trace experiment separately from historical J460 releases."""
import argparse
import json
from pathlib import Path
import zipfile
from run_trace_research import ROOT,digest,source_files,verify_pristine

def package(binary_dir,evidence_dir,output):
    validation=json.loads((evidence_dir/'validation.json').read_text())
    if validation['schema']!='isaac-execution-trace-research-1' or not validation['repeated_suites_identical'] or validation['unexpected_failures']:
        raise ValueError('Missing successful repeated diagnostics')
    if not validation['baseline_regression_completed']:raise ValueError('Missing original regression validation')
    if not all(test['passed'] for test in validation['tests'].values()):raise ValueError('Missing propagation/semantic checks')
    current={p.relative_to(ROOT).as_posix():digest(p) for p in source_files()}
    if current!=validation['source_sha256']:raise ValueError('Source changed since validation')
    verify_pristine();files={}
    for name,expected in validation['binary_sha256'].items():
        if digest(binary_dir/name)!=expected:raise ValueError('Binary changed since validation: '+name)
        files['bin/'+name]=binary_dir/name
    for name in current:files['source/'+name]=ROOT/name
    files['README.md']=ROOT/'docs/EXECUTION_DEPENDENCIES.md'
    for path in (ROOT/'docs').glob('*.md'):files['docs/'+path.name]=path
    for path in evidence_dir.rglob('*'):
        if path.is_file():files['reports/current/'+path.relative_to(evidence_dir).as_posix()]=path
    # Historical evidence includes hashes for its own binaries; it does not certify these binaries.
    for path in (ROOT/'reports').glob('*.json'):files['reports/history/'+path.name]=path
    for path in (ROOT/'reports').glob('*.md'):files['reports/history/'+path.name]=path
    records=[{'path':name,'sha256':digest(path),'bytes':path.stat().st_size} for name,path in sorted(files.items())]
    manifest={'version':'trace-0.1.0','kind':'standalone_x86_lua533_execution_dependency_coin_model',
              'game_process_used':False,'game_hooks_installed':False,'game_dll_replaced':False,'current_j460_batch_validated':False,
              'diagnostic_passed':True,'trace_mode_gate_passed':validation['trace_mode_gate_passed'],
              'generic_mod_compatibility_passed':False,'playable':False,'lua_archive_sha256':validation['lua_archive_sha256'],
              'historical_evidence_is_for_its_recorded_hashes':True,'files':records}
    output.parent.mkdir(parents=True,exist_ok=True);prefix='isaac-authority-trace-0.1.0/'
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,path in sorted(files.items()):archive.write(path,prefix+name)
        archive.writestr(prefix+'bundle-manifest.json',json.dumps(manifest,indent=2))
    sha=digest(output)
    with output.with_suffix(output.suffix+'.sha256').open('x',encoding='ascii') as checksum:checksum.write(sha+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':sha,'files':len(records),'trace_mode_gate_passed':validation['trace_mode_gate_passed'],'playable':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary-dir',type=Path,required=True)
    parser.add_argument('--evidence-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(package(args.binary_dir.resolve(),args.evidence_dir.resolve(),args.output.resolve()),indent=2))
