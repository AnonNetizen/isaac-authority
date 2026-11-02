"""Seal numeric read handles + symbolic drawing recipes, without new packages."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_compact_reads as c
import run_draw_plans as d
import run_boundary_handoff as old
ROOT=c.ROOT
def main():
    compact_path=ROOT/'reports/compact-reads-v3/result.json';draw_path=ROOT/'reports/draw-plans-v5/result.json'
    comp=json.loads(compact_path.read_text(encoding='utf-8'));draw=json.loads(draw_path.read_text(encoding='utf-8'))
    assert comp['passed']and len(comp['cases'])==12 and len(comp['regressions'])==106 and draw['passed']and len(draw['cases'])==11
    assert comp['binary_sha256']==draw['binary_sha256']==old.digest(c.EXE)
    assert comp['driver_sha256']==old.digest(ROOT/'tools/run_compact_reads.py')and draw['driver_sha256']==old.digest(ROOT/'tools/run_draw_plans.py')
    assert draw['inspector_sha256']==old.digest(ROOT/'tools/inspect_draw_plans.py')
    assert comp['manifest_sha256']==old.digest(c.MANIFEST)and draw['manifest_sha256']==old.digest(d.MANIFEST)
    protected=c.protected();build=(ROOT/'build-compact-read').resolve();assert build==Path('D:/Coding/ISAAC/authority/build-compact-read').resolve()
    binaries={p.relative_to(ROOT).as_posix():old.digest(p)for p in (build/'Release').iterdir()if p.suffix in ['.exe','.pdb','.lib']}
    archives=[]
    for folder in ['compact-reads-v1','compact-reads-v2','compact-reads-v3','draw-plans-v1','draw-plans-v2','draw-plans-v3','draw-plans-v4','draw-plans-v5']:
        for p in sorted((ROOT/'reports'/folder).glob('*.json')):
            if p.name=='baseline-manifest.json':continue
            target=p.with_suffix(p.suffix+'.gz');assert not target.exists()and not p.is_symlink()and p.resolve().is_relative_to((ROOT/'reports').resolve())
            data=p.read_bytes();target.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(target.read_bytes())==data
            archives.append(dict(path=target.relative_to(ROOT).as_posix(),original_sha256=old.digest(p),sha256=old.digest(target),original_bytes=len(data),bytes=target.stat().st_size));p.unlink()
    cleanup=[]
    for p in build.rglob('*'):
        regenerate=p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk','.idb']or(p.suffix=='.pdb'and any(n.endswith('.dir')for n in p.parts))
        if p.is_file()and regenerate:
            assert not p.is_symlink()and p.resolve().is_relative_to(build)
            cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=old.digest(p),basis='regenerable intermediate in this compact candidate only'))
    for v in cleanup:
        p=ROOT/v['path'];assert old.digest(p)==v['sha256'];p.unlink()
    assert protected==c.protected()
    for p,h in binaries.items():assert old.digest(ROOT/p)==h
    assert not list(build.rglob('*.audit'))
    candidate=dict(schema='compact-read-candidate-1',abi='ia-lua533-compact-reads-1',executable='build-compact-read/Release/authority-compact-reads.exe',executable_sha256=old.digest(c.EXE),verifier='tools/verify_compact_reads.py',suite=c.MANIFEST.relative_to(ROOT).as_posix(),draw_suite=d.MANIFEST.relative_to(ROOT).as_posix(),results='docs/COMPACT_READ_RESULTS.md',work_limit=10000000,child_timeout_seconds=5,bindings_verified=False,consumer_cache_enabled=False,automatic_projection_passed=False,real_mod_initialization_verified=False,stable_baseline='research/boundary_current.json')
    old.save(ROOT/'research/compact_read_candidate_v1.json',candidate)
    old.save(ROOT/'research/boundary_next.json',dict(schema='mutable-research-pointer-1',candidate='research/compact_read_candidate_v1.json',note='Experimental continuation; does not replace the sealed baseline. Mutable pointer is not part of immutable evidence.'))
    measure=next(v for v in comp['cases']if v['id']=='execution-only-long')['reports'];shared=next(v for v in comp['cases']if v['id']=='shared-long-sibling')['reports'][2]
    inputs=[c.MANIFEST,d.MANIFEST,ROOT/'research/compact_read_candidate_v1.json',ROOT/'docs/COMPACT_READ_PLAN.md',ROOT/'docs/COMPACT_READ_RESULTS.md',ROOT/'tools/run_compact_reads.py',ROOT/'tools/run_draw_plans.py',ROOT/'tools/inspect_draw_plans.py',ROOT/'tools/verify_compact_reads.py',Path(__file__),ROOT/'build-compact-read/generated/derived_sha256.json']
    inputs+=list((ROOT/'compact_read_runtime').iterdir())+list((ROOT/'research/compact_reads').glob('*.lua'))+[ROOT/'research/compact_reads_v1.json',ROOT/'research/draw_plans_v1.json',ROOT/'research/draw_plans_v2.json']
    summary=dict(schema='compact-read-final-1',compact_read_gate_passed=True,compact_functional_cases=10,compact_safety_rejections=2,old_regressions=106,symbolic_template_cases=3,unresolved_template_diagnostics=6,template_capacity_rejections=2,draw_scope='symbolic bytecode recipes without value/version/caller bindings',bindings_verified=False,consumer_cache_enabled=False,automatic_projection_passed=False,real_mod_initialization_verified=False,work_limit=10000000,child_timeout_seconds=5,game_started=False,protected_files_and_saves_unchanged=comp['protected_files_unchanged']and comp['save_files_unchanged'],layout_probes=comp['layout_probes'],shared_key_storage=shared['metadata'][1]['compact_storage'],execution_only_samples=[dict(mode=mode,seconds=r['seconds'],private_commit_bytes=r['private_commit_bytes'],charged_work=r['budget']['used'])for mode,r in zip(['stock','prior','compact-1','compact-2'],measure)],compact_case_results=[dict(id=v['id'],kind=v['kind'],passed=v['passed'])for v in comp['cases']],draw_case_results=[dict(id=v['id'],kind=v['kind'],passed=v['passed'])for v in draw['cases']],archives=archives,cleanup=cleanup,cleanup_bytes=sum(v['bytes']for v in cleanup),binaries=binaries,inputs={p.relative_to(ROOT).as_posix():old.digest(p)for p in inputs if p.is_file()},protected_inventory_sha256=hashlib.sha256(json.dumps(protected,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    old.save(ROOT/'reports/compact-read-final.json',summary)
    print(json.dumps({k:summary[k]for k in ['compact_read_gate_passed','compact_functional_cases','compact_safety_rejections','old_regressions','symbolic_template_cases','unresolved_template_diagnostics','template_capacity_rejections','cleanup_bytes']}))
if __name__=='__main__':main()
