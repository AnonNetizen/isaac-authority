"""Verify delivery, losslessly compress superseded short reports, clean owned objects."""
import gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_writes as w
import run_boundary_handoff as old
ROOT=w.ROOT
def main():
    report=ROOT/'reports/boundary-writes-v3/result.json';r=json.loads(report.read_text(encoding='utf-8'))
    assert r['passed'] and len(r['cases'])==38 and len(r['regressions'])==18
    assert r['protected_files_unchanged'] and r['save_files_unchanged'] and not r['consumer_read_sets_implemented'] and not r['automatic_projection_passed']
    assert r['manifest_sha256']==old.digest(w.MANIFEST) and r['driver_sha256']==old.digest(ROOT/'tools/run_boundary_writes.py')
    binaries={p.relative_to(ROOT).as_posix():old.digest(p) for p in (ROOT/'build-write-barrier/Release').iterdir() if p.suffix in ['.exe','.lib']}
    for name,h in r['binary_sha256'].items():assert old.digest(ROOT/'build-write-barrier/Release'/name)==h
    formal=w.protected();history=[]
    for folder in ['boundary-writes-v1','boundary-writes-v2']:
        p=ROOT/'reports'/folder/'result.json';data=p.read_bytes();packed=p.with_suffix('.json.gz')
        assert p.resolve().is_relative_to((ROOT/'reports'/folder).resolve()) and not p.is_symlink() and not packed.exists()
        packed.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(packed.read_bytes())==data
        history.append(dict(path=packed.relative_to(ROOT).as_posix(),sha256=old.digest(packed),original_sha256=old.digest(p),original_bytes=len(data),bytes=packed.stat().st_size,reason='lossless earlier short verification; same candidate binary, earlier case/driver inventory'))
        p.unlink()
    build=(ROOT/'build-write-barrier').resolve();assert build==Path('D:/Coding/ISAAC/authority/build-write-barrier').resolve();cleanup=[]
    for p in build.rglob('*'):
        if p.is_file() and p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk']:
            assert not p.is_symlink() and p.resolve().is_relative_to(build)
            cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=old.digest(p),basis='regenerable objects in this new candidate only'))
    for row in cleanup:
        p=ROOT/row['path'];assert old.digest(p)==row['sha256'];p.unlink()
    assert formal==w.protected()
    for p,h in binaries.items():assert old.digest(ROOT/p)==h
    inputs=[w.MANIFEST,ROOT/'research/boundary_writes_v1.json',report,ROOT/'tools/run_boundary_writes.py',ROOT/'tools/verify_boundary_writes.py',Path(__file__),ROOT/'docs/BOUNDARY_WRITE_BARRIER_PLAN.md',ROOT/'docs/BOUNDARY_WRITE_BARRIER_RESULTS.md',ROOT/'build-write-barrier/generated/derived_sha256.json']
    inputs+=list((ROOT/'write_barrier_runtime').iterdir())+list((ROOT/'research/boundary_writes').glob('*.lua'))
    summary=dict(schema='boundary-write-barriers-final-1',write_barrier_gate_passed=True,functional_cases=sum(c['kind']=='functional' for c in r['cases']),safety_rejection_cases=sum(c['kind']=='safety-rejection' for c in r['cases']),old_regressions=18,work_limit=10000000,child_timeout_seconds=5,consumer_read_sets_implemented=False,automatic_mixed_projection_passed=False,game_started=False,full_trace_enabled=False,normal_audit_bytes=0,protected_files_and_saves_unchanged=True,cleanup_bytes=sum(c['bytes'] for c in cleanup),cleanup=cleanup,historical_reports=history,inputs={p.relative_to(ROOT).as_posix():old.digest(p) for p in inputs if p.is_file()},binaries=binaries,imported_libraries={p:old.digest(ROOT/p) for p in ['build-boundary/Release/boundary_lua.lib','build-ui-incremental-encoded/Release/authority_core.lib']})
    old.save(ROOT/'reports/boundary-writes-final.json',summary)
    print(json.dumps({k:summary[k] for k in ['write_barrier_gate_passed','functional_cases','safety_rejection_cases','old_regressions','cleanup_bytes','normal_audit_bytes']}))
if __name__=='__main__':main()
