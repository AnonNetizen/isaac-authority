"""Package the verified optimization candidate over the preserved 0.1.3 layer."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from run_incremental_ui import ROOT,digest,write
NAME='isaac-authority-ui-incremental-0.1.4'
BASE_SHA='923240ad9a5f6b1114269dd62cdc340561bc5af4ceab1d7bd6d7377a9a9f742e'

def build():
    baseline=ROOT/'artifacts/isaac-authority-ui-incremental-0.1.3.zip'
    if digest(baseline)!=BASE_SHA:raise ValueError('Preserved base package changed')
    overlay={}
    for folder in ['incremental_ui_runtime','tools','docs']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:overlay['source/'+p.relative_to(ROOT).as_posix()]=p
    overlay['source/CMakeLists.txt']=ROOT/'CMakeLists.txt'
    for p in (ROOT/'research').glob('ui_incremental*.json'):overlay['source/'+p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'research/ui_incremental_fixtures').glob('*.lua'):overlay['source/'+p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'build-ui-incremental-factored-release/Release').iterdir():
        if p.suffix in ['.exe','.dll']:overlay['bin/'+p.name]=p
    for folder in ['ui-incremental-factored-oracle','ui-incremental-factored-real','ui-incremental-factored-boundaries','ui-incremental-factored-regressions','ui-incremental-leaf-oracle']:
        for p in (ROOT/'reports'/folder).rglob('*'):
            if p.is_file():overlay['reports/'+folder+'/'+p.relative_to(ROOT/'reports'/folder).as_posix()]=p
    # Keep failed probes and every earlier binary with its independent hash index.
    for folder in ['ui-incremental-5m-preserved','ui-incremental-monotone-preserved','ui-incremental-leaf-preserved','ui-incremental-leaf-boundaries','ui-incremental-leaf-boundaries-v2','ui-incremental-leaf-boundaries-v3']:
        for p in (ROOT/'reports'/folder).rglob('*'):
            if p.is_file():overlay['history/'+folder+'/'+p.relative_to(ROOT/'reports'/folder).as_posix()]=p
    for folder in ['ui-incremental-monotone-oracle','ui-incremental-monotone-real','ui-incremental-leaf-real','ui-incremental-leaf-timing','ui-incremental-factored-timing']:
        name='comparison.json' if 'timing' in folder else ('oracle-result.json' if 'oracle' in folder else 'real-result.json')
        p=ROOT/'reports'/folder/name;overlay['reports/'+folder+'/'+name]=p
    for name in ['ui-incremental-optimization-delivery.json','ui-incremental-factoring-proof.json','ui-incremental-optimization-audit.json']:
        p=ROOT/'reports'/name;overlay['reports/'+name]=p
    overlay['README.md']=ROOT/'docs/INCREMENTAL_UI_OPTIMIZATION.md'
    target=ROOT/'artifacts'/f'{NAME}.zip';files={}
    with zipfile.ZipFile(baseline) as old,zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for entry in old.infolist():
            rel=entry.filename.split('/',1)[1]
            if entry.is_dir() or rel=='FILES.json':continue
            if rel.startswith('bin/'):rel='history/2m-base-'+rel
            if rel in overlay:continue
            h=hashlib.sha256()
            with old.open(entry) as src,out.open(NAME+'/'+rel,'w',force_zip64=True) as dst:
                while chunk:=src.read(1024*1024):h.update(chunk);dst.write(chunk)
            files[rel]=h.hexdigest()
        for rel,p in sorted(overlay.items()):out.write(p,NAME+'/'+rel);files[rel]=digest(p)
        index={'schema':'isaac-incremental-optimization-index-1','files':files,'base_archive_sha256':BASE_SHA,'game_images_fonts_included':False}
        out.writestr(NAME+'/FILES.json',json.dumps(index,indent=2))
    sha=digest(target);target.with_suffix('.zip.sha256').write_text(sha+'\n',encoding='ascii')
    result={'archive':str(target),'sha256':sha,'bytes':target.stat().st_size,'indexed_files':len(files)}
    write(ROOT/'reports/ui-incremental-optimization-package.json',result);print(json.dumps(result),flush=True)

def extract(archive,destination):
    expected=archive.with_suffix('.zip.sha256').read_text().strip()
    if digest(archive)!=expected:raise ValueError('Archive hash mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            final=(destination/member).resolve()
            if not final.is_relative_to(destination.resolve()):raise ValueError('Archive path escape')
        z.extractall(destination)
    root=destination/NAME;index=json.loads((root/'FILES.json').read_bytes())
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=set(index['files'])|{'FILES.json'}:raise ValueError('Extracted file set differs')
    for name,sha in index['files'].items():
        if digest(root/name)!=sha:raise ValueError('Extracted hash differs '+name)
    return root,index

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--extract',type=Path);p.add_argument('--destination',type=Path);a=p.parse_args()
    if a.extract:
        root,index=extract(a.extract.resolve(),a.destination.resolve());print(json.dumps({'root':str(root),'verified_files':len(index['files'])}))
    else:build()
