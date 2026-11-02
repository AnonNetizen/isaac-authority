"""Consolidate this one-off measurement and preserve the formal candidate."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import measure_boundary_uncapped as m
ROOT=m.ROOT;OUT=ROOT/'reports/boundary-uncapped-20261016'

def main():
    original=(OUT/'result.json').read_bytes();result=json.loads(original)
    comparison=json.loads((OUT/'cpu-comparison.json').read_text(encoding='utf-8'))
    assert result['formal_files_unchanged']and result['save_files_unchanged']and result['frozen_real_files_unchanged']
    assert len(result['cases'])==29 and sum(c['completed']for c in result['cases'])==26
    assert result['binary_sha256']==m.old.digest(m.EXE)and result['driver_sha256']==m.old.digest(Path(m.__file__))
    assert comparison['ordinary_results_equal']and comparison['bindings_on_work']==23000452 and comparison['bindings_off_work']==14000369
    baseline=json.loads(gzip.decompress((ROOT/'reports/bound-values-v3/result.json.gz').read_bytes()))
    byid={c['id']:c for c in baseline['cases']}
    ordinary=[]
    for c in result['cases']:
        if c['group']=='current-model'and c['id']!='payload-capacity':
            assert c['measurement']['report']['semantic']==byid[c['id']]['native_reports'][2]['semantic'];ordinary.append(c['id'])
    protected=json.loads((m.BASE/'protected-before.json').read_text(encoding='utf-8'));assert protected==m.b.protected()
    derivation=json.loads((m.BASE/'derivation.json').read_text(encoding='utf-8'))
    for p,h in derivation['frozen_real_files'].items():assert m.old.digest(ROOT/p)==h
    archives=[];cleanup=[]
    # These two files contain every parsed report, diagnostic, memory sample and
    # raw-output hash. Verify byte-preserving compression before consolidation.
    for name in ['result.json','cpu-comparison.json']:
        p=OUT/name;data=p.read_bytes();packed=p.with_name(p.name+'.gz');assert not packed.exists();packed.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(packed.read_bytes())==data
        archives.append(dict(path=packed.relative_to(ROOT).as_posix(),sha256=m.old.digest(packed),raw_sha256=m.old.digest(p),raw_bytes=len(data),bytes=packed.stat().st_size))
    def remove_duplicate(path,basis):
        assert path.is_file()and not path.is_symlink()and path.resolve().is_relative_to(OUT.resolve())
        cleanup.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=m.old.digest(path),basis=basis));path.unlink()
    items=[label for c in result['cases']for label in [c['measurement'],c['formal_control']]if label is not None]+[comparison['control']]
    for item in items:
        for a in item['archives']:
            p=OUT/a['path'];assert m.old.digest(p)==a['sha256'];raw=gzip.decompress(p.read_bytes());assert hashlib.sha256(raw).hexdigest()==a['raw_sha256']
            if '.json.'in p.name:
                equal=json.loads(raw)==item['report']if raw.strip()else item['report']is None
            else:equal=raw.decode('utf-8',errors='replace')==item['stderr_tail']
            if equal:remove_duplicate(p,'complete parsed stdout/exact stderr is retained in consolidated result or CPU comparison; original raw SHA256 retained there')
    for c in result['cases']:
        p=OUT/(c['id']+'-summary.json');row=json.loads(p.read_text(encoding='utf-8'))
        assert row['id']==c['id']and row['measurement']=={k:v for k,v in c['measurement'].items()if k!='report'}
        remove_duplicate(p,'identical case summary retained in consolidated result')
    for name in ['result.json','cpu-comparison.json']:remove_duplicate(OUT/name,'full bytes retained in checked gzip archive')
    build=m.BASE.resolve();assert build==Path('D:/Coding/ISAAC/authority/build-bound-measurement').resolve()
    for p in build.rglob('*'):
        regenerate=p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk','.idb']or(p.suffix=='.pdb'and any(n.endswith('.dir')for n in p.parts))
        if p.is_file()and regenerate:
            assert not p.is_symlink()and p.resolve().is_relative_to(build)
            cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=m.old.digest(p),basis='regenerable intermediate in this measurement build only'));p.unlink()
    assert protected==m.b.protected()
    inputs=[Path(m.__file__),Path(__file__),ROOT/'docs/BOUNDARY_UNCAPPED_20261016.md',m.MANIFEST,m.BASE/'formal-control.json',m.BASE/'measurement-cpu-control.json',m.BASE/'derivation.json',m.BASE/'protected-before.json']+list(m.GEN.iterdir())
    seal=dict(schema='uncapped-boundary-measurement-final-1',measurement_only=True,formal_gate_changed=False,work_quota=None,wall_clock_timeout_seconds=None,private_memory_quota=None,record_caps=None,full_trace_enabled=False,expression_verifier_run=False,game_started=False,formal_files_unchanged=True,save_files_unchanged=True,frozen_sources_unchanged=True,ordinary_model_comparisons=len(ordinary),native_execution_cases_completed=26,native_execution_cases_total=29,real_mod_initialization_completed=False,cpu_observer_comparison={k:v for k,v in comparison.items()if k!='control'},archives=archives,cleanup=cleanup,cleanup_bytes=sum(x['bytes']for x in cleanup),binary_sha256=m.old.digest(m.EXE),binaries={p.relative_to(ROOT).as_posix():m.old.digest(p)for p in(m.BASE/'Release').iterdir()if p.suffix in ['.exe','.pdb']},inputs={p.relative_to(ROOT).as_posix():m.old.digest(p)for p in inputs if p.is_file()})
    m.old.save(OUT/'final.json',seal)
    print(json.dumps(dict(finalized=True,ordinary_equal=len(ordinary),retained_report_bytes=sum(a['bytes']for a in archives),removed_duplicate_and_intermediate_bytes=seal['cleanup_bytes'],formal_unchanged=True)))
if __name__=='__main__':main()
