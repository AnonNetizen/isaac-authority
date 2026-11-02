"""Freeze the previous candidate before deriving a separate private runtime."""
import hashlib, json, shutil
from pathlib import Path

root=Path(__file__).resolve().parents[1]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
if __name__=='__main__':
    target=root/'slice3_runtime'
    if (target/'ia_graph.cpp').exists(): raise SystemExit('Slice3 already exists; refusing to overwrite')
    files={str(p.relative_to(root)).replace('\\','/'):digest(p)
           for folder in ('slice2_runtime','research') for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    for name in ('artifacts/isaac-authority-slice2-0.1.0-final.zip','build-slice2-release/Release/ia_lua533_slice2.dll'):
        files[name]=digest(root/name)
    (root/'reports/slice3-baseline.json').write_text(json.dumps({'schema':'slice3-preservation-baseline-1','files':files},indent=2)+'\n',encoding='utf-8')
    target.mkdir(exist_ok=True)
    for name in ('ia_graph.cpp','ia_graph.h','CMakeLists.txt'):
        shutil.copyfile(root/'slice2_runtime'/name,target/name)
    p=target/'CMakeLists.txt';p.write_text(p.read_text().replace('SLICE2','SLICE3').replace('slice2','slice3'),encoding='utf-8')
