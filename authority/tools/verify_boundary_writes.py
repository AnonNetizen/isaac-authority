"""Read-only validation; does not build, run Lua, launch the game or touch saves."""
import gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_writes as w
import run_boundary_handoff as old
ROOT=w.ROOT
def main():
    p=ROOT/'reports/boundary-writes-final.json';r=json.loads(p.read_text(encoding='utf-8'));assert r['write_barrier_gate_passed']
    for group in ['inputs','binaries','imported_libraries']:
        for name,h in r[group].items():assert old.digest(ROOT/name)==h,'Delivery hash differs: '+name
    derived=json.loads((ROOT/'build-write-barrier/generated/derived_sha256.json').read_text())
    assert old.digest(ROOT/'boundary_runtime/boundary.cpp')==derived['baseline_sha256']
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-write-barrier/generated'/name)==h,'Derived source differs: '+name
    pristine=json.loads((ROOT/'third_party/lua533/SOURCE.json').read_text())
    assert old.digest(ROOT/'third_party/lua533/SOURCE.json')==derived['pristine_manifest_sha256']
    for f in pristine['files']:assert old.digest(ROOT/'third_party/lua533'/f['path'])==f['sha256']
    for prior in r['historical_reports']:
        p=ROOT/prior['path'];assert old.digest(p)==prior['sha256']
        import hashlib
        assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()==prior['original_sha256']
    w.protected()
    print(json.dumps(dict(verified=True,functional_cases=r['functional_cases'],safety_rejections=r['safety_rejection_cases'],old_regressions=r['old_regressions'],work_limit=r['work_limit'],child_timeout_seconds=r['child_timeout_seconds'],consumer_read_sets_implemented=False,automatic_projection_passed=False)))
if __name__=='__main__':main()
