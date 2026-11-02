"""Verify bounded menu evidence, including historical false-positive correction."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_menu_environment as m
import verify_ui_flow
ROOT=m.ROOT;SEAL=ROOT/'reports/menu-environment-final.json'
def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def review_baseline():
    old=archived(ROOT/'reports/menu-environment-real-v1/result.json.gz')
    row=next(c for c in old['cases']if c['id']=='mcm-open-via-personal-input')
    assert row['passed']and row['reports'][1]['steps'][-1]['values']==m.values(False)
    assert not row['reports'][1]['steps'][0]['draws']
    return dict(schema='menu-baseline-review-1',historical_open_callback_completed=True,historical_menu_was_open=False,historical_open_verdict_invalidated=True,reason='historical frozen MCM contained prior experimental online guard; original driver checked callback completion but omitted actual visible state',historical_report_sha256=m.f.digest(ROOT/'reports/menu-environment-real-v1/result.json.gz'),pre_experiment_proof_sha256=m.f.digest(ROOT/'research/menu_environment/pristine_mcm_proof.json'),game_files_modified=False)
def results():
    runs=[];maximum=dict(work=0,seconds=0,private_commit_bytes=0)
    for folder,count,path in [('menu-environment-v4',37,m.MANIFEST),('menu-environment-repeat-v4',37,m.MANIFEST),('menu-environment-edges-v2',5,ROOT/'research/menu_environment_edges_v2.json'),('menu-environment-flow-regressions-v2',36,m.f.MANIFEST)]:
        r=archived(ROOT/'reports'/folder/'result.json.gz');assert r['passed']and len(r['cases'])==count and r['manifest_sha256']==m.f.digest(path)and r['protected_files_unchanged']
        assert all(r['binaries'][p.relative_to(ROOT).as_posix()]==m.f.digest(p)for p in [m.EXE,m.REF])
        for c in r['cases']:
            assert c['passed']and all(x['passed']for x in c['checks'])
            for a,p in zip(c['artifacts'],c['reports']):
                assert not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and a['seconds']<5
                assert p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and not p['game_started']and not p['full_trace_enabled']
                maximum['seconds']=max(maximum['seconds'],a['seconds']);maximum['work']=max(maximum['work'],p['budget']['used'])
                if'semantic'in p:
                    assert p['private_commit_bytes']<1024**3 and not p['automatic_projection_implemented']and not p['personal_draws_publishable']and p['source_unchanged']
                    maximum['private_commit_bytes']=max(maximum['private_commit_bytes'],p['private_commit_bytes'])
        runs.append(r)
    for a,b in zip(runs[0]['cases'],runs[1]['cases']):
        assert a['id']==b['id']
        for p,q in zip(a['reports'],b['reports']):assert p.get('semantic')==q.get('semantic')and p.get('steps')==q.get('steps')
    real=archived(ROOT/'reports/menu-environment-real-v4/result.json.gz');assert not real['passed']and len(real['cases'])==5 and real['manifest_sha256']==m.f.digest(m.REAL)
    failures={c['id']:c['reports'][1].get('first_unsupported_entry')for c in real['cases']}
    assert failures=={'mcm-post-render':None,'eid-post-render':'Uncaptured ItemConfig lookup: 0:78','combined-post-render':'Uncaptured ItemConfig lookup: 0:78','mcm-open-via-personal-input':'Unregistered seeds API: AddSeedEffect','combined-open-via-personal-input':'Unregistered seeds API: AddSeedEffect'}
    for c in real['cases']:
        assert all(real['binaries'][p.relative_to(ROOT).as_posix()]==m.f.digest(p)for p in [m.EXE,m.REF])
        for a,p in zip(c['artifacts'],c['reports']):assert a['seconds']<5 and not a['timed_out']and not a['output_limit_exceeded']and p['budget']['used']<=10000000
        if c['id']=='mcm-post-render':
            for p in c['reports']:
                files=[x for role in p['modules']['states']for x in role['files']if x['file']=='scripts/modconfig.lua']
                assert len(files)==2 and all(x['sha256']=='19a0366d7db6faae98a94dd46c5111f5ec4e5d4dc1bc456cb7fd3cacac3ffaf2'for x in files)
    proof=m.f.load(ROOT/'research/menu_environment/pristine_mcm_proof.json');assert m.f.digest(ROOT/proof['executed_source'])==proof['backup_sha256']==proof['executed_sha256']
    old=ROOT/'research/slice3_ui_inputs/mods/mod_config_menu_cn_2494192799/scripts/modconfig.lua';assert m.f.digest(old)==proof['historical_frozen_sha256']
    for folder in ['menu-environment-v1','menu-environment-real-v1','menu-environment-real-v2']:
        path=ROOT/'reports'/folder;r=archived(path/'result.json.gz');assert hashlib.sha256(gzip.decompress((path/'driver.py.gz').read_bytes())).hexdigest()==r['driver_sha256']
    assert m.f.load(ROOT/'reports/menu-environment-baseline-review.json')==review_baseline()
    return dict(schema='menu-environment-verification-1',menu_environment_contracts_passed=True,functional_cases=23,expected_rejections=14,repeated_cases=37,additional_edge_cases=5,ui_flow_regressions=36,maximum_model_or_regression_child=maximum,full_ui_gate_passed=False,first_unsupported_entries=failures,historical_mcm_menu_open_verdict_corrected=True,native_environment_equivalence_verified=False,native_audio_verified=False,rendering_verified=False,authority_projection_passed=False,network_connection_verified=False,long_running_history_bounded=False,bundle_extraction_reproduced=False,playable=False,game_started=False)
def inputs():
    paths=list((ROOT/'menu_runtime').iterdir())+list((ROOT/'research/menu_environment').iterdir())
    paths+=[ROOT/'tools'/name for name in ['freeze_menu_environment.py','freeze_pristine_mcm.py','run_menu_environment.py','check_menu_environment_edges.py','check_menu_environment_regressions.py','verify_menu_environment.py']]
    paths+=[ROOT/name for name in ['research/menu_environment_v1.json','research/menu_environment_v2.json','research/menu_environment_v3.json','research/menu_environment_real_v1.json','research/menu_environment_real_v2.json','research/menu_environment_real_v3.json','research/menu_environment_edges_v1.json','research/menu_environment_edges_v2.json','research/menu_environment_candidate_v1.json','docs/MENU_ENVIRONMENT_PLAN.md','docs/MENU_ENVIRONMENT_RESULTS.md','reports/menu-environment-baseline-review.json','build-menu-environment/generated/derived_sha256.json']]
    return {p.relative_to(ROOT).as_posix():m.f.digest(p)for p in paths if p.is_file()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');p.add_argument('--record-review',action='store_true');a=p.parse_args()
    if a.record_review:m.f.freeze_json(ROOT/'reports/menu-environment-baseline-review.json',review_baseline());return
    with contextlib.redirect_stdout(io.StringIO()):verify_ui_flow.main()
    result=results();derived=m.f.load(ROOT/'build-menu-environment/generated/derived_sha256.json');assert derived['abi']=='ia-lua533-menu-environment-1'and derived['parent_final_sha256']==m.f.digest(ROOT/'reports/ui-flow-final.json')
    for name,v in derived['derived'].items():assert m.f.digest(ROOT/'build-menu-environment/generated'/name)==v['sha256']and m.f.digest(ROOT/v['source'])==v['source_sha256']
    archives=[]
    for folder in ['menu-environment-v1','menu-environment-real-v1','menu-environment-real-v2','menu-environment-v3','menu-environment-repeat-v3','menu-environment-real-v3','menu-environment-edges-v1','menu-environment-flow-regressions-v1','menu-environment-v4','menu-environment-repeat-v4','menu-environment-real-v4','menu-environment-edges-v2','menu-environment-flow-regressions-v2']:
        for path in sorted((ROOT/'reports'/folder).glob('*.gz')):
            raw=gzip.decompress(path.read_bytes());archives.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=m.f.digest(path),raw_sha256=hashlib.sha256(raw).hexdigest()))
    seal=dict(**result,abi=derived['abi'],parent_final_sha256=m.f.digest(ROOT/'reports/ui-flow-final.json'),inputs=inputs(),binaries={p.relative_to(ROOT).as_posix():m.f.digest(p)for p in [m.EXE,m.REF]},archives=archives)
    if a.seal:m.f.freeze_json(SEAL,seal)
    else:assert m.f.load(SEAL)==seal
    print(json.dumps(dict(artifact_integrity_verified=True,**result)))
if __name__=='__main__':main()
