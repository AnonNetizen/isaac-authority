"""Package a reproducible first-gate result; image/font bytes remain local."""
import argparse, json, zipfile
from pathlib import Path
from run_slice3_ui_research import ROOT, HISTORY, fingerprints, preserved, verify_inputs
from run_trace_research import digest, verify_pristine

def package(binary,previous,evidence,game,output):
    result=json.loads((evidence/'validation.json').read_text())
    if result['schema']!='isaac-slice3-ui-research-1' or not result['repeated_suites_identical'] or not result['baseline_regression_completed']:
        raise ValueError('Missing repeated gate/regression evidence')
    if fingerprints(binary)!=(result['binary_sha256'],result['source_sha256']) or preserved()!=result['preserved_slice3_artifacts']:
        raise ValueError('Source/binary/history changed since validation')
    verify_pristine();verify_inputs(ROOT,game);files={}
    for name in result['binary_sha256']:files['bin/'+name]=binary/name
    for name in result['source_sha256']:files['source/'+name]=ROOT/name
    files['source/reports/slice3-ui-baseline.json']=ROOT/'reports/slice3-ui-baseline.json'
    files['README.md']=ROOT/'docs/SLICE3_UI.md'
    for suite,mode in HISTORY:
        dll=previous/('ia_lua533_'+mode+'.dll')
        if digest(dll)!=result['historical_suites'][suite]['runtime_sha256']:raise ValueError('Historical DLL changed')
        files['history-bin/'+dll.name]=dll
        definition=json.loads((ROOT/'research'/suite).read_text())
        name='resources/scripts/enums.lua'
        if digest(game/name)!=definition['enums_sha256']:raise ValueError('Model-game enums changed')
        files['model_game/'+name]=game/name
        for case in definition['cases']:
            for mod in case['mods']:
                if mod['base']=='game':
                    for relative,sha in mod['sha256'].items():
                        p=game/mod['root']/relative
                        if digest(p)!=sha:raise ValueError('Historical model input changed')
                        files['model_game/'+mod['root']+'/'+relative]=p
    files['history-bin/authority-slice3-research.exe']=previous/'authority-slice3-research.exe'
    for p in evidence.rglob('*'):
        if p.is_file():files['reports/current/'+p.relative_to(evidence).as_posix()]=p
    for p in (ROOT/'reports').glob('slice3-ui-*'):
        if p.is_file():files['reports/development/'+p.name]=p
    # Original package stays intact on disk. Include its hash/audit rather than
    # nesting a second 239 MB package. This bundle contains the original DLLs,
    # frozen suites and complete current regression evidence for reproduction.
    files['history/slice3-validation.json']=ROOT/'reports/slice3-final-verified/validation.json'
    files['history/slice3-package.sha256']=ROOT/'artifacts/isaac-authority-slice3-0.1.0-verified.zip.sha256'
    entries=[{'path':n,'bytes':p.stat().st_size,'sha256':digest(p)} for n,p in sorted(files.items())]
    # The pinned official Lua source includes its OSI documentation logo.
    # It is not an Isaac resource; verify_pristine already checks its hash.
    lua_documentation_logo='source/third_party/lua533/doc/osi-certified-72x60.png'
    if any(Path(n).suffix.lower() in ('.png','.fnt','.anm2','.jpg','.dds','.ttf') and n!=lua_documentation_logo for n in files):
        raise ValueError('Resource bytes must remain local')
    manifest={'version':'slice3-ui-0.1.0','kind':'standalone_x86_actual_framework_initialization_gate',
        'private_abi':result['private_abi'],'view_rule':result['view_rule'],
        'initialization_contract_gate_passed':result['initialization_contract_gate_passed'],
        'conclusion':result['conclusion'],'game_process_used':False,'render_capture_passed':False,
        'pixel_rendering_tested':False,'resource_bytes_distributed':False,'playable':False,'files':entries}
    output.parent.mkdir(parents=True,exist_ok=True);prefix='isaac-authority-slice3-ui-0.1.0/'
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,p in sorted(files.items()):archive.write(p,prefix+name)
        archive.writestr(prefix+'bundle-manifest.json',json.dumps(manifest,indent=2))
    sha=digest(output)
    with output.with_suffix(output.suffix+'.sha256').open('x',encoding='ascii') as f:f.write(sha+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':sha,'files':len(entries),'bytes':output.stat().st_size,
        'initialization_contract_gate_passed':result['initialization_contract_gate_passed'],'resource_bytes_distributed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','previous','evidence','game','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(*[getattr(a,n).resolve() for n in ('binary','previous','evidence','game','output')]),indent=2))
