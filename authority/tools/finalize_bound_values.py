"""Seal the bounded observation gate; keep no duplicate plaintext reports."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_bound_values as b
import run_boundary_handoff as old
ROOT=b.ROOT

def deterministic(report):
    return [dict(id=c['id'],semantic=c['native_reports'][2]['semantic'],steps=c['native_reports'][2]['steps'],metadata=b.repeat_metadata(c['native_reports'][2]['metadata']),plans=c['plans'],verification=[[{k:v for k,v in p.items()if k!='seconds'}for p in run]for run in c['verification']])for c in report['cases']]

def main():
    runs=[json.loads((ROOT/f'reports/bound-values-v{v}/result.json').read_text(encoding='utf-8'))for v in [3,4]]
    for r in runs:
        assert r['passed']and len(r['cases'])==21 and len(r['faults'])==8 and len(r['regressions'])==129
        assert r['driver_sha256']==old.digest(ROOT/'tools/run_bound_values.py')and r['manifest_sha256']==old.digest(b.MANIFEST)
        assert r['inspector_sha256']==old.digest(ROOT/'tools/inspect_draw_plans.py')
        assert r['derived_manifest_sha256']==old.digest(ROOT/'build-bound-value/generated/derived_sha256.json')
        assert r['protected_files_unchanged']and r['save_files_unchanged']
        assert r['binary_sha256']=={p.name:old.digest(p)for p in [b.EXE,b.VERIFY]}
    assert deterministic(runs[0])==deterministic(runs[1]),'Across-batch evidence differs'
    protected=b.protected();build=(ROOT/'build-bound-value').resolve();assert build==Path('D:/Coding/ISAAC/authority/build-bound-value').resolve()
    binaries={p.relative_to(ROOT).as_posix():old.digest(p)for p in(build/'Release').iterdir()if p.suffix in ['.exe','.pdb','.lib']}
    archives=[]
    for folder in ['bound-values-smoke-v1','bound-values-smoke-v2','bound-values-v1','bound-values-v2','bound-values-v3','bound-values-v4']:
        for p in sorted((ROOT/'reports'/folder).iterdir()):
            if not p.is_file()or p.suffix=='.gz':continue
            assert p.suffix in ['.json','.stdout','.stderr']
            target=p.with_name(p.name+'.gz');assert not target.exists()and not p.is_symlink()and p.resolve().is_relative_to((ROOT/'reports').resolve())
            data=p.read_bytes();target.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(target.read_bytes())==data
            archives.append(dict(path=target.relative_to(ROOT).as_posix(),original_sha256=old.digest(p),sha256=old.digest(target),original_bytes=len(data),bytes=target.stat().st_size));p.unlink()
    cleanup=[]
    for p in build.rglob('*'):
        regenerate=p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk','.idb']or(p.suffix=='.pdb'and any(n.endswith('.dir')for n in p.parts))
        if p.is_file()and regenerate:
            assert not p.is_symlink()and p.resolve().is_relative_to(build)
            cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=old.digest(p),basis='regenerable intermediate in bound-value candidate only'))
    for row in cleanup:
        p=ROOT/row['path'];assert old.digest(p)==row['sha256'];p.unlink()
    assert protected==b.protected()
    for p,h in binaries.items():assert old.digest(ROOT/p)==h
    assert not list(build.rglob('*.audit'))
    candidate=dict(schema='bound-value-candidate-1',abi='ia-lua533-bound-values-1',executable=b.EXE.relative_to(ROOT).as_posix(),executable_sha256=old.digest(b.EXE),stock_verifier=b.VERIFY.relative_to(ROOT).as_posix(),stock_verifier_sha256=old.digest(b.VERIFY),verifier='tools/verify_bound_values.py',suite=b.MANIFEST.relative_to(ROOT).as_posix(),results='docs/BOUND_VALUE_RESULTS.md',work_limit=10000000,child_timeout_seconds=5,scope='read-time observed frame scalar equality only',origins_verified=False,consumer_cache_enabled=False,authority_projection_passed=False,personal_draws_publishable=False,real_mod_initialization_verified=False,prior='research/compact_read_candidate_v1.json',stable_baseline='research/boundary_current.json')
    old.save(ROOT/'research/bound_value_candidate_v1.json',candidate)
    old.save(ROOT/'research/boundary_next.json',dict(schema='mutable-research-pointer-1',candidate='research/bound_value_candidate_v1.json',note='Experimental observed values only; does not replace the sealed baseline. Mutable pointer is not part of immutable evidence.'))
    inputs=[b.MANIFEST,ROOT/'research/bound_values_v1.json',ROOT/'research/bound_value_candidate_v1.json',ROOT/'docs/BOUND_VALUE_PLAN.md',ROOT/'docs/BOUND_VALUE_RESULTS.md',ROOT/'tools/run_bound_values.py',ROOT/'tools/verify_bound_values.py',Path(__file__),ROOT/'build-bound-value/generated/derived_sha256.json']
    inputs+=list((ROOT/'bound_value_runtime').iterdir())+list((ROOT/'research/bound_values').glob('*.lua'))+[ROOT/'build-boundary/Release/boundary_lua.lib']
    summary=dict(schema='observed-binding-final-1',observed_frame_gate_passed=True,observed_frame_functional_cases=12,unresolved_diagnostics=7,native_rollback_cases=1,native_capacity_rejections=1,corruption_rejections=8,old_regressions=129,origins_verified=False,consumer_cache_enabled=False,authority_projection_passed=False,personal_draws_publishable=False,real_mod_initialization_verified=False,work_limit=10000000,child_timeout_seconds=5,game_started=False,protected_files_and_saves_unchanged=True,batch_seconds=[r['seconds']for r in runs],case_results=[dict(id=c['id'],kind=c['kind'],passed=c['passed'])for c in runs[0]['cases']],repeat_evidence_sha256=hashlib.sha256(json.dumps(deterministic(runs[0]),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),archives=archives,cleanup=cleanup,cleanup_bytes=sum(v['bytes']for v in cleanup),binaries=binaries,inputs={p.relative_to(ROOT).as_posix():old.digest(p)for p in inputs if p.is_file()},protected_inventory_sha256=hashlib.sha256(json.dumps(protected,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    old.save(ROOT/'reports/bound-values-final.json',summary)
    print(json.dumps({k:summary[k]for k in ['observed_frame_gate_passed','observed_frame_functional_cases','unresolved_diagnostics','old_regressions','cleanup_bytes']}))
if __name__=='__main__':main()
