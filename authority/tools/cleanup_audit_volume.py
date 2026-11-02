"""Remove only named C++ objects from this build, preserving all runnable outputs."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import digest
ROOT=Path(__file__).resolve().parents[1]
NAMES={
 'ia_lua533_audit_volume.dir':['ia_graph','ia_trace','ia_bounded','liveness','init_profile'],
 'authority-audit-volume.dir':['compact_runner','private_lua_bridge','ui_backend_roots'],
 'authority-audit-volume-real.dir':['consumer_real','private_lua_bridge','ui_backend_roots','mod_runtime_roots'],
 'authority-audit-volume-tests.dir':['volume_journal_tests','init_profile'],
 'authority-audit-wire-tests.dir':['wire_tests','init_profile'],
}
def run(apply):
    base=(ROOT/'build-audit-volume').resolve(strict=True)
    if not base.is_relative_to(ROOT.resolve()) or base.name!='build-audit-volume':raise RuntimeError('Unexpected build root')
    protected={str(p.relative_to(base)):digest(p) for p in base.rglob('*') if p.is_file() and p.suffix.lower() in ['.dll','.exe','.lib','.cpp','.h','.hpp','.inc']}
    targets=[]
    for folder,names in NAMES.items():
        for name in names:
            p=base/folder/'Release'/(name+'.obj')
            if not p.exists():continue
            if p.is_symlink() or not p.resolve().is_relative_to(base):raise RuntimeError('Object target escapes verified build')
            targets.append({'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)})
    removed=[]
    if apply:
        for target in targets:
            p=Path(target['path'])
            if digest(p)!=target['sha256']:raise RuntimeError('Object changed since validation')
            p.unlink();removed.append(target)
    changed=[p for p,h in protected.items() if digest(base/p)!=h]
    report={'schema':'audit-volume-exact-object-cleanup-1','applied':apply,'verified_root':str(base),'targets':targets,'deleted':removed,'removed_bytes':sum(t['bytes'] for t in removed),'protected_files':len(protected),'protected_changed':changed,'recursive_delete':False,'formal_lua_c_objects_touched':False}
    name='audit-volume-build-cleanup.json' if apply else 'audit-volume-build-cleanup-plan.json'
    (ROOT/'reports'/name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['targets','deleted']}))
    if changed:raise RuntimeError('Protected artifact changed')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();run(a.apply)
