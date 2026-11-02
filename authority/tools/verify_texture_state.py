"""Read-only identity, repetition, resource and explicitly failed UI gate checks."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_texture_state as t
import verify_sprite_state
import freeze_texture_state

def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def main():
    verify_sprite_state.main();root=t.ROOT;final=t.s.e.v.s.o.load(root/'reports/texture-state-final.json')
    assert final['model_contracts_passed']and not final['gate_passed']and not final['real_mod_initialization_passed']and not final['authority_projection_passed']
    for group in ['inputs','binaries']:
        for name,h in final[group].items():assert t.old.digest(root/name)==h,'Texture artifact differs: '+name
    for a in final['archives']:
        path=root/a['path'];raw=gzip.decompress(path.read_bytes());assert t.old.digest(path)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    derived=t.s.e.v.s.o.load(root/'build-texture-state/generated/derived_sha256.json')
    assert derived['abi']=='ia-lua533-texture-state-1'and derived['prior_final_sha256']==t.old.digest(root/'reports/sprite-state-final-v2.json')
    for name,row in derived['derived'].items():assert t.old.digest(root/'build-texture-state/generated'/name)==row['sha256']and t.old.digest(root/row['source'])==row['source_sha256']
    assert t.old.digest(root/'build-read-set/Release/read_lua.lib')==derived['lua_sha256']and t.old.digest(root/'build-boundary/Release/boundary_lua.lib')==derived['stock_lua_sha256']
    current=t.old.digest(t.EXE);runs=[]
    for name,count in [('texture-state-v2',45),('texture-state-repeat-v2',45),('texture-state-sprites-v2',41)]:
        result=archived(root/'reports'/name/'result.json.gz');assert result['passed']and len(result['cases'])==count and result['work_limit']==10000000 and result['child_timeout_seconds']==5
        assert result['binaries'][t.EXE.relative_to(root).as_posix()]==current
        for c in result['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                assert a['seconds']<5 and a['returncode']!=-9 and p is not None and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())
                assert not p['game_started']and not p['full_trace_enabled']
                if 'semantic'in p:assert p['private_commit_bytes']<1024**3 and not p['automatic_projection_implemented']and not p['personal_draws_publishable']
        runs.append(result)
    assert [c['id']for c in runs[0]['cases']]==[c['id']for c in runs[1]['cases']]
    for a,b in zip(runs[0]['cases'],runs[1]['cases']):
        for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    profile=t.s.e.v.s.o.load(t.PROFILE);assert len(profile['images'])==19 and len(profile['sprites'])==7 and sum(len(s['layers'])for s in profile['sprites'])==26
    for e in profile['evidence']:assert t.old.digest(root/e['path'])==e['sha256']
    freeze_texture_state.freeze() # Rebuild only metadata in memory and compare exact frozen bytes.
    real=archived(root/'reports/texture-state-real-v2/result.json.gz');assert not real['passed']and len(real['cases'])==3
    for c in real['cases']:
        for a,p in zip(c['artifacts'],c['reports']):
            assert a['seconds']<5 and p is not None and not p['completed']and not p['game_started']and not p['texture_state']['pixels_rendered']and not p['texture_state']['native_return_equivalence_verified']
            assert p['budget']['used']<10000000
            if c['id']=='eid':
                assert p['first_unsupported_entry']=='Expected integer';w=p['texture_state']['first_failure']
                assert any(x.get('bytes_hex')=='EIDCallbacks.SEARCH_NAME_CONVERSION'.encode().hex()and x['index']==2 for x in w['arguments'])
                assert any(bytes.fromhex(f['source_hex']).decode('utf-8').replace('\\','/').endswith('/features/eid_bagofcrafting_search.lua')and f['line']==58 for f in w['frames'])
                assert p['modules']['states'][0]['compilations']==114 and p['sprite_state']['range_bytes_verified']==321063 and p['texture_state']['loose_bytes_verified']==136685
            else:assert "global 'Font'"in p['first_unsupported_entry']
    print(json.dumps(dict(artifact_integrity_verified=True,abi=derived['abi'],new_classified_checks=45,repeated_outputs_equal=True,sprite_regressions=41,real_mod_initialization_passed=False,authority_projection_passed=False,native_return_equivalence_verified=False,game_started=False)))
if __name__=='__main__':main()
