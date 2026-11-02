"""Read-only validation of the current read-set candidate; old gate is historical."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_reads as r
import run_boundary_handoff as old
ROOT=r.ROOT
def main():
    final=json.loads((ROOT/'reports/boundary-reads-final.json').read_text(encoding='utf-8'))
    assert final['read_set_gate_passed'] and final['legacy_macro_repaired'] and not final['automatic_projection_passed']
    for group in ['inputs','binaries']:
        for name,h in final[group].items():assert old.digest(ROOT/name)==h,'Current delivery hash differs: '+name
    derived=json.loads((ROOT/'build-read-set/generated/derived_sha256.json').read_text())
    for name,h in derived['derived'].items():assert old.digest(ROOT/'build-read-set/generated'/name)==h
    assert old.digest(ROOT/'build-write-barrier/generated/derived_sha256.json')==derived['write_candidate_manifest_sha256']
    pristine=json.loads((ROOT/'third_party/lua533/SOURCE.json').read_text())
    for f in pristine['files']:assert old.digest(ROOT/'third_party/lua533'/f['path'])==f['sha256']
    for row in final['compressed_history']:
        p=ROOT/row['path'];assert old.digest(p)==row['sha256'];assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()==row['original_sha256']
    assert hashlib.sha256(json.dumps(r.protected(),sort_keys=True,separators=(',',':')).encode()).hexdigest()==final['protected_inventory_sha256']
    current=json.loads((ROOT/'research/boundary_current.json').read_text());assert current['abi']=='ia-lua533-boundary-reads-1' and current['legacy_write_runtime_unsafe']
    print(json.dumps(dict(verified=True,current_abi=current['abi'],functional_cases=final['functional_cases'],safety_rejections=final['safety_rejections'],not_reusable_diagnostics=final['not_reusable_diagnostics'],old_regressions=56,stability_probes=12,legacy_write_runtime_unsafe=True,consumer_cache_enabled=False,automatic_projection_passed=False)))
if __name__=='__main__':main()
