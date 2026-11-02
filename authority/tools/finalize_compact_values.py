"""Seal compact native observations and remove only owned redundant artifacts."""
import gzip,hashlib,json,statistics,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_compact_values as c
ROOT=c.ROOT
def deterministic(r):
    return [dict(id=x['id'],steps=x['reports'][1]['steps'],semantic=x['reports'][1]['semantic'],verification=[[{k:v for k,v in p.items()if k!='seconds'}for p in run]for run in x['verification']])for x in r['cases']]
def main():
    runs=[json.loads((ROOT/f'reports/compact-values-v{n}/result.json').read_text(encoding='utf-8'))for n in [2,3]];bench=json.loads((ROOT/'reports/compact-values-bench-v1/result.json').read_text(encoding='utf-8'))
    assert bench['passed']and all(r['passed']and len(r['cases'])==24 and len(r['regressions'])==129 and len(r['faults'])==8 for r in runs)
    assert deterministic(runs[0])==deterministic(runs[1])
    for r in runs+[bench]:assert r['binary_sha256']==c.b.old.digest(c.EXE)and r['driver_sha256']==c.b.old.digest(Path(c.__file__))
    for r in runs:
        for row in r['cases']:
            if row['kind']!='encoding-probe':assert row['reports'][0]['budget']['used']==row['reports'][1]['budget']['used'],'Logical work changed: '+row['id']
    sample=bench['cases'][1]['reports'];speedup=statistics.median(x['seconds']for x in sample[:2])/statistics.median(x['seconds']for x in sample[2:]);assert speedup>1
    protected=c.protected();build=(ROOT/'build-compact-value').resolve();assert build==Path('D:/Coding/ISAAC/authority/build-compact-value').resolve()
    binaries={p.relative_to(ROOT).as_posix():c.b.old.digest(p)for p in(build/'Release').iterdir()if p.suffix in ['.exe','.pdb','.lib']};archives=[];cleanup=[]
    for folder in ['compact-values-v1','compact-values-v2','compact-values-v3','compact-values-bench-v1']:
        directory=ROOT/'reports'/folder
        report=json.loads((directory/'result.json').read_text(encoding='utf-8'));requests=[]
        for row in report['cases']:
            for run_index,plans in enumerate(row.get('plans',[])):
                steps=[s for s in row['reports'][run_index+1]['steps']if s.get('metadata',{}).get('observed_sources')]
                requests.extend(dict(capture=s['metadata'],draws=s['draws'],recipes=p)for s,p in zip(steps,plans))
        for name in ['verification-request.json','fault-request.json']:
            p=directory/name
            if p.exists()and json.loads(p.read_text(encoding='utf-8'))in requests:
                assert not p.is_symlink()and p.resolve().is_relative_to(directory.resolve());cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=c.b.old.digest(p),bytes=p.stat().st_size,basis='exact request data already present in retained native reports and plans'));p.unlink()
        for p in sorted((ROOT/'reports'/folder).glob('*.json')):
            target=p.with_name(p.name+'.gz');assert not target.exists()and not p.is_symlink()and p.resolve().is_relative_to((ROOT/'reports').resolve())
            data=p.read_bytes();target.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(target.read_bytes())==data;archives.append(dict(path=target.relative_to(ROOT).as_posix(),sha256=c.b.old.digest(target),raw_sha256=c.b.old.digest(p),raw_bytes=len(data),bytes=target.stat().st_size));p.unlink()
    for p in build.rglob('*'):
        regenerate=p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk','.idb']or(p.suffix=='.pdb'and any(n.endswith('.dir')for n in p.parts))
        if p.is_file()and regenerate:
            assert not p.is_symlink()and p.resolve().is_relative_to(build);cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=c.b.old.digest(p),bytes=p.stat().st_size,basis='regenerable compact-value intermediate'));p.unlink()
    assert protected==c.protected()
    for p,h in binaries.items():assert c.b.old.digest(ROOT/p)==h
    candidate=dict(schema='compact-value-candidate-1',abi='ia-lua533-compact-values-1',executable=c.EXE.relative_to(ROOT).as_posix(),executable_sha256=c.b.old.digest(c.EXE),stock_verifier=c.b.VERIFY.relative_to(ROOT).as_posix(),stock_verifier_sha256=c.b.old.digest(c.b.VERIFY),verifier='tools/verify_compact_values.py',suite=c.MANIFEST.relative_to(ROOT).as_posix(),benchmark_suite=c.BENCH.relative_to(ROOT).as_posix(),results='docs/COMPACT_VALUE_RESULTS.md',work_limit=10000000,child_timeout_seconds=5,origins_verified=False,consumer_cache_enabled=False,authority_projection_passed=False,personal_draws_publishable=False,real_mod_initialization_verified=False,prior='research/bound_value_candidate_v1.json')
    c.b.old.save(ROOT/'research/compact_value_candidate_v1.json',candidate);c.b.old.save(ROOT/'research/boundary_next.json',dict(schema='mutable-research-pointer-1',candidate='research/compact_value_candidate_v1.json',note='Experimental compact observed values; no authority projection or real SDK compatibility claim.'))
    inputs=[c.MANIFEST,c.BENCH,ROOT/'research/compact_value_candidate_v1.json',Path(c.__file__),Path(__file__),ROOT/'tools/verify_compact_values.py',ROOT/'docs/COMPACT_VALUE_PLAN.md',ROOT/'docs/COMPACT_VALUE_RESULTS.md',ROOT/'build-compact-value/generated/derived_sha256.json']+list((ROOT/'compact_value_runtime').iterdir())+list((ROOT/'research/compact_values').glob('*.lua'))
    final=dict(schema='compact-value-final-1',compact_observer_gate_passed=True,cases=24,functional_parameter_cases=12,unresolved_diagnostics=9,native_rollback_cases=1,native_capacity_rejections=1,wire_encoding_checks=252,corruption_rejections=8,old_regressions=129,work_limit=10000000,child_timeout_seconds=5,paired_cpu_speedup=speedup,batch_seconds=[r['seconds']for r in runs],origins_verified=False,consumer_cache_enabled=False,authority_projection_passed=False,personal_draws_publishable=False,real_mod_initialization_verified=False,game_started=False,protected_files_and_saves_unchanged=True,case_results=[dict(id=x['id'],kind=x['kind'],passed=x['passed'])for x in runs[0]['cases']],archives=archives,cleanup=cleanup,cleanup_bytes=sum(x['bytes']for x in cleanup),binaries=binaries,inputs={p.relative_to(ROOT).as_posix():c.b.old.digest(p)for p in inputs if p.is_file()})
    c.b.old.save(ROOT/'reports/compact-values-final.json',final);print(json.dumps(dict(sealed=True,cases=24,regressions=129,wire_encoding_checks=252,speedup=speedup,cleanup_bytes=final['cleanup_bytes'])))
if __name__=='__main__':main()
