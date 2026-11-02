"""Remove only explicitly named C++ object outputs from this candidate build."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
NAMES={
 'ia_lua533_consumers.dir':['ia_graph','ia_trace','ia_bounded','liveness'],
 'authority-consumers.dir':['compact_runner','private_lua_bridge','ui_backend_roots'],
 'authority-consumers-real.dir':['consumer_real','private_lua_bridge','ui_backend_roots','mod_runtime_roots'],
}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(apply):
    base=(ROOT/'build-consumers').resolve(strict=True)
    if not base.is_relative_to(ROOT.resolve()) or base.name!='build-consumers':raise RuntimeError('Unexpected build root')
    protected={str(p.relative_to(base)):digest(p) for p in base.rglob('*') if p.is_file() and p.suffix.lower() in ['.dll','.exe','.lib','.cpp','.h','.hpp','.inc']}
    targets=[]
    for folder,names in NAMES.items():
        for name in names:
            p=base/folder/'Release'/(name+'.obj')
            if not p.exists():continue
            if not p.resolve().is_relative_to(base) or p.suffix!='.obj' or p.is_symlink():raise RuntimeError('Object target escapes verified build')
            targets.append({'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)})
    removed=[]
    if apply:
        for target in targets:
            p=Path(target['path'])
            if digest(p)!=target['sha256']:raise RuntimeError('Object changed since validation')
            p.unlink();removed.append(target)
    changed=[name for name,h in protected.items() if digest(base/name)!=h]
    report={'schema':'consumer-explicit-object-cleanup-1','applied':apply,'verified_root':str(base),'targets':targets,'deleted':removed,'removed_bytes':sum(t['bytes'] for t in removed),'protected_files':len(protected),'protected_changed':changed,'recursive_delete':False,'formal_lua_c_objects_touched':False}
    output=ROOT/'reports'/('consumer-build-cleanup.json' if apply else 'consumer-build-cleanup-plan.json');output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['targets','deleted']},ensure_ascii=False))
    if changed:raise RuntimeError('Protected artifact changed')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();run(a.apply)
