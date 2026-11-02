"""Seal the partial module candidate; preserve the real functional failures."""
import gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_frozen_modules as m
ROOT=m.ROOT
def main():
    model=json.loads((ROOT/'reports/frozen-modules-v4/result.json').read_text(encoding='utf-8'));real=json.loads((ROOT/'reports/frozen-modules-real-v3/result.json').read_text(encoding='utf-8'));reg=json.loads((ROOT/'reports/module-regressions-v2/result.json').read_text(encoding='utf-8'))
    assert not model['passed']and len(model['cases'])==41 and sum(x['passed']for x in model['cases'])==40
    assert model['cases'][-1]['id']=='real-filepath-helper'and'Sprite'in model['cases'][-1]['reports'][1]['first_unsupported_entry']
    assert not real['passed']and len(real['cases'])==3 and not real['real_mod_initialization_passed']and all(x['diagnostic_agreement']for x in real['cases'])
    assert reg['passed']and len(reg['cases'])==153 and reg['binary_sha256']==m.old.digest(m.EXE)
    hashes={p.name:m.old.digest(p)for p in[m.EXE,m.REF]};assert model['binaries']==real['binaries']==hashes and model['driver_sha256']==real['driver_sha256']==m.old.digest(Path(m.__file__))
    assert model['protected_files_unchanged']and real['protected_files_unchanged']and model['save_files_unchanged']and real['save_files_unchanged']
    frozen={}
    for path in [m.MANIFEST,m.REAL]:
        for case in json.loads(path.read_text(encoding='utf-8'))['cases']:
            if case['kind']=='process-rejection':continue
            for root in case['modules']['roots']:
                for name,h in root['sha256'].items():p=ROOT/root['root']/name;assert m.old.digest(p)==h;frozen[p.relative_to(ROOT).as_posix()]=h
    before=m.protected();build=m.BASE.resolve();assert build==Path('D:/Coding/ISAAC/authority/build-frozen-module').resolve();binaries={p.relative_to(ROOT).as_posix():m.old.digest(p)for p in(build/'Release').iterdir()if p.suffix in ['.exe','.pdb','.lib']}
    archives=[];cleanup=[]
    folders=['frozen-modules-v1','frozen-modules-v2','frozen-modules-v3','frozen-modules-v4','frozen-modules-real-v1','frozen-modules-real-v2','frozen-modules-real-v3','module-regressions-v1','module-regressions-v2']
    for name in folders:
        for p in sorted((ROOT/'reports'/name).glob('*.json')):
            target=p.with_name(p.name+'.gz');assert not target.exists()and not p.is_symlink()and p.resolve().is_relative_to((ROOT/'reports').resolve());data=p.read_bytes();target.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(target.read_bytes())==data;archives.append(dict(path=target.relative_to(ROOT).as_posix(),sha256=m.old.digest(target),raw_sha256=m.old.digest(p),raw_bytes=len(data),bytes=target.stat().st_size));p.unlink()
    for p in build.rglob('*'):
        regenerate=p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk','.idb']or(p.suffix=='.pdb'and any(n.endswith('.dir')for n in p.parts))
        if p.is_file()and regenerate:
            assert not p.is_symlink()and p.resolve().is_relative_to(build);cleanup.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=m.old.digest(p),basis='regenerable frozen-module build intermediate'));p.unlink()
    assert before==m.protected()
    for p,h in binaries.items():assert m.old.digest(ROOT/p)==h
    candidate=dict(schema='frozen-module-candidate-1',abi='ia-lua533-frozen-modules-1',gate_passed=False,executable=m.EXE.relative_to(ROOT).as_posix(),executable_sha256=m.old.digest(m.EXE),reference=m.REF.relative_to(ROOT).as_posix(),reference_sha256=m.old.digest(m.REF),verifier='tools/verify_frozen_modules.py',suite=m.MANIFEST.relative_to(ROOT).as_posix(),real_suite=m.REAL.relative_to(ROOT).as_posix(),results='docs/FROZEN_MODULE_RESULTS.md',work_limit=10000000,child_timeout_seconds=5,real_helper_functional_failures=1,real_mod_initialization_passed=False,authority_projection_passed=False,consumer_cache_enabled=False,prior='research/compact_value_candidate_v1.json')
    m.old.save(ROOT/'research/frozen_module_candidate_v1.json',candidate);m.old.save(ROOT/'research/boundary_next.json',dict(schema='mutable-research-pointer-1',candidate='research/frozen_module_candidate_v1.json',gate_passed=False,note='Partial research: Sprite/Game interfaces missing. Previous compact-value baseline remains verified.'))
    inputs=[Path(m.__file__),Path(__file__),ROOT/'tools/run_module_regressions.py',ROOT/'tools/verify_frozen_modules.py',ROOT/'docs/FROZEN_MODULE_PLAN.md',ROOT/'docs/FROZEN_MODULE_RESULTS.md',m.MANIFEST,m.REAL,ROOT/'research/frozen_modules_v1.json',ROOT/'research/frozen_modules_v2.json',ROOT/'research/frozen_module_candidate_v1.json',ROOT/'build-frozen-module/generated/derived_sha256.json']+list((ROOT/'module_runtime').iterdir())
    final=dict(schema='frozen-module-final-1',gate_passed=False,functional_model_cases=32,expected_recovery_or_rejection_cases=8,contract_cases_reached_expectation=40,contract_cases_total=41,real_helper_functional_failures=1,old_regressions=153,real_mod_initialization_passed=False,authority_projection_passed=False,consumer_cache_enabled=False,game_started=False,work_limit=10000000,child_timeout_seconds=5,protected_files_and_saves_unchanged=True,real_failure_records=[dict(id=x['id'],error=x['reports'][1]['first_unsupported_entry'],work=x['reports'][1]['budget']['used'],source_files=x['reports'][1]['modules']['source_files'],source_bytes=x['reports'][1]['modules']['source_bytes'])for x in real['cases']],archives=archives,cleanup=cleanup,cleanup_bytes=sum(x['bytes']for x in cleanup),frozen_files=frozen,binaries=binaries,inputs={p.relative_to(ROOT).as_posix():m.old.digest(p)for p in inputs if p.is_file()})
    m.old.save(ROOT/'reports/frozen-modules-final.json',final);print(json.dumps(dict(sealed_partial_candidate=True,gate_passed=False,cases_reached_expectation=40,real_helper_failures=1,old_regressions=153,cleanup_bytes=final['cleanup_bytes'])))
if __name__=='__main__':main()
