"""Verify pause/clock evidence without declaring full UI or native playback ready."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as f
import verify_font_capture

def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def legacy_review():
    report=archived(f.ROOT/'reports/ui-flow-legacy-regressions-v1/result.json.gz');assert len(report['cases'])==78 and not report['passed']and report['binary_sha256']==f.digest(f.EXE)
    ordinary=lambda rows:[{k:({a:b for a,b in v.items()if a not in ['gc_prepaid_heap_bytes','gc_prepaid_work']}if k=='metadata'and isinstance(v,dict)else v)for k,v in row.items()}for row in rows]
    baselines={group:{c['id']:c['reports'][1]for c in archived(f.ROOT/path)['cases']}for group,path in [('objects','reports/model-objects-v3/result.json.gz'),('sprites','reports/sprite-state-v2/result.json.gz')]}
    differences=[]
    for c in report['cases']:
        a=c['report'];b=baselines[c['group']][c['id']];assert a is not None and c['artifact']['seconds']<5 and not c['artifact']['timed_out']and not c['artifact']['output_limit_exceeded']and a['budget']['limit']==10000000
        assert a.get('semantic')==b.get('semantic')and a.get('first_unsupported_entry')==b.get('first_unsupported_entry')and ordinary(a.get('steps',[]))==ordinary(b.get('steps',[]))
        if a.get('steps')!=b.get('steps'):
            differences.append(dict(group=c['group'],id=c['id'],fields=['gc_prepaid_heap_bytes','gc_prepaid_work'],old=[b['steps'][1]['metadata'][k]for k in ['gc_prepaid_heap_bytes','gc_prepaid_work']],new=[a['steps'][1]['metadata'][k]for k in ['gc_prepaid_heap_bytes','gc_prepaid_work']]))
    assert [x['id']for x in differences]==['bounded-gc-churn']
    return dict(schema='ui-flow-legacy-review-1',functional_cases_matched=78,original_strict_verdict=False,original_failure_preserved=True,excluded_fields_are_allocator_dependent_telemetry=True,differences=differences,result_sha256=f.digest(f.ROOT/'reports/ui-flow-legacy-regressions-v1/result.json.gz'))

def results():
    binary=f.digest(f.EXE);reference=f.digest(f.REF);runs=[]
    for name,count,manifest in [('ui-flow-v2',36,f.MANIFEST),('ui-flow-repeat-v2',36,f.MANIFEST),('ui-flow-font-regressions-v1',48,f.parent.MANIFEST)]:
        r=archived(f.ROOT/'reports'/name/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['manifest_sha256']==f.digest(manifest)and r['binaries'][f.EXE.relative_to(f.ROOT).as_posix()]==binary and r['binaries'][f.REF.relative_to(f.ROOT).as_posix()]==reference
        assert r['work_limit']==10000000 and r['child_timeout_seconds']==5 and r['protected_files_unchanged']and not r['playable']and not r['rendering_verified']and not r['authority_projection_passed']
        for c in r['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                assert p is not None and a['seconds']<5 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and not p['game_started']and not p['full_trace_enabled']and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())
                if'semantic'in p:
                    assert p['private_commit_bytes']<1024**3 and p['source_unchanged']and not p['automatic_projection_implemented']and not p['personal_draws_publishable']
                    for m in p['metadata']:
                        if m['ui_flow']is not None:assert not m['ui_flow']['native_update_equivalence_verified']and not m['ui_flow']['non_loop_terminal_supported']and m['ui_flow']['per_update_journal_records']==0
        runs.append(r)
    for a,b in zip(runs[0]['cases'],runs[1]['cases']):
        for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    repeated=next(c for c in runs[0]['cases']if c['id']=='loop-10000-updates-fixed-storage')['reports'][1];assert repeated['steps'][-2]['clocks'][0]['updates']==10000 and len(repeated['steps'][-1]['states'][0]['commands'])==2
    probes=archived(f.ROOT/'reports/ui-flow-real-v1/result.json.gz');assert not probes['passed']and len(probes['cases'])==3 and probes['manifest_sha256']==f.digest(f.REAL)
    failures={c['id']:c['reports'][0]['first_unsupported_entry']for c in probes['cases']};assert'SFXManager'in failures['mcm-post-render']and'GetPlayerType'in failures['eid-post-render']and'SFXManager'in failures['combined-post-render']
    text=archived(f.ROOT/'reports/ui-flow-real-text-v1/result.json.gz');assert text['passed']and len(text['cases'])==2 and text['binaries'][f.EXE.relative_to(f.ROOT).as_posix()]==binary
    for c in text['cases']:
        assert c['passed']and all(x['passed']for x in c['checks'])
        for a,p in zip(c['artifacts'],c['reports']):assert a['seconds']<5 and p['steps'][1]['draws'][0]['text_hex']==b'native bridge'.hex()and p['semantic']['sprite_clocks']and p['budget']['limit']==10000000
    review=legacy_review();assert f.load(f.ROOT/'reports/ui-flow-legacy-regressions-v1/review.json')==review
    initial=archived(f.ROOT/'reports/ui-flow-v1/result.json.gz');assert not initial['passed']and[c['id']for c in initial['cases']if not c['passed']]==['reject-personal-reward'];assert hashlib.sha256(gzip.decompress((f.ROOT/'reports/ui-flow-v1/driver.py.gz').read_bytes())).hexdigest()==initial['driver_sha256']
    return dict(pause_snapshot_model_passed=True,explicit_loop_clock_model_passed=True,functional_cases=21,expected_rejection_cases=15,repeated_cases=36,old_functional_regressions=126,old_strict_gc_telemetry_match=False,real_text_capture_cases=2,full_ui_gate_passed=False,first_unsupported_entries=failures,native_update_equivalence_verified=False,non_loop_terminal_verified=False,rendering_verified=False,authority_projection_passed=False,playable=False,game_started=False)

def main():
    verify_font_capture.main();seal=f.load(f.ROOT/'reports/ui-flow-final.json');assert seal['pause_snapshot_model_passed']and seal['explicit_loop_clock_model_passed']and not seal['full_ui_gate_passed']and not seal['playable']
    for group in ['inputs','binaries']:
        for p,h in seal[group].items():assert f.digest(f.ROOT/p)==h,'UI flow artifact differs: '+p
    for a in seal['archives']:
        p=f.ROOT/a['path'];raw=gzip.decompress(p.read_bytes());assert f.digest(p)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    derived=f.load(f.ROOT/'build-ui-flow/generated/derived_sha256.json');assert derived['prior_final_sha256']==f.digest(f.ROOT/'reports/font-capture-final.json')and derived['abi']=='ia-lua533-ui-flow-1'
    for name,v in derived['derived'].items():assert f.digest(f.ROOT/'build-ui-flow/generated'/name)==v['sha256']and f.digest(f.ROOT/v['source'])==v['source_sha256']
    assert derived['lua_sha256']==f.digest(f.ROOT/'build-read-set/Release/read_lua.lib')and derived['stock_lua_sha256']==f.digest(f.ROOT/'build-boundary/Release/boundary_lua.lib')
    import freeze_ui_flow;freeze_ui_flow.freeze()
    print(json.dumps(dict(artifact_integrity_verified=True,abi=derived['abi'],**results())))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results-only',action='store_true');p.add_argument('--record-legacy-review',action='store_true');a=p.parse_args()
    if a.record_legacy_review:
        value=legacy_review();path=f.ROOT/'reports/ui-flow-legacy-regressions-v1/review.json';f.freeze_json(path,value);print(json.dumps(value))
    elif a.results_only:print(json.dumps(results()))
    else:main()
