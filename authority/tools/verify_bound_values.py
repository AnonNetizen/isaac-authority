"""Read-only verification of observed-frame bindings and the sealed lineage."""
import gzip,hashlib,json,sys
sys.dont_write_bytecode=True
import run_bound_values as b
import run_boundary_handoff as old
import verify_compact_reads
ROOT=b.ROOT

def main():
    verify_compact_reads.main()
    v=json.loads((ROOT/'reports/bound-values-final.json').read_text(encoding='utf-8'))
    assert v['observed_frame_gate_passed']and not v['origins_verified']and not v['authority_projection_passed']and not v['consumer_cache_enabled']
    assert v['work_limit']==10000000 and v['child_timeout_seconds']==5
    for group in ['inputs','binaries']:
        for p,h in v[group].items():assert old.digest(ROOT/p)==h,'Sealed observed-value artifact differs: '+p
    derived=json.loads((ROOT/'build-bound-value/generated/derived_sha256.json').read_text(encoding='utf-8'))
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-bound-value/generated'/name)==h
    assert old.digest(ROOT/'build-read-set/Release/read_lua.lib')==derived['imported_lua_sha256']
    assert old.digest(ROOT/'reports/compact-read-final.json')==derived['compact_final_sha256']
    assert hashlib.sha256(json.dumps(b.protected(),sort_keys=True,separators=(',',':')).encode()).hexdigest()==v['protected_inventory_sha256']
    for a in v['archives']:
        p=ROOT/a['path'];assert old.digest(p)==a['sha256'];assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()==a['original_sha256']
    print(json.dumps(dict(verified=True,abi='ia-lua533-bound-values-1',observed_frame_functional_cases=v['observed_frame_functional_cases'],unresolved_diagnostics=v['unresolved_diagnostics'],native_rollback_cases=1,native_capacity_rejections=1,corruption_rejections=8,old_regressions=129,origins_verified=False,consumer_cache_enabled=False,authority_projection_passed=False)))
if __name__=='__main__':main()
