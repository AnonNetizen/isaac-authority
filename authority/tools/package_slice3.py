"""Deliver frozen Slice3 evidence and keep the complete Slice2 package intact."""
import argparse,json,zipfile
from pathlib import Path
from run_slice3_research import ROOT,fingerprints,preserved
from run_trace_research import digest,verify_pristine

def package(binary,evidence,game,output):
    report=json.loads((evidence/'validation.json').read_text())
    if report['schema']!='isaac-execution-slice3-research-1' or not report['repeated_suites_identical'] or not report['baseline_regression_completed']:raise ValueError('Missing validation evidence')
    if fingerprints(binary)!=(report['binary_sha256'],report['source_sha256']) or preserved()!=report['immutable_baseline']:raise ValueError('Evidence fingerprint changed')
    verify_pristine();files={}
    for name in report['binary_sha256']:files['bin/'+name]=binary/name
    for name in report['source_sha256']:files['source/'+name]=ROOT/name
    files['README.md']=ROOT/'docs/EXECUTION_SLICE3.md'
    files['source/reports/slice3-baseline.json']=ROOT/'reports/slice3-baseline.json'
    files['history/isaac-authority-slice2-0.1.0-final.zip']=ROOT/'artifacts/isaac-authority-slice2-0.1.0-final.zip'
    files['history/isaac-authority-slice2-0.1.0-final.zip.sha256']=ROOT/'artifacts/isaac-authority-slice2-0.1.0-final.zip.sha256'
    files['model_game/resources/scripts/enums.lua']=game/'resources/scripts/enums.lua'
    for suite in report['suites']:
        manifest=json.loads((ROOT/'research'/suite).read_text())
        if digest(game/'resources/scripts/enums.lua')!=manifest['enums_sha256']:raise ValueError('Model enums changed')
        for c in manifest['cases']:
            for mod in c['mods']:
                if mod['base']=='game':
                    for name,sha in mod['sha256'].items():
                        p=game/mod['root']/name
                        if digest(p)!=sha:raise ValueError('Frozen game mod changed')
                        files['model_game/'+mod['root']+'/'+name]=p
    for p in evidence.rglob('*'):
        if p.is_file():files['reports/current/'+p.relative_to(evidence).as_posix()]=p
    for pattern in ('slice3-*.json','slice3-*.log'):
        for p in (ROOT/'reports').glob(pattern):files['reports/history/'+p.name]=p
    for p in ROOT.glob('build-slice3*.log'):files['reports/history/build/'+p.name]=p
    records=[{'path':name,'sha256':digest(p),'bytes':p.stat().st_size} for name,p in sorted(files.items())]
    manifest={k:report[k] for k in ('private_abi','view_rule','functional_gate_passed','generic_mod_compatibility_passed','lua_archive_sha256','playable')}
    manifest.update(version='slice3-0.1.0',kind='standalone_x86_dual_view_coin_model',files=records,game_process_used=False,game_dll_replaced=False,real_mcm_eid_tested=False)
    prefix='isaac-authority-slice3-0.1.0/';output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,p in sorted(files.items()):archive.write(p,prefix+name)
        archive.writestr(prefix+'bundle-manifest.json',json.dumps(manifest,indent=2))
    sha=digest(output)
    with output.with_suffix(output.suffix+'.sha256').open('x',encoding='ascii') as f:f.write(sha+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':sha,'files':len(records),'functional_gate_passed':report['functional_gate_passed'],'playable':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','evidence','game','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(*[getattr(a,n).resolve() for n in ('binary','evidence','game','output')]),indent=2))
