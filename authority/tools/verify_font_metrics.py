"""Verify finite font/query evidence and real initialization, keeping UI gates closed.""" 
import argparse,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_font_metrics as f
import verify_callback_framework

def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def results():
    root=f.ROOT;binary=f.old.digest(f.EXE);runs=[]
    for name,count,manifest in [('font-metrics-v2',64,f.CURRENT),('font-metrics-repeat-v2',64,f.CURRENT),('font-metrics-callbacks-v2',44,f.c.CURRENT),('font-metrics-real-v2',3,f.REAL),('font-metrics-real-repeat-v2',3,f.REAL)]:
        r=archived(root/'reports'/name/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['manifest_sha256']==f.old.digest(manifest)
        assert r['binaries'][f.EXE.relative_to(root).as_posix()]==binary and r['work_limit']==10000000 and r['child_timeout_seconds']==5 and r['protected_files_unchanged']and r['save_files_unchanged']
        assert [x['id']for x in r['cases']]==[x['id']for x in f.c.t.s.e.v.s.o.load(manifest)['cases']]
        for c in r['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                assert a['seconds']<5 and a['returncode']!=-9 and not a['output_limit_exceeded']and not a['reader_failures']and len(bytes.fromhex(a['stderr_hex']))<=256*1024 and p is not None
                assert p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and not p['game_started']and not p['full_trace_enabled']
                if'semantic'in p:assert p['private_commit_bytes']<1024**3 and not p['automatic_projection_implemented']and not p['personal_draws_publishable']
                if manifest==f.REAL:
                    assert'semantic'in p and p['source_unchanged']and not p['consumer_read_sets_implemented']and all(p['semantic']['font_states'])
                    assert all(not m['font_metrics']['rendering_verified']and not m['callback_framework']['consumer_capture_supported']for m in p['metadata'])
                    assert all(s['compilations']>0 for s in p['modules']['states'])
        runs.append(r)
    for left,right in [(runs[0],runs[1]),(runs[3],runs[4])]:
        for a,b in zip(left['cases'],right['cases']):
            for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    transport=archived(root/'reports/font-metrics-transport-v1/result.json.gz');assert transport['passed']and transport['binary_sha256']==binary and transport['supervisor_sha256']==f.old.digest(root/'tools/bounded_font_process.py')and transport['report_limit']==2*1024**2 and transport['diagnostic_limit']==256*1024
    assert all(x['passed']and x['output_limit_exceeded']and not x['timed_out']and x['seconds']<5 and not x['reader_failures']and x['stdout_bytes']<=2*1024**2 and x['stderr_bytes']<=256*1024 for x in transport['reports'])
    return dict(new_classified_checks=64,functional_cases=39,expected_rejection_cases=25,old_classified_regressions=44,transport_quota_case=True,repeated_outputs_equal=True,real_mod_initialization_passed=True,authority_projection_passed=False,framework_consumer_capture_supported=False,rendering_verified=False,game_started=False)

def main():
    verify_callback_framework.main();root=f.ROOT;final=f.c.t.s.e.v.s.o.load(root/'reports/font-metrics-final.json')
    assert final['model_contracts_passed']and final['real_mod_initialization_passed']and not final['gate_passed']and not final['authority_projection_passed']and not final['rendering_verified']
    for group in ['inputs','binaries']:
        for name,h in final[group].items():assert f.old.digest(root/name)==h,'Font artifact differs: '+name
    for a in final['archives']:
        raw=gzip.decompress((root/a['path']).read_bytes());assert f.old.digest(root/a['path'])==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    derived=f.c.t.s.e.v.s.o.load(root/'build-font-metrics/generated/derived_sha256.json')
    assert derived['abi']=='ia-lua533-font-metrics-1'and derived['prior_final_sha256']==f.old.digest(root/'reports/callback-framework-final.json')
    for name,d in derived['derived'].items():assert f.old.digest(root/'build-font-metrics/generated'/name)==d['sha256']and f.old.digest(root/d['source'])==d['source_sha256']
    assert f.old.digest(root/'build-read-set/Release/read_lua.lib')==derived['lua_sha256']and f.old.digest(root/'build-boundary/Release/boundary_lua.lib')==derived['stock_lua_sha256']
    profile=f.c.t.s.e.v.s.o.load(f.PROFILE);assert len(profile['fonts'])==14 and all(x['canonical_width']==x['native_canonical_width']for x in profile['fonts'])
    for e in profile['evidence']:assert f.old.digest(root/e['path'])==e['sha256']
    f.freeze_fonts.freeze() # All outputs already exist; exact frozen metadata comparison only.
    print(json.dumps(dict(artifact_integrity_verified=True,abi=derived['abi'],native_width_controls=14,**results())))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--results-only',action='store_true');a=parser.parse_args()
    if a.results_only:print(json.dumps(results()))
    else:main()
