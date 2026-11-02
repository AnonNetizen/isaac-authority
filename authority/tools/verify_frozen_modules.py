"""Verify artifact integrity without relabeling the failed real-module gate."""
import gzip,hashlib,json,sys
sys.dont_write_bytecode=True
import run_frozen_modules as m
import verify_compact_values
ROOT=m.ROOT
def main():
    verify_compact_values.main();v=json.loads((ROOT/'reports/frozen-modules-final.json').read_text(encoding='utf-8'))
    assert not v['gate_passed']and v['contract_cases_reached_expectation']==40 and v['real_helper_functional_failures']==1 and not v['real_mod_initialization_passed']
    for group in ['inputs','binaries','frozen_files']:
        for p,h in v[group].items():assert m.old.digest(ROOT/p)==h,'Module artifact differs: '+p
    d=json.loads((ROOT/'build-frozen-module/generated/derived_sha256.json').read_text(encoding='utf-8'))
    assert m.old.digest(ROOT/'reports/compact-values-final.json')==d['prior_final_sha256']
    assert m.old.digest(ROOT/'build-read-set/Release/read_lua.lib')==d['lua_sha256']
    assert m.old.digest(ROOT/'build-boundary/Release/boundary_lua.lib')==d['stock_lua_sha256']
    for name,entry in d['derived'].items():assert m.old.digest(ROOT/'build-frozen-module/generated'/name)==entry['sha256']and m.old.digest(ROOT/entry['source'])==entry['source_sha256']
    for a in v['archives']:
        raw=(ROOT/a['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==a['sha256'];assert hashlib.sha256(gzip.decompress(raw)).hexdigest()==a['raw_sha256']
    print(json.dumps(dict(artifact_integrity_verified=True,abi='ia-lua533-frozen-modules-1',gate_passed=False,functional_model_cases=32,expected_recovery_or_rejection_cases=8,real_helper_functional_failures=1,old_regressions=153,real_mod_initialization_passed=False,authority_projection_passed=False)))
if __name__=='__main__':main()
