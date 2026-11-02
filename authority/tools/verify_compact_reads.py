"""Read-only verification of the experimental continuation and sealed baseline."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_compact_reads as c
import run_boundary_handoff as old
ROOT=c.ROOT
def main():
    v=json.loads((ROOT/'reports/compact-read-final.json').read_text(encoding='utf-8'))
    assert v['compact_read_gate_passed']and not v['bindings_verified']and not v['automatic_projection_passed']
    for group in ['inputs','binaries']:
        for p,h in v[group].items():assert old.digest(ROOT/p)==h,'Sealed compact artifact differs: '+p
    derived=json.loads((ROOT/'build-compact-read/generated/derived_sha256.json').read_text())
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-compact-read/generated'/name)==h
    assert old.digest(ROOT/'build-read-set/Release/read_lua.lib')==derived['imported_lua_sha256']
    assert old.digest(ROOT/'reports/boundary-reads-final.json')==derived['read_candidate_final_sha256']
    assert hashlib.sha256(json.dumps(c.protected(),sort_keys=True,separators=(',',':')).encode()).hexdigest()==v['protected_inventory_sha256']
    for a in v['archives']:
        p=ROOT/a['path'];assert old.digest(p)==a['sha256'];assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()==a['original_sha256']
    print(json.dumps(dict(verified=True,abi='ia-lua533-compact-reads-1',compact_functional_cases=v['compact_functional_cases'],compact_safety_rejections=v['compact_safety_rejections'],old_regressions=v['old_regressions'],symbolic_template_cases=v['symbolic_template_cases'],unresolved_diagnostics=v['unresolved_template_diagnostics'],bindings_verified=False,consumer_cache_enabled=False,automatic_projection_passed=False)))
if __name__=='__main__':main()
