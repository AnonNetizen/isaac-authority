"""Read-only verification of bounded services and their incomplete real gate."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_engine_services as e
import verify_value_objects
def archived(p):return json.loads(gzip.decompress(p.read_bytes()))
def main():
    verify_value_objects.main();root=e.ROOT;final=e.v.s.o.load(root/'reports/engine-services-final.json')
    assert final['model_contracts_passed'] and not final['gate_passed'] and not final['real_mod_initialization_passed'] and not final['authority_projection_passed']
    for group in ['inputs','binaries','frozen_files']:
        for name,h in final[group].items():assert e.old.digest(root/name)==h,'Service artifact differs: '+name
    d=e.v.s.o.load(root/'build-engine-services/generated/derived_sha256.json')
    assert d['abi']=='ia-lua533-engine-services-2' and e.old.digest(root/'reports/value-objects-final.json')==d['prior_final_sha256']
    for name,x in d['derived'].items():assert e.old.digest(root/'build-engine-services/generated'/name)==x['sha256']and e.old.digest(root/x['source'])==x['source_sha256']
    assert e.old.digest(root/'build-read-set/Release/read_lua.lib')==d['lua_sha256']and e.old.digest(root/'build-boundary/Release/boundary_lua.lib')==d['stock_lua_sha256']
    for a in final['archives']:
        p=root/a['path'];raw=gzip.decompress(p.read_bytes());assert e.old.digest(p)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    for folder in ['engine-services-v2','engine-services-values-v2']:
        old=archived(root/'reports'/folder/'result.json.gz')
        for name in ['authority-services.exe','authority-services-reference.exe']:
            raw=gzip.decompress((root/'reports'/folder/(name+'.gz')).read_bytes())
            assert hashlib.sha256(raw).hexdigest()==old['binaries']['build-engine-services/Release/'+name]
    for name,count in [('engine-services-v4',32),('engine-services-core-v3',153),('engine-services-values-v3',40),('engine-services-sdk-v3',35),('engine-services-objects-v3',37),('engine-services-modules-v3',41),('engine-services-gc-v3',4)]:
        r=archived(root/'reports'/name/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['work_limit']==10000000 and r['child_timeout_seconds']==5
        hashes=r.get('binaries',{});assert (r.get('binary_sha256')or hashes.get(e.EXE.relative_to(root).as_posix()))==e.old.digest(e.EXE)
    data=e.v.s.o.load(e.CATALOG);assert data['coverage']=='partial' and len(data['items'])==4
    for x in data['evidence']:assert e.old.digest(root/x['path'])==x['sha256']
    assert data['items'][0]['fields']==dict(ID=1,Name='#THE_SAD_ONION_NAME',Quality=3)
    real=archived(root/'reports/engine-services-real-v3/result.json.gz');assert not real['passed']and len(real['cases'])==3
    for c in real['cases']:
        p=c['reports'][1];assert p['abi']==d['abi']and not p['completed']and p['engine_services']['coverage']=='partial'
        if c['id']=='eid':assert 'Unregistered Sprite resource: gfx/005.100_collectible.anm2'in p['first_unsupported_entry']
        else:
            assert 'Sprite.SetFrame contract not implemented'in p['first_unsupported_entry']
            assert bytes.fromhex(p['engine_services']['last_log_attempt']['text_hex'])==b'Loading Mod Config Menu Chinese v10034'
    initial=archived(root/'reports/engine-services-v1/result.json.gz');assert not initial['passed']and initial['cases'][-1]['reports'][1]['steps'][0]['values']==[{'type':'integer','value':0}]
    failed=archived(root/'reports/engine-services-values-v2/result.json.gz');c=next(c for c in failed['cases']if c['id']=='mixed-userdata-gc-shadow');assert not c['passed']and c['reports'][1]['semantic']==c['reports'][2]['semantic']
    repaired=archived(root/'reports/engine-services-repeat-repair-v1/result.json.gz');assert repaired['passed']and len(repaired['attempts'])==12
    for a in repaired['attempts']:
        p=a['report'];state=p['steps'][1]['metadata'];assert 'weak_checks'not in state and 'peak'not in state and p['metadata'][1]['value_objects']['weak_checks']>0
    code=(root/'engine_services_runtime/context_services.inc').read_text(encoding='utf-8');assert code.index('if(length>10219)')<code.index('std::string message(raw,length)')
    print(json.dumps(dict(artifact_integrity_verified=True,abi=d['abi'],new_classified_checks=32,old_classified_regressions=310,real_mod_initialization_passed=False,authority_projection_passed=False,game_started=False)))
if __name__=='__main__':main()
