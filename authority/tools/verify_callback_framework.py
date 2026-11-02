"""Read-only proof of source-backed callback behavior and the still-failed UI gate."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_callback_framework as f
import verify_texture_state

def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def results():
    root=f.ROOT;binary=f.old.digest(f.EXE);runs=[]
    for name,count,path in [('callback-framework-v3',44,f.CURRENT),('callback-framework-repeat-v3',44,f.CURRENT),('callback-framework-textures-v2',45,f.t.CURRENT),('callback-framework-sdk-v3',35,f.t.s.e.v.s.CURRENT)]:
        r=archived(root/'reports'/name/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['manifest_sha256']==f.old.digest(path)
        assert r['binaries'][f.EXE.relative_to(root).as_posix()]==binary and r['work_limit']==10000000 and r['child_timeout_seconds']==5 and r['protected_files_unchanged']and r['save_files_unchanged']
        assert [c['id']for c in r['cases']]==[c['id']for c in f.t.s.e.v.s.o.load(path)['cases']]
        for c in r['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                assert a['seconds']<5 and a['returncode']!=-9 and p is not None and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and not p['full_trace_enabled']and not p['game_started']
                if'semantic'in p:
                    assert p['private_commit_bytes']<1024**3 and not p['automatic_projection_implemented']and not p['personal_draws_publishable']
                    if path==f.CURRENT:assert not p['consumer_read_sets_implemented']and all(m['callback_framework']['source_unmodified']and not m['callback_framework']['consumer_capture_supported']and m['callback_framework']['depth']==0 for m in p['metadata'])
        runs.append(r)
    for a,b in zip(runs[0]['cases'],runs[1]['cases']):
        for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    refusal=next(c for c in runs[0]['cases']if c['id']=='reject-nested-hook-budget')
    assert all('Boundary work limit exceeded'in p['first_unsupported_entry']for p in refusal['reports'])
    real=archived(root/'reports/callback-framework-real-v2/result.json.gz');assert not real['passed']and len(real['cases'])==3
    for c in real['cases']:
        for a,p in zip(c['artifacts'],c['reports']):
            assert a['seconds']<5 and p is not None and not p['completed']and not p['game_started']and "global 'Font'"in p['first_unsupported_entry']and p['budget']['used']<10000000
            source=p['first_unsupported_entry'].replace('\\','/')
            if c['id']=='eid':assert'main.lua:165:'in source and p['modules']['states'][0]['compilations']==115
            else:assert'modconfig.lua:528:'in source
    return dict(new_classified_checks=44,functional_cases=30,expected_rejection_cases=14,repeated_outputs_equal=True,old_classified_regressions=80,real_mod_initialization_passed=False,authority_projection_passed=False,framework_consumer_capture_supported=False,game_started=False)

def main():
    verify_texture_state.main();root=f.ROOT;final=f.t.s.e.v.s.o.load(root/'reports/callback-framework-final.json')
    assert final['model_contracts_passed']and not final['gate_passed']and not final['real_mod_initialization_passed']and not final['authority_projection_passed']
    for group in ['inputs','binaries']:
        for name,h in final[group].items():assert f.old.digest(root/name)==h,'Callback artifact differs: '+name
    for a in final['archives']:
        raw=gzip.decompress((root/a['path']).read_bytes());assert f.old.digest(root/a['path'])==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    derived=f.t.s.e.v.s.o.load(root/'build-callback-framework/generated/derived_sha256.json')
    assert derived['abi']=='ia-lua533-callback-framework-1'and derived['prior_final_sha256']==f.old.digest(root/'reports/texture-state-final.json')
    for name,d in derived['derived'].items():assert f.old.digest(root/'build-callback-framework/generated'/name)==d['sha256']and f.old.digest(root/d['source'])==d['source_sha256']
    assert f.old.digest(root/'build-read-set/Release/read_lua.lib')==derived['lua_sha256']and f.old.digest(root/'build-boundary/Release/boundary_lua.lib')==derived['stock_lua_sha256']
    p=f.t.s.e.v.s.o.load(f.PROFILE);data=(root/p['main_path']).read_bytes();assert hashlib.sha256(data).hexdigest()==p['main_sha256']and hashlib.sha256(b''.join(data.splitlines(keepends=True)[40:163])).hexdigest()==p['fragment_sha256']
    print(json.dumps(dict(artifact_integrity_verified=True,abi=derived['abi'],**results())))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--results-only',action='store_true');a=parser.parse_args()
    if a.results_only:print(json.dumps(results()))
    else:main()
