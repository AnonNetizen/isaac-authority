"""Verify API evidence and preserve the failed user-rule gates as failures."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as w
import verify_menu_environment
ROOT=w.ROOT;SEAL=ROOT/'reports/world-view-final.json'
def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def valid_child(a,p):
    assert p is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and a['seconds']<5
    assert p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and not p['full_trace_enabled']and not p['game_started']
    if'semantic'in p:assert p['private_commit_bytes']<1024**3 and not p['automatic_projection_implemented']and not p['personal_draws_publishable']
def record(row):
    assert not row['authority_reference_proven']and row['result']=='native-void'
    assert row['state_after']==row['state_before']+(row['policy']=='authority-commit')
    assert row['context']and any(f['instruction']is not None for f in row['context'])
    for f in row['context']:
        if f['instruction']is not None:assert f['instruction']['pc']>=0 and len(f['bytecode_sha256'])==64 and len(f['source_sha256'])==64
def results():
    binaries={p.relative_to(ROOT).as_posix():w.parent.f.digest(p)for p in[w.EXE,w.REF]};runs=[];maximum=dict(seconds=0,work=0,private_commit_bytes=0)
    for folder,count,path in [('world-view-v7',35,w.MANIFEST),('world-view-repeat-v7',35,w.MANIFEST),('world-view-menu-regressions-v2',37,w.parent.MANIFEST)]:
        r=archived(ROOT/'reports'/folder/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['manifest_sha256']==w.parent.f.digest(path)and r['binaries']==binaries and r['protected_files_unchanged']
        for c in r['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                valid_child(a,p);maximum['seconds']=max(maximum['seconds'],a['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['private_commit_bytes']=max(maximum['private_commit_bytes'],p.get('private_commit_bytes',0))
                for step in p.get('steps',[]):
                    for row in step.get('world_records',[]):record(row)
        runs.append(r)
    for a,b in zip(runs[0]['cases'],runs[1]['cases']):
        assert a['id']==b['id']
        for p,q in zip(a['reports'],b['reports']):assert p['semantic']==q['semantic']and p['steps']==q['steps']and p['world_view_diagnostics']==q['world_view_diagnostics']
    for folder,message in [('world-view-required-projection-v5',None),('world-view-required-mixed-v2','World write requires authority phase')]:
        r=archived(ROOT/'reports'/folder/'result.json.gz');assert not r['passed']and len(r['cases'])==1 and r['binaries']==binaries and not r['full_ui_gate_passed']
        c=r['cases'][0];assert not c['passed']
        for a,p in zip(c['artifacts'],c['reports']):
            valid_child(a,p)
            if message:assert a['returncode']==1 and p['first_unsupported_entry']==message
            else:
                assert a['returncode']==0
                frame=next(s for s in p['steps']if'draws'in s);text=bytes.fromhex(frame['draws'][0]['text_hex']).decode();assert'|setting=2|'in text and'|coins=1|'in text
                store=json.loads(bytes.fromhex(p['semantic']['mod_stores'][1]['mods/world-view-fixture']['data_hex']));assert store==dict(amount=2,language='zh',x=147)
    real=archived(ROOT/'reports/world-view-real-v7/result.json.gz');assert not real['passed']and len(real['cases'])==6 and real['binaries']==binaries and real['manifest_sha256']==w.parent.f.digest(w.REAL)
    failures={c['id']:c['reports'][1].get('first_unsupported_entry')for c in real['cases']}
    assert failures=={'mcm-post-render':None,'eid-post-render':'Frozen module path outside registered roots','combined-post-render':'Frozen module path outside registered roots','mcm-open-via-personal-input':'Sprite.Render contract not implemented','combined-open-via-personal-input':'Sprite.Render contract not implemented','eid-authority-unlock-warning':'Sprite property write not implemented: Scale'}
    for c in real['cases']:
        for a,p in zip(c['artifacts'],c['reports']):
            valid_child(a,p)
            if'open-via-personal-input'in c['id']:
                witness=p['world_view_diagnostics']['first_failure'];assert witness['record_count']==7
                rows=witness['records'];assert [x['api']for x in rows]==['Seeds.AddSeedEffect']+['EntityPlayer.Velocity','EntityPlayer.Position','EntityPlayer.ControlsEnabled']*2
                assert all(x['policy']=='personal-intent'and x['state_before']==x['state_after']==0 for x in rows)
                for row in rows:record(row)
            if c['id']in ['eid-post-render','combined-post-render']:
                witness=p['texture_state']['first_failure'];assert witness['arguments'][2]['bytes_hex']==''and witness['arguments'][1]['integer']==0
    # Earlier one-frame EID completion was empty and is not used as a HUD pass.
    early=archived(ROOT/'reports/world-view-real-v1/result.json.gz')
    for c in early['cases']:
        if c['id']in ['eid-post-render','combined-post-render']:assert not any(s['draws']for s in c['reports'][1]['steps']if'draws'in s)
    identity=archived(ROOT/'reports/world-view-source-identity-v1/result.json.gz');assert identity['passed']and identity['binaries']==binaries
    for a,p in zip(identity['artifacts'],identity['reports']):valid_child(a,p);assert p['steps'][0]['values']==w.values('secondary')
    return dict(schema='world-view-verification-1',api_model_contracts_passed=True,api_functional_cases=24,api_expected_rejections=11,repeated_api_cases=35,menu_regressions=37,physical_source_ownership_regressions=1,required_functional_gates=2,required_functional_failures=2,user_rule_projection_passed=False,personal_mixed_callback_timeline_passed=False,real_source_cases=6,real_source_functional_failures=5,actual_mcm_world_intents_captured=7,first_unsupported_entries=failures,maximum_completed_api_or_regression_child=maximum,full_ui_gate_passed=False,native_equivalence_verified=False,native_tags_resampled=False,authority_projection_passed=False,rendering_verified=False,network_connection_verified=False,long_running_history_bounded=False,bundle_extraction_reproduced=False,playable=False,game_started=False)
def main():
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args();argv=sys.argv
    try:
        sys.argv=[argv[0]]
        with contextlib.redirect_stdout(io.StringIO()):verify_menu_environment.main();w.frozen.freeze()
    finally:sys.argv=argv
    value=results();paths=list((ROOT/'world_view_runtime').iterdir())+list((ROOT/'research/world_view').rglob('*'))
    paths+=[ROOT/'tools'/n for n in ['freeze_world_view.py','run_world_view.py','check_world_view_regressions.py','check_world_view_mixed_gate.py','check_world_view_source_identity.py','verify_world_view.py']]
    paths+=list((ROOT/'research').glob('world_view*.json'))+[ROOT/'docs/WORLD_VIEW_RESULTS.md',ROOT/'build-world-view/generated/derived_sha256.json']
    inputs={p.relative_to(ROOT).as_posix():w.parent.f.digest(p)for p in paths if p.is_file()}
    derived=w.parent.f.load(ROOT/'build-world-view/generated/derived_sha256.json');assert derived['abi']=='ia-lua533-world-view-1'and derived['parent_final_sha256']==w.parent.f.digest(ROOT/'reports/menu-environment-final.json')
    for name,v in derived['derived'].items():assert w.parent.f.digest(ROOT/'build-world-view/generated'/name)==v['sha256']and w.parent.f.digest(ROOT/v['source'])==v['source_sha256']
    archives=[]
    for folder in sorted((ROOT/'reports').glob('world-view-*')):
        if not folder.is_dir():continue
        for path in sorted(folder.glob('*.gz')):
            raw=gzip.decompress(path.read_bytes());archives.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=w.parent.f.digest(path),raw_sha256=hashlib.sha256(raw).hexdigest()))
        driver=folder/'driver.py.gz'
        if driver.exists():assert hashlib.sha256(gzip.decompress(driver.read_bytes())).hexdigest()==archived(folder/'result.json.gz')['driver_sha256']
    seal=dict(**value,abi=derived['abi'],parent_final_sha256=derived['parent_final_sha256'],inputs=inputs,binaries={p.relative_to(ROOT).as_posix():w.parent.f.digest(p)for p in[w.EXE,w.REF]},archives=archives)
    if a.seal:w.parent.f.freeze_json(SEAL,seal)
    else:assert w.parent.f.load(SEAL)==seal
    print(json.dumps(dict(artifact_integrity_verified=True,**value)))
if __name__=='__main__':main()
