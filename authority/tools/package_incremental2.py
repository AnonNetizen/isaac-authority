"""Create a small, non-nested stage-one research bundle with per-file hashes."""
import argparse
import json
import sys
import zipfile
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import ROOT,digest,write

GROUPS=[{'manifest':'research/ui_incremental2_stage1_v7.json','report':'native-v7'},
        {'manifest':'research/ui_incremental2_legacy_oracle_v2.json','report':'legacy-v4'}]

def package(output):
    files={};evidence=ROOT/'reports/ui-incremental2-stage1';runs=[]
    def add(name,path):
        if name in files and files[name]!=path:raise ValueError('Duplicate archive entry')
        files[name]=path
    for name in ['native','third_party/lua533','third_party/nlohmann','trace_runtime','slice_runtime',
                 'slice2_runtime','slice3_ui_runtime','bounded_ui_runtime','incremental_ui_runtime','incremental2_ui_runtime']:
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:add('authority/'+path.relative_to(ROOT).as_posix(),path)
    for name in ['authority_core.lib','authority_lua_bridge.lib']:
        add('authority/build-ui-incremental-encoded/Release/'+name,ROOT/'build-ui-incremental-encoded/Release'/name)
    for name in ['authority-incremental2-research.exe','ia_lua533_ui_incremental2.dll','ia_lua533_ui_incremental2_oracle.dll']:
        add('authority/build-ui-incremental2/Release/'+name,ROOT/'build-ui-incremental2/Release'/name)
    for name in ['ia_lua533_reference.dll','ia_lua533_ui_incremental.dll']:
        add('authority/build-ui-incremental-encoded-v3-release/Release/'+name,ROOT/'build-ui-incremental-encoded-v3-release/Release'/name)
    for group in GROUPS:
        result=json.loads((evidence/group['report']/'result.json').read_text(encoding='utf-8'))
        if not result['preflight_passed'] or not result['complete_manifest_run']:raise ValueError('Incomplete first-gate validation')
        if result['runtime_sha256']!=digest(ROOT/'build-ui-incremental2/Release/ia_lua533_ui_incremental2.dll'):raise ValueError('Runtime changed after validation')
        if result['runner_sha256']!=digest(ROOT/'build-ui-incremental2/Release/authority-incremental2-research.exe'):raise ValueError('Runner changed after validation')
        if digest(ROOT/group['manifest'])!=result['manifest_sha256']:raise ValueError('Frozen suite changed')
        runs.append(result)
        add('authority/'+group['manifest'],ROOT/group['manifest'])
        suite=json.loads((ROOT/group['manifest']).read_text(encoding='utf-8'))
        for case in suite['cases']:
            for chunk in case['chunks']:
                path=ROOT/chunk['file']
                if digest(path)!=chunk['sha256']:raise ValueError('Frozen source changed')
                add('authority/'+chunk['file'],path)
        for path in (evidence/group['report']).iterdir():
            if path.is_file():add('reports/'+group['report']+'/'+path.name,path)
    # Keep failure conclusions with the bundle; large historical binaries stay in
    # their existing protected snapshots, never nested as another research ZIP.
    for folder in ['legacy-oracle','preflight-1','metatable-audit-v1','metatable-audit-v2']:
        add('reports/history/'+folder+'-result.json',evidence/folder/'result.json')
    for path in (evidence/'metatable-audit-v2/binary').iterdir():
        if path.suffix in ('.dll','.exe'):add('reports/history/metatable-audit-v2-binary/'+path.name,path)
    for name in ['ui_incremental_oracle_encoded_v1.json','ui_incremental2_legacy_oracle_v1.json',
                 'ui_incremental2_stage1_v4.json','ui_incremental2_stage1_v5.json','ui_incremental2_stage1_v6.json']:
        add('authority/research/'+name,ROOT/'research'/name)
    for name in ['run_incremental2.py','reproduce_incremental2.py','package_incremental2.py','audit_baseline.py']:
        add('authority/tools/'+name,ROOT/'tools'/name)
    add('README.md',ROOT/'docs/INCREMENTAL2_REFACTOR.md')
    add('reports/stage1-summary.json',evidence/'summary-v2.json')
    add('reports/history/previous-package.sha256',ROOT/'artifacts/isaac-incremental2-native-effects-v1.zip.sha256')
    entries=[{'path':name,'bytes':path.stat().st_size,'sha256':digest(path)} for name,path in sorted(files.items())]
    manifest={'schema':'isaac-incremental2-native-effects-1','revision':2,'private_abi':'ia-lua533-slice3-ui-incremental-2',
              'work_limit':10000000,'groups':GROUPS,'cases':sum(len(r['cases']) for r in runs),
              'native_field_gate_passed':runs[0]['stage_gate_passed'] and runs[1]['preflight_passed'],
              'compact_graph_complete':False,'runtime_audit_stream_complete':False,'graph_gc_complete':False,
              'real_mcm_eid_initialization_run':False,'game_started':False,'entire_refactor_passed':False,'files':entries}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,path in sorted(files.items()):archive.write(path,name)
        archive.writestr('bundle-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    # Verify every member directly without producing an extraction tree.
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise ValueError('Archive CRC failed')
        for entry in entries:
            import hashlib
            with archive.open(entry['path']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:raise ValueError('Archive hash mismatch')
    sha=digest(output)
    with output.with_suffix(output.suffix+'.sha256').open('x',encoding='ascii') as stream:stream.write(sha+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':sha,'bytes':output.stat().st_size,'files_verified':len(entries),'native_field_gate_passed':manifest['native_field_gate_passed']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(package(args.output.resolve()),ensure_ascii=False))
