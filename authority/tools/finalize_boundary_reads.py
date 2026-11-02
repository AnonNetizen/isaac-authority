"""Seal current CLI evidence, preserve unique failures, clean only this build."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_reads as r
import run_boundary_handoff as old
ROOT=r.ROOT
def main():
    report=ROOT/'reports/boundary-reads-v10/result.json';result=json.loads(report.read_text(encoding='utf-8'))
    assert result['passed'] and len(result['cases'])==50 and len(result['regressions'])==56 and len(result['stability_probes'])==12
    assert result['driver_sha256']==old.digest(ROOT/'tools/run_boundary_reads.py') and result['manifest_sha256']==old.digest(r.MANIFEST)
    assert result['protected_files_unchanged'] and result['save_files_unchanged'] and result['binaries_unchanged']
    assert result['derived_manifest_sha256']==old.digest(ROOT/'build-read-set/generated/derived_sha256.json')
    for name,h in result['binary_sha256'].items():assert old.digest(ROOT/'build-read-set/Release'/name)==h
    protected=r.protected();binaries={p.relative_to(ROOT).as_posix():old.digest(p) for p in (ROOT/'build-read-set/Release').iterdir() if p.suffix in ['.exe','.lib','.pdb']}
    history=[]
    def compress(p):
        target=p.with_suffix(p.suffix+'.gz');assert not target.exists() and not p.is_symlink()
        assert p.resolve().is_relative_to((ROOT/'reports').resolve())
        data=p.read_bytes();target.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(target.read_bytes())==data
        history.append(dict(path=target.relative_to(ROOT).as_posix(),sha256=old.digest(target),original_sha256=old.digest(p),original_bytes=len(data),bytes=target.stat().st_size));p.unlink()
    for n in range(1,10):
        folder=ROOT/'reports'/('boundary-reads-v'+str(n))
        for p in sorted(folder.glob('*.json')):compress(p)
    compress(ROOT/'reports/boundary-reads-nativefault.exe')
    p=ROOT/'reports/boundary-reads-nativefault-debug.exe.gz';data=gzip.decompress(p.read_bytes())
    history.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=old.digest(p),original_sha256=hashlib.sha256(data).hexdigest(),original_bytes=len(data),bytes=p.stat().st_size))
    cleanup=[];build=(ROOT/'build-read-set').resolve();assert build==Path('D:/Coding/ISAAC/authority/build-read-set').resolve()
    for p in build.rglob('*'):
        remove=p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk','.idb'] or (p.suffix=='.pdb' and any(part.endswith('.dir') for part in p.parts))
        if p.is_file() and remove:
            assert not p.is_symlink() and p.resolve().is_relative_to(build)
            cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=old.digest(p),basis='regenerable objects/compiler databases in current read-set build only; linked symbols preserved'))
    for row in cleanup:
        p=ROOT/row['path'];assert old.digest(p)==row['sha256'];p.unlink()
    assert protected==r.protected()
    for p,h in binaries.items():assert old.digest(ROOT/p)==h
    assert not list(build.rglob('*.audit'))
    current=dict(schema='current-boundary-research-1',abi='ia-lua533-boundary-reads-1',executable='build-read-set/Release/authority-reads.exe',executable_sha256=old.digest(r.EXE),suite=r.MANIFEST.relative_to(ROOT).as_posix(),driver='tools/run_boundary_reads.py',verifier='tools/verify_boundary_reads.py',results='docs/BOUNDARY_READ_SET_RESULTS.md',work_limit=10000000,child_timeout_seconds=5,legacy_write_runtime_unsafe=True,legacy_reason='settt_ double-evaluates side-effecting destination; nil/constant initialization may corrupt GC traversal',legacy_role='preserved offline fault comparison only',consumer_cache_enabled=False,automatic_projection_passed=False,real_mod_initialization_verified=False)
    old.save(ROOT/'research/boundary_current.json',current)
    inputs=[report,r.MANIFEST,ROOT/'research/boundary_current.json',ROOT/'README.md',ROOT/'tools/run_boundary_reads.py',ROOT/'tools/verify_boundary_reads.py',Path(__file__),ROOT/'docs/BOUNDARY_READ_SET_PLAN.md',ROOT/'docs/BOUNDARY_READ_SET_RESULTS.md',ROOT/'build-read-set/generated/derived_sha256.json']
    inputs+=list((ROOT/'read_set_runtime').iterdir())+list((ROOT/'research/boundary_reads').glob('*.lua'))+list((ROOT/'research').glob('boundary_reads_v[1-4].json'))
    summary=dict(schema='boundary-read-set-final-1',read_set_gate_passed=True,legacy_macro_repaired=True,legacy_write_runtime_unsafe=True,functional_cases=sum(c['kind']=='functional' for c in result['cases']),safety_rejections=sum(c['kind']=='safety-rejection' for c in result['cases']),not_reusable_diagnostics=sum(c['kind']=='diagnostic-not-reusable' for c in result['cases']),old_regressions=56,stability_probes=12,work_limit=10000000,child_timeout_seconds=5,consumer_cache_enabled=False,automatic_projection_passed=False,real_mod_initialization_verified=False,game_started=False,normal_audit_bytes=0,protected_files_and_saves_unchanged=True,compressed_history=history,cleanup_bytes=sum(v['bytes'] for v in cleanup),cleanup=cleanup,binaries=binaries,inputs={p.relative_to(ROOT).as_posix():old.digest(p) for p in inputs if p.is_file()})
    summary['protected_inventory_sha256']=hashlib.sha256(json.dumps(protected,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    old.save(ROOT/'reports/boundary-reads-final.json',summary)
    print(json.dumps({k:summary[k] for k in ['read_set_gate_passed','functional_cases','safety_rejections','not_reusable_diagnostics','old_regressions','stability_probes','cleanup_bytes']}))
if __name__=='__main__':main()
