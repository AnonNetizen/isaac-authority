"""Delta bundle: reuse the pinned first-gate package, never nest its libraries."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import ROOT,digest,write
BASE_SHA='74f934c1772242fbffb959515df4c826235da21132dfea58ae66f53e6e44a611'

def package(output):
    base=ROOT/'artifacts/isaac-incremental2-native-effects-v2.zip'
    if digest(base)!=BASE_SHA:raise ValueError('Pinned base bundle changed')
    evidence=ROOT/'reports/ui-compact';files={}
    for folder in ['compact_ui_runtime','research/ui_compact_fixtures']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files['authority/'+p.relative_to(ROOT).as_posix()]=p
    for name in ['ui_compact_storage_v1.json','ui_compact_storage_v2.json','ui_compact_storage_v3.json']:
        files['authority/research/'+name]=ROOT/'research'/name
    for name in ['run_compact.py','run_compact_storage.py','read_compact_audit.py','reproduce_compact.py','package_compact.py','cleanup_compact_replay.ps1']:
        files['authority/tools/'+name]=ROOT/'tools'/name
    binary=ROOT/'build-ui-incremental2/compact/Release'
    for name in ['ia_lua533_ui_compact.dll','authority-compact-research.exe']:
        files['authority/build-ui-incremental2/compact/Release/'+name]=binary/name
    for group,complete_key in [('final-regression-v2','complete_51_case_gate'),('final-storage-v2','complete_13_case_gate')]:
        report=json.loads((evidence/group/'result.json').read_text(encoding='utf-8'))
        if not report['passed'] or not report.get(complete_key) or report['runtime_sha256']!=digest(binary/'ia_lua533_ui_compact.dll') or report['runner_sha256']!=digest(binary/'authority-compact-research.exe'):raise ValueError('Final binary/gate mismatch')
        for p in (evidence/group).iterdir():
            if p.is_file():files['evidence/'+group+'/'+p.name]=p
    for group in ['storage-preflight','storage-preflight-v2','userdata-root-gate']:
        files['evidence/history/'+group+'-result.json']=evidence/group/'result.json'
    files['README.md']=ROOT/'docs/COMPACT_GRAPH_AND_RECLAIM.md'
    entries=[{'path':n,'bytes':p.stat().st_size,'sha256':digest(p)} for n,p in sorted(files.items())]
    manifest={'schema':'isaac-compact-delta-1','private_abi':'ia-lua533-slice3-ui-compact-1',
              'base_archive':base.name,'base_sha256':BASE_SHA,'work_limit':10000000,'cases':64,
              'groups':[{'manifest':'research/ui_incremental2_stage1_v7.json','expected':'reports/native-v7','kind':'regression'},
                        {'manifest':'research/ui_incremental2_legacy_oracle_v2.json','expected':'reports/legacy-v4','kind':'regression'},
                        {'manifest':'research/ui_compact_storage_v3.json','expected':'evidence/final-storage-v2','kind':'storage'}],
              'real_mcm_eid_tested':False,'game_started':False,'arbitrary_mod_compatibility_proven':False,'files':entries}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for n,p in sorted(files.items()):archive.write(p,n)
        archive.writestr('compact-bundle-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('Archive CRC failure')
        for e in entries:
            with archive.open(e['path']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=e['sha256']:raise ValueError('Archive entry hash failure')
    sha=digest(output)
    with output.with_suffix('.zip.sha256').open('x',encoding='ascii') as f:f.write(sha+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':sha,'bytes':output.stat().st_size,'files_verified':len(entries),'base_sha256':BASE_SHA,'nested_archives':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(package(a.output.resolve()),ensure_ascii=False))
