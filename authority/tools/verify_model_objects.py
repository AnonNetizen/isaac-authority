"""Verify the optional object candidate without promoting its real-mod gate."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_model_objects as o
import verify_frozen_modules

def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def main():
    verify_frozen_modules.main();root=o.ROOT;final=o.load(root/'reports/model-objects-final.json')
    assert final['model_contracts_passed']and not final['gate_passed']and not final['real_mod_initialization_passed']and not final['authority_projection_passed']
    for group in ['inputs','binaries','frozen_files']:
        for name,h in final[group].items():assert o.old.digest(root/name)==h,'Object artifact differs: '+name
    derived=o.load(root/'build-model-objects/generated/derived_sha256.json')
    assert o.old.digest(root/'reports/frozen-modules-final.json')==derived['prior_final_sha256']
    assert o.old.digest(root/'build-read-set/Release/read_lua.lib')==derived['lua_sha256']
    assert o.old.digest(root/'build-boundary/Release/boundary_lua.lib')==derived['stock_lua_sha256']
    for name,v in derived['derived'].items():assert o.old.digest(root/'build-model-objects/generated'/name)==v['sha256']and o.old.digest(root/v['source'])==v['source_sha256']
    assert o.resource_catalog()==o.load(o.CATALOG)
    for a in final['archives']:
        p=root/a['path'];raw=gzip.decompress(p.read_bytes());assert o.old.digest(p)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    for label,count in [('model-objects-v3',37),('model-objects-gc-v2',4),('model-objects-modules-v2',41),('model-objects-regressions-v1',153)]:
        r=archived(root/'reports'/label/'result.json.gz');assert r['passed']and len(r['cases'])==count
        assert r['work_limit']==10000000 and r['child_timeout_seconds']==5
    r=archived(root/'reports/model-objects-v3/result.json.gz');cases={c['id']:c for c in r['cases']}
    for c in r['cases']:assert all(t['passed']for t in c['checks'])
    churn=cases['bounded-gc-churn']['reports'][1]['metadata'][1]['model_objects'];assert churn['live']==3 and churn['created']==4099 and churn['retired']==4096 and churn['peak']==36
    assert all(a['returncode']==1 and a['seconds']<5 for a in cases['reject-object-work-budget']['artifacts'])
    old=archived(root/'reports/model-objects-v1/result.json.gz');assert not old['passed']and old['cases'][-1]['id']=='reject-object-work-budget'
    assert all(a['returncode']==-9 for a in old['cases'][-1]['artifacts'])
    assert hashlib.sha256(gzip.decompress((root/'reports/model-objects-v1/driver.py.gz').read_bytes())).hexdigest()==old['driver_sha256']
    real=archived(root/'reports/model-objects-real-v1/result.json.gz');assert not real['passed']and len(real['cases'])==3
    assert 'Multiple mods' in real['cases'][0]['reports'][1]['first_unsupported_entry']and 'Keyboard' in real['cases'][1]['reports'][1]['first_unsupported_entry']
    print(json.dumps(dict(artifact_integrity_verified=True,abi='ia-lua533-model-objects-1',model_contracts=37,collector_contracts=4,module_contracts=41,old_regressions=153,real_mod_initialization_passed=False,authority_projection_passed=False,game_started=False,cleanup_bytes=final['cleanup_bytes'])))
if __name__=='__main__':main()
