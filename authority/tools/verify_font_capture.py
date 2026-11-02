"""Verify the bounded font capture stage while leaving full UI/playability closed."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_font_capture as f
import verify_font_metrics

def archived(p):return json.loads(gzip.decompress(p.read_bytes()))

def results():
    binary=f.digest(f.EXE);reference=f.digest(f.REF);runs=[]
    for folder,count,manifest in [('font-capture-v3',48,f.MANIFEST),('font-capture-repeat-v3',48,f.MANIFEST),('font-capture-real-v2',5,f.REAL),('font-capture-font-regressions-v1',64,f.old.CURRENT)]:
        report=archived(f.ROOT/'reports'/folder/'result.json.gz');assert report['passed']and len(report['cases'])==count and report['manifest_sha256']==f.digest(manifest)
        assert report['binaries'][f.EXE.relative_to(f.ROOT).as_posix()]==binary and report['binaries'][f.REF.relative_to(f.ROOT).as_posix()]==reference
        assert report['work_limit']==10000000 and report['child_timeout_seconds']==5 and report['protected_files_unchanged']and not report['game_started']and not report['rendering_verified']and not report['authority_projection_passed']
        assert [c['id']for c in report['cases']]==[c['id']for c in f.load(manifest)['cases']]
        for c in report['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                assert p is not None and a['seconds']<5 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and not p['game_started']and not p['full_trace_enabled']
                if 'semantic'in p:
                    assert p['private_commit_bytes']<1024**3 and p['source_unchanged']and not p['automatic_projection_implemented']and not p['personal_draws_publishable']
                    for m in p['metadata']:
                        if m['font_capture']is not None:assert m['font_capture']['native_draw_calls']==0 and not m['font_capture']['layout_or_pixels_verified']and not m['font_capture']['authority_projection_proven']
        runs.append(report)
    for a,b in zip(runs[0]['cases'],runs[1]['cases']):
        for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    cases={c['id']:c for c in runs[0]['cases']}
    rollback=cases['rollback-all-updated-state']['reports'][1]
    saved=rollback['semantic']['mod_stores'][1]['mods/font-capture-fixture'];assert saved['present']and json.loads(bytes.fromhex(saved['data_hex']))==dict(amount=2,language='zh',x=147)
    assert cases['authority-reward-once']['reports'][1]['semantic']['world']['effects']==[dict(amount=1,api='coins.add')]
    real_old=archived(f.ROOT/'reports/font-capture-real-v1/result.json.gz');assert real_old['passed']
    for a,b in zip(real_old['cases'],runs[2]['cases']):
        for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    for name in ['eid-render-string','combined-render-string']:
        c=next(c for c in runs[2]['cases']if c['id']==name);p=c['reports'][1];assert p['steps'][1]['draws'][0]['text_hex']==b'native bridge'.hex()and not p['consumer_read_sets_implemented']
    callbacks=archived(f.ROOT/'reports/font-capture-callback-regressions-v1/result.json.gz');assert callbacks['passed']and len(callbacks['cases'])==44 and callbacks['binary_sha256']==binary and callbacks['manifest_sha256']==f.digest(f.old.c.CURRENT)
    for c in callbacks['cases']:
        assert c['passed']and c['report']is not None and c['artifact']['seconds']<5 and c['report']['budget']['limit']==10000000
    probes=archived(f.ROOT/'reports/font-capture-probes-v1/result.json.gz');assert not probes['passed']and probes['manifest_sha256']==f.digest(f.PROBES)and len(probes['cases'])==3
    failures={c['id']:c['reports'][0]['first_unsupported_entry']for c in probes['cases']}
    assert failures=={'mcm-post-render':'Game.IsPaused contract not implemented','eid-post-render':'Sprite.Update contract not implemented','combined-post-render':'Game.IsPaused contract not implemented'}
    wire=archived(f.ROOT/'reports/font-capture-wire-v1/result.json.gz');assert wire['passed']and wire['runtime_sha256']==binary and wire['binary_sha256']==f.digest(f.EXE.with_name('authority-font-wire-check.exe'))
    assert wire['valid']['report']['commands']==59 and wire['valid']['report']['frames']==57 and wire['valid']['report']['largest_packet_bytes']<=512*1024
    assert len(wire['refusals'])==5 and all(x['passed']for x in wire['refusals'])and not wire['network_connection_verified']and not wire['rendering_verified']
    for p,h in wire['sources'].items():assert f.digest(f.ROOT/p)==h
    initial=archived(f.ROOT/'reports/font-capture-v1/result.json.gz');assert not initial['passed']and len([c for c in initial['cases']if not c['passed']])==5
    driver=gzip.decompress((f.ROOT/'reports/font-capture-v1/driver.py.gz').read_bytes());assert hashlib.sha256(driver).hexdigest()==initial['driver_sha256']
    return dict(font_capture_contracts_passed=True,functional_cases=26,expected_rejection_cases=22,repeated_cases=48,old_classified_regressions=108,real_source_text_capture_cases=2,native_protocol_font_commands=59,full_post_render_passed=False,first_unsupported_entries=failures,framework_consumer_capture_supported=False,authority_projection_passed=False,rendering_verified=False,network_connection_verified=False,playable=False,game_started=False)

def main():
    verify_font_metrics.main();seal=f.load(f.ROOT/'reports/font-capture-final.json');assert not seal['playable']and not seal['full_ui_gate_passed']and seal['font_capture_contracts_passed']
    for group in ['inputs','binaries']:
        for p,h in seal[group].items():assert f.digest(f.ROOT/p)==h,'Font capture artifact differs: '+p
    for a in seal['archives']:
        packed=f.ROOT/a['path'];raw=gzip.decompress(packed.read_bytes());assert f.digest(packed)==a['sha256']and hashlib.sha256(raw).hexdigest()==a['raw_sha256']
    derived=f.load(f.ROOT/'build-font-capture/generated/derived_sha256.json');assert derived['abi']=='ia-lua533-font-capture-1'and derived['prior_final_sha256']==f.digest(f.ROOT/'reports/font-metrics-final.json')
    for name,v in derived['derived'].items():assert f.digest(f.ROOT/'build-font-capture/generated'/name)==v['sha256']and f.digest(f.ROOT/v['source'])==v['source_sha256']
    assert derived['lua_sha256']==f.digest(f.ROOT/'build-read-set/Release/read_lua.lib')and derived['stock_lua_sha256']==f.digest(f.ROOT/'build-boundary/Release/boundary_lua.lib')
    profile=f.load(f.PROFILE);e=profile['settings_witness']
    with(f.ROOT/e['path']).open('rb')as stream:stream.seek(e['offset']);raw=stream.read(e['bytes'])
    assert hashlib.sha256(raw).hexdigest()==e['sha256']and not profile['default_alignment_verified']
    print(json.dumps(dict(artifact_integrity_verified=True,abi=derived['abi'],**results())))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results-only',action='store_true');a=p.parse_args()
    if a.results_only:print(json.dumps(results()))
    else:main()
