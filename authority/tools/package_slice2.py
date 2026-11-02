"""Package exact slice2 evidence, preserved slice1 and a repeatable standalone entry."""
import argparse,json,zipfile
from pathlib import Path
from run_slice2_research import ROOT,fingerprints,baseline
from run_trace_research import digest,verify_pristine

def package(binary,evidence,output):
    report=json.loads((evidence/'validation.json').read_text())
    if report['schema']!='isaac-execution-slice2-research-1' or not report['repeated_suites_identical'] or not report['baseline_regression_completed']:raise ValueError('Missing repeat or regression evidence')
    if fingerprints(binary)!=(report['binary_sha256'],report['source_sha256']) or baseline()!=report['immutable_baseline']:raise ValueError('Source/binary changed since validation')
    verify_pristine();files={}
    for name in report['binary_sha256']:files['bin/'+name]=binary/name
    for name in report['source_sha256']:files['source/'+name]=ROOT/name
    files['README.md']=ROOT/'docs/EXECUTION_SLICE2.md'
    files['source/reports/slice2-baseline.json']=ROOT/'reports/slice2-baseline.json'
    files['source/artifacts/isaac-authority-slice-0.1.0-final.zip']=ROOT/'artifacts/isaac-authority-slice-0.1.0-final.zip'
    for p in evidence.rglob('*'):
        if p.is_file():files['reports/current/'+p.relative_to(evidence).as_posix()]=p
    for p in (ROOT/'reports').glob('*.json'):files['reports/history/'+p.name]=p
    for p in (ROOT/'reports').glob('slice2-*.log'):files['reports/history/'+p.name]=p
    for folder in ('slice2-freeze-history','slice2-final-verified','slice2-final-budgeted','slice2-final-release','slice-final-verified','trace-final-release'):
        for p in (ROOT/'reports'/folder).rglob('*'):
            if p.is_file():files['reports/history/'+folder+'/'+p.relative_to(ROOT/'reports'/folder).as_posix()]=p
    records=[{'path':name,'sha256':digest(p),'bytes':p.stat().st_size} for name,p in sorted(files.items())]
    manifest={'version':'slice2-0.1.0','kind':'standalone_x86_lua533_timeline_storage_branch_coin_model','private_abi':report['private_abi'],'game_process_used':False,'game_hooks_installed':False,'game_dll_replaced':False,'native_world_committed':False,'playable':False,'generic_mod_compatibility_passed':False,'diagnostic_passed':True,'functional_gate_passed':report['functional_gate_passed'],'lua_archive_sha256':report['lua_archive_sha256'],'historical_evidence_is_for_its_recorded_hashes':True,'files':records}
    prefix='isaac-authority-slice2-0.1.0/';output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,p in sorted(files.items()):archive.write(p,prefix+name)
        archive.writestr(prefix+'bundle-manifest.json',json.dumps(manifest,indent=2))
    sha=digest(output)
    with output.with_suffix(output.suffix+'.sha256').open('x',encoding='ascii') as f:f.write(sha+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':sha,'files':len(records),'functional_gate_passed':report['functional_gate_passed'],'playable':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary-dir',type=Path,required=True);p.add_argument('--evidence-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(a.binary_dir.resolve(),a.evidence_dir.resolve(),a.output.resolve()),indent=2))
