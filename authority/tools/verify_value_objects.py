"""Read-only artifact verification; never launches a model or the game."""
import gzip, hashlib, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_value_objects as v
import verify_mod_sdk

def main():
    verify_mod_sdk.main();root=v.ROOT;final=v.s.o.load(root/'reports/value-objects-final.json')
    assert final['model_contracts_passed'] and not final['gate_passed']
    assert not final['real_mod_initialization_passed'] and not final['authority_projection_passed']
    for group in ['inputs','binaries','frozen_files']:
        for name,h in final[group].items():assert v.old.digest(root/name)==h,'Value artifact differs: '+name
    d=v.s.o.load(root/'build-value-objects/generated/derived_sha256.json')
    assert v.old.digest(root/'reports/mod-sdk-final.json')==d['prior_final_sha256']
    for name,x in d['derived'].items():
        assert v.old.digest(root/'build-value-objects/generated'/name)==x['sha256']
        assert v.old.digest(root/x['source'])==x['source_sha256']
    assert v.old.digest(root/'build-read-set/Release/read_lua.lib')==d['lua_sha256']
    assert v.old.digest(root/'build-boundary/Release/boundary_lua.lib')==d['stock_lua_sha256']
    for a in final['archives']:
        p=root/a['path'];raw=gzip.decompress(p.read_bytes())
        assert v.old.digest(p)==a['sha256'] and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    for name,count in [('value-objects-v2',40),('value-objects-core-v2',153),('value-objects-old-objects-v2',37),('value-objects-modules-v2',41),('value-objects-gc-v2',4),('value-objects-sdk-v2',35)]:
        r=json.loads(gzip.decompress((root/'reports'/name/'result.json.gz').read_bytes()))
        assert r['passed'] and len(r['cases'])==count and r['work_limit']==10000000 and r['child_timeout_seconds']==5
    real=json.loads(gzip.decompress((root/'reports/value-objects-real-v2/result.json.gz').read_bytes()))
    assert not real['passed'] and len(real['cases'])==3
    for c in real['cases']:
        assert ('GetItemConfig' if c['id']=='eid' else 'DebugString') in c['reports'][1]['first_unsupported_entry']
    print(json.dumps(dict(artifact_integrity_verified=True,abi=final['abi'],model_classified_checks=40,old_classified_regressions=270,real_mod_initialization_passed=False,authority_projection_passed=False,game_started=False)))
if __name__=='__main__':main()
