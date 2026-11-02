"""Read-only verification of sprite state, resource witnesses and failed UI gate."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_sprite_state as s
import verify_engine_services
def archived(p):return json.loads(gzip.decompress(p.read_bytes()))
def main():
    verify_engine_services.main();root=s.ROOT;final=s.e.v.s.o.load(root/'reports/sprite-state-final-v2.json')
    assert final['model_contracts_passed']and not final['gate_passed']and not final['real_mod_initialization_passed']and not final['authority_projection_passed']
    for group in ['inputs','binaries','frozen_files']:
        for name,h in final[group].items():assert s.old.digest(root/name)==h,'Sprite artifact differs: '+name
    d=s.e.v.s.o.load(root/'build-sprite-state/generated/derived_sha256.json')
    assert d['abi']=='ia-lua533-sprite-state-1'and s.old.digest(root/'reports/engine-services-final.json')==d['prior_final_sha256']
    for name,x in d['derived'].items():assert s.old.digest(root/'build-sprite-state/generated'/name)==x['sha256']and s.old.digest(root/x['source'])==x['source_sha256']
    assert s.old.digest(root/'build-read-set/Release/read_lua.lib')==d['lua_sha256']and s.old.digest(root/'build-boundary/Release/boundary_lua.lib')==d['stock_lua_sha256']
    for a in final['archives']:
        p=root/a['path'];raw=gzip.decompress(p.read_bytes());assert s.old.digest(p)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    for name,count in [('sprite-state-v2',41),('sprite-state-core-v6',153),('sprite-state-services-v2',32),('sprite-state-values-v2',40),('sprite-state-sdk-v2',35),('sprite-state-objects-v2',37),('sprite-state-modules-v2',41),('sprite-state-gc-v2',4)]:
        r=archived(root/'reports'/name/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['work_limit']==10000000 and r['child_timeout_seconds']==5
        assert (r.get('binary_sha256')or r['binaries'][s.EXE.relative_to(root).as_posix()])==s.old.digest(s.EXE)
    core=archived(root/'reports/sprite-state-core-v6/result.json.gz');assert core['ordered_case_coverage_verified']and core['preflight_shared']and core['protected_files_unchanged']and all(g['passed']and g['seconds']<60 for g in core['groups'])
    assert core['worker_timeout_seconds']==5 and core['worker_memory_limit_bytes']==1024**3 and all(a['seconds']<5 for a in core['analyses'])
    # This frozen negative case must fail analysis; every other analysis must succeed.
    rejected=[a for a in core['analyses']if a['returncode']!=0]
    assert len(rejected)==1 and rejected[0]['returncode']==1 and rejected[0]['stderr'].strip().endswith('RuntimeError: Draw recipe global node capacity exceeded')
    refusal=next(c for c in core['cases']if c['suite']=='draw-plans'and c['id']=='global-node-limit')
    assert refusal['passed']and next(t['passed']for t in refusal['checks']if t['check']=='analysis-capacity-rejection')
    proof=archived(root/'reports/sprite-state-verification-v2/analysis-rejection.json.gz')
    assert proof['passed']and proof['id']==refusal['id']and proof['binary_sha256']==s.old.digest(s.EXE)and proof['worker_sha256']==s.old.digest(root/'tools/sprite_core_worker.py')
    manifest=s.e.v.s.o.load(root/proof['manifest']);case=next(c for c in manifest['cases']if c['id']==proof['id'])
    assert s.old.digest(root/proof['manifest'])==proof['manifest_sha256']and case['check']=='analysis-rejected'and proof['expected_error']=='RuntimeError: Draw recipe '+case['reason']
    assert hashlib.sha256(json.dumps(proof['request'],sort_keys=True,separators=(',',':')).encode()).hexdigest()==proof['request_sha256']
    assert proof['artifact']['returncode']==0 and proof['artifact']['seconds']<5 and proof['analysis']['returncode']==1 and proof['analysis']['seconds']<5 and proof['analysis']['stderr'].strip().endswith(proof['expected_error'])
    assert proof['work_limit']==10000000 and proof['worker_timeout_seconds']==5 and proof['worker_memory_limit_bytes']==1024**3
    profile=s.e.v.s.o.load(s.PROFILE);assert len(profile['sprites'])==7 and sum(len(x['animations'])for x in profile['sprites'])==81
    for e in profile['evidence']:assert s.old.digest(root/e['path'])==e['sha256']
    game=Path(profile['game_root']);checked={}
    for asset in profile['sprites']:
        for p in asset['range_proofs']:
            for r in p['ranges']:
                key=(p['path'],r['offset'],r['bytes']);assert r['bytes']<=4*1024**2
                if key in checked:assert checked[key]==r['sha256'];continue
                with (game/p['path']).open('rb')as f:f.seek(r['offset']);data=f.read(r['bytes'])
                assert len(data)==r['bytes']and hashlib.sha256(data).hexdigest()==r['sha256'];checked[key]=r['sha256']
    model=archived(root/'reports/sprite-state-v2/result.json.gz');c=next(c for c in model['cases']if c['id']=='requested-frame-preserved');state=c['reports'][1]['semantic']['sprite_states'][1][0];assert state['requested_frame']==4 and state['root_frame']==0 and state['commands'][-1]['requested']==4
    native=archived(root/'reports/sprite-state-real-v2/result.json.gz');assert not native['passed']and len(native['cases'])==3
    for c in native['cases']:
        p=c['reports'][1];assert not p['completed']and not p['sprite_state']['rendering_verified']
        if c['id']=='eid':assert 'Sprite.ReplaceSpritesheet contract not implemented'in p['first_unsupported_entry']and p['sprite_state']['range_bytes_verified']==275949 and p['sprite_state']['read_pins_held']==2
        else:assert "global 'Font'"in p['first_unsupported_entry']
    print(json.dumps(dict(artifact_integrity_verified=True,abi=d['abi'],new_classified_checks=41,native_animation_controls=81,old_classified_regressions=342,real_mod_initialization_passed=False,authority_projection_passed=False,game_started=False)))
if __name__=='__main__':main()
