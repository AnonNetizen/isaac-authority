"""Preserve this research binary/source once; reuse local frozen dependencies."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import digest,write
ROOT=Path(__file__).resolve().parents[1]

def snapshot(output):
    reports=ROOT/'reports/ui-userdata-roots';result=json.loads((reports/'delivery.json').read_text(encoding='utf-8'))
    if not result['userdata_model_gate_passed'] or not result['model_expected_outcomes_passed']:raise ValueError('Completed model gate required')
    files={}
    for directory in ['compact_ui_runtime','research/ui_userdata_fixtures']:
        for path in (ROOT/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:files['authority/'+path.relative_to(ROOT).as_posix()]=path
    for path in ROOT.glob('research/ui_userdata_roots_v*.json'):files['authority/'+path.relative_to(ROOT).as_posix()]=path
    for name in ['run_userdata_roots.py','run_compact_real.py','inspect_compact_prefix.py','snapshot_userdata_roots.py']:
        files['authority/tools/'+name]=ROOT/'tools'/name
    for name in ['ia_lua533_ui_compact.dll','authority-compact-research.exe','authority-compact-real.exe']:
        path=ROOT/'build-ui-incremental2/compact/Release'/name;files['authority/'+path.relative_to(ROOT).as_posix()]=path
    files['README.md']=ROOT/'docs/USERDATA_ROOTS_PLAN.md'
    for name in ['delivery.json','root-gate-final-v5/result.json','final-regression-51/result.json','final-regression-13/result.json','real-six-v2/result.json','real-six-v2/first-evidence-differences.json','real-six-v2/audit-prefix-validation.json','duplicate-audit-cleanup.json']:
        files['evidence/'+name]=reports/name
    entries=[{'path':n,'bytes':p.stat().st_size,'sha256':digest(p)} for n,p in sorted(files.items())]
    manifest={'schema':'userdata-local-snapshot-1','work_limit':10000000,'real_gate_passed':False,'private_abi':result['private_abi'],'root_abi':result['userdata_root_abi'],'runtime_sha256':result['runtime_sha256'],'portable_standalone_package':False,'requires_existing_workspace':True,'external_frozen_inputs_and_library_hashes':result['input_hashes'],'raw_audits_retained_in_workspace_not_copied':True,'files':entries}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in sorted(files.items()):z.write(path,name)
        z.writestr('userdata-snapshot-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as z:
        if z.testzip():raise ValueError('Snapshot CRC failed')
        for e in entries:
            with z.open(e['path']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=e['sha256']:raise ValueError('Snapshot member hash mismatch')
    sha=digest(output)
    with output.with_suffix('.zip.sha256').open('x',encoding='ascii') as f:f.write(sha+'  '+output.name+'\n')
    package={'archive':str(output),'sha256':sha,'bytes':output.stat().st_size,'files_verified':len(entries),'extracted_duplicate_created':False,'real_gate_passed':False,'portable':False}
    write(reports/'snapshot-result.json',package);return package

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(snapshot(a.output.resolve()),ensure_ascii=False))
