"""Build an indexed incremental research layer over the preserved bounded package."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME='isaac-authority-ui-incremental-0.1.3'
BASE_SHA='bdc7755dfb54e03d39982c43e620adbb0adde344197b81d6a9ab690aaa150829'
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def build():
    baseline=ROOT/'artifacts/isaac-authority-ui-bounded-0.1.0.zip'
    if digest(baseline)!=BASE_SHA:raise ValueError('Preserved base package changed')
    overlay={}
    for folder in ['native','incremental_ui_runtime','tools','docs']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:overlay['source/'+p.relative_to(ROOT).as_posix()]=p
    overlay['source/CMakeLists.txt']=ROOT/'CMakeLists.txt'
    for p in (ROOT/'research').glob('ui_incremental*.json'):overlay['source/'+p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'research/ui_incremental_fixtures').glob('*.lua'):overlay['source/'+p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'build-ui-incremental-release/Release').iterdir():
        if p.suffix in ['.exe','.dll']:overlay['bin/'+p.name]=p
    for folder in ['ui-incremental-oracle-final','ui-incremental-real-final','ui-incremental-oracle-liveness','ui-incremental-real-liveness','ui-incremental-liveness-stress']:
        for p in (ROOT/'reports'/folder).iterdir():
            if p.is_file():overlay['reports/'+folder+'/'+p.name]=p
    for p in (ROOT/'reports').glob('ui-incremental-*.json'):overlay['reports/'+p.name]=p
    for folder in ['ui-incremental-before-batch','ui-incremental-before-empty-source','ui-incremental-before-live-stack','ui-incremental-before-liveness']:
        for p in (ROOT/'reports'/folder).iterdir():
            if p.is_file():overlay['reports/'+folder+'/'+p.name]=p
    for filename in ['structure-resize.json','structure-resize.stderr.txt']:
        p=ROOT/'reports/ui-incremental-reproduction/results'/filename
        overlay['history/reproduction-0.1.2/'+filename]=p
    for folder in ['ui-incremental-real-1','ui-incremental-real-2','ui-incremental-real-3','ui-incremental-oracle-1','ui-incremental-oracle-2','ui-incremental-oracle-3','ui-incremental-oracle-4','ui-incremental-oracle-5']:
        for filename in ['real-result.json','oracle-result.json']:
            p=ROOT/'reports'/folder/filename
            if p.exists():overlay['reports/'+folder+'/'+filename]=p
    for filename in ['validation.json','base-checks.json','before.json','after.json']:
        p=ROOT/'reports/ui-incremental-regressions'/filename;overlay['reports/ui-incremental-regressions/'+filename]=p
    overlay['README.md']=ROOT/'docs/INCREMENTAL_UI.md'
    conclusion=ROOT/'reports/ui-incremental-CONCLUSION.txt';overlay['CONCLUSION.txt']=conclusion
    target=ROOT/'artifacts'/f'{NAME}.zip';files={}
    with zipfile.ZipFile(baseline) as old,zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for name in old.namelist():
            rel=name.split('/',1)[1]
            if rel in overlay or rel=='FILES.json' or name.endswith('/'):continue
            if rel=='bundle-manifest.json':rel='history/base-bounded-manifest.json'
            data=old.read(name);out.writestr(NAME+'/'+rel,data);files[rel]=hashlib.sha256(data).hexdigest()
        for rel,p in sorted(overlay.items()):
            out.write(p,NAME+'/'+rel);files[rel]=digest(p)
        index={'schema':'isaac-incremental-package-index-1','files':files,'base_archive_sha256':BASE_SHA,'game_images_fonts_included':False}
        out.writestr(NAME+'/FILES.json',json.dumps(index,indent=2))
    sha=digest(target);target.with_suffix('.zip.sha256').write_text(sha+'\n',encoding='ascii')
    result={'archive':str(target),'sha256':sha,'bytes':target.stat().st_size,'indexed_files':len(files)}
    write(ROOT/'reports/ui-incremental-package.json',result);print(json.dumps(result));return result
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
        if digest(root/name)!=sha:raise ValueError('Extracted file hash differs '+name)
    result={'root':str(root),'archive_sha256':expected,'verified_files':len(index['files'])};print(json.dumps(result));return root,index
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--extract',type=Path);p.add_argument('--destination',type=Path);a=p.parse_args()
    if a.extract:extract(a.extract.resolve(),a.destination.resolve())
    else:build()
