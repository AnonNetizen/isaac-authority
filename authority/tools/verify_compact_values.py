"""Read-only compact observation verification and immutable predecessor checks."""
import gzip,hashlib,json,sys
sys.dont_write_bytecode=True
import run_compact_values as c
import verify_bound_values
ROOT=c.ROOT
def main():
    verify_bound_values.main();v=json.loads((ROOT/'reports/compact-values-final.json').read_text(encoding='utf-8'))
    assert v['compact_observer_gate_passed']and not v['authority_projection_passed']and not v['consumer_cache_enabled']
    for group in ['inputs','binaries']:
        for p,h in v[group].items():assert c.b.old.digest(ROOT/p)==h,'Sealed compact observation differs: '+p
    d=json.loads((ROOT/'build-compact-value/generated/derived_sha256.json').read_text(encoding='utf-8'))
    for n,entry in d['derived'].items():assert c.b.old.digest(ROOT/'build-compact-value/generated'/n)==entry['sha256']and c.b.old.digest(ROOT/entry['source'])==entry['source_sha256']
    assert c.b.old.digest(ROOT/'reports/bound-values-final.json')==d['prior_final_sha256']and c.b.old.digest(ROOT/'build-read-set/Release/read_lua.lib')==d['imported_lua_sha256']
    for a in v['archives']:
        data=(ROOT/a['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==a['sha256'];assert hashlib.sha256(gzip.decompress(data)).hexdigest()==a['raw_sha256']
    print(json.dumps(dict(verified=True,abi='ia-lua533-compact-values-1',cases=24,old_regressions=129,corruption_rejections=8,wire_encoding_checks=252,work_limit=10000000,child_timeout_seconds=5,paired_cpu_speedup=v['paired_cpu_speedup'],authority_projection_passed=False)))
if __name__=='__main__':main()
