"""Verify the SDK model artifacts and preserve failed real initialization."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_mod_sdk as s
import verify_model_objects

def archived(p):return json.loads(gzip.decompress(p.read_bytes()))
def main():
    verify_model_objects.main();root=s.ROOT;final=s.o.load(root/'reports/mod-sdk-final.json')
    assert final['model_contracts_passed']and not final['gate_passed']and not final['real_mod_initialization_passed']and not final['authority_projection_passed']
    for group in ['inputs','binaries','frozen_files']:
        for name,h in final[group].items():assert s.old.digest(root/name)==h,'SDK artifact differs: '+name
    d=s.o.load(root/'build-mod-sdk/generated/derived_sha256.json')
    assert s.old.digest(root/'reports/model-objects-final.json')==d['prior_final_sha256']
    for name,v in d['derived'].items():assert s.old.digest(root/'build-mod-sdk/generated'/name)==v['sha256']and s.old.digest(root/v['source'])==v['source_sha256']
    assert s.old.digest(root/'build-read-set/Release/read_lua.lib')==d['lua_sha256']and s.old.digest(root/'build-boundary/Release/boundary_lua.lib')==d['stock_lua_sha256']
    for a in final['archives']:
        p=root/a['path'];raw=gzip.decompress(p.read_bytes());assert s.old.digest(p)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    for name,count in [('mod-sdk-v5',35),('mod-sdk-core-v2',153),('mod-sdk-objects-v2',37),('mod-sdk-modules-v2',41),('mod-sdk-gc-v2',4)]:
        r=archived(root/'reports'/name/'result.json.gz');assert r['passed']and len(r['cases'])==count
        assert r['work_limit']==10000000 and r['child_timeout_seconds']==5
    current=archived(root/'reports/mod-sdk-v5/result.json.gz');assert all(all(t['passed']for t in c['checks'])for c in current['cases'])
    c=next(c for c in current['cases']if c['id']=='full-frozen-enum-bytes');raw=bytes.fromhex(c['reports'][1]['steps'][0]['values'][0]['hex']);assert len(raw)==158508 and hashlib.sha256(raw).hexdigest()=='ee28c5634b77b7294240030368101e517f57520d58e48a44ba0125fd06b167b7'
    repaired=archived(root/'reports/mod-sdk-userdata-repair-v1/result.json.gz');assert repaired['passed']and len(repaired['attempts'])==24 and all(x['artifact']['returncode']==0 for x in repaired['attempts'])
    diagnostic=archived(root/'reports/mod-sdk-userdata-diagnostic-v1/result.json.gz');assert 'FILE*' in diagnostic['attempts'][-1]['report']['first_unsupported_entry']
    real=archived(root/'reports/mod-sdk-real-v2/result.json.gz');assert not real['passed']and len(real['cases'])==3 and all('Vector'in c['reports'][1]['first_unsupported_entry']for c in real['cases'])
    source=(root/'build-mod-sdk/generated/boundary.cpp').read_text(encoding='utf-8');assert 'luaL_openlibs(L)'not in source and 'luaopen_io'not in source and 'open_research_libraries(L)'in source
    print(json.dumps(dict(artifact_integrity_verified=True,abi='ia-lua533-mod-sdk-1',sdk_model_cases=35,old_classified_regressions=235,late_module_repeats=24,real_mod_initialization_passed=False,authority_projection_passed=False,game_started=False,cleanup_bytes=final['cleanup_bytes'])))
if __name__=='__main__':main()
