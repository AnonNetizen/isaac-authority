"""Verify persistent private views, their publication boundary and preserved parents."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import verify_reward_timeline as parent
ROOT=Path(__file__).resolve().parents[1];FINAL=ROOT/'reports/branch-views-final.json'
REPORTS={
    'branch':ROOT/'reports/branch-views-v2/result.json.gz',
    'original':ROOT/'reports/branch-views-original-gates/result.json.gz',
    'reward':ROOT/'reports/branch-views-reward-regressions/result.json.gz',
    'api':ROOT/'reports/branch-views-world-regressions/result.json.gz',
    'init':ROOT/'reports/branch-views-real-init/result.json.gz',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    d=ROOT/'build-branch-views/generated/derived_sha256.json';m=json.loads(d.read_text(encoding='utf-8'))
    paths={d,ROOT/'reports/reward-timeline-final.json',ROOT/'docs/BRANCH_VIEWS_RESULTS.md',ROOT/'tools/check_branch_views.py',Path(__file__),ROOT/'reports/branch-views-preview/result.json.gz',ROOT/'reports/branch-views-v1/failure.json'}
    for group in ['inputs','outputs']:paths.update(ROOT/p for p in m[group])
    for folder in ['branch_views_runtime','research/branch_views']:paths.update(p for p in (ROOT/folder).iterdir()if p.is_file())
    paths.update((ROOT/'build-branch-views/Release')/p for p in ['authority-branch-views.exe','authority-branch-views-reference.exe']);paths.update(REPORTS.values());return sorted(paths)
def audit(require_seal=True):
    with contextlib.redirect_stdout(io.StringIO()):parent.audit()
    if require_seal:
        seal=json.loads(FINAL.read_text(encoding='utf-8'))
        for p,h in seal['files'].items():assert sha(ROOT/p)==h,('Changed sealed input',p)
        assert not seal['playable']and not seal['general_mod_compatibility_gate_passed']
    derived=json.loads((ROOT/'build-branch-views/generated/derived_sha256.json').read_text(encoding='utf-8'))
    assert derived['parent_final_sha256']==sha(ROOT/'reports/reward-timeline-final.json')
    for group in ['inputs','outputs']:
        for p,h in derived[group].items():assert sha(ROOT/p)==h
    data={k:load(p)for k,p in REPORTS.items()};assert all(r['passed']and r['protected_files_unchanged']and not r['playable']for r in data.values())
    assert[len(data[k]['cases'])for k in ['branch','original','reward','api','init']]==[20,2,26,35,3]
    assert data['branch']['functional_or_recovery_cases']==14 and data['branch']['boundary_diagnostics']==6
    suite=json.loads((ROOT/'research/branch_views/suite-v2.json').read_text(encoding='utf-8'));spec={c['id']:c for c in suite['cases']}
    for c in suite['cases']:assert sha(ROOT/c['source'])==c['source_sha256']
    old=json.loads((ROOT/'research/authority_timeline/suite-v8.json').read_text(encoding='utf-8'))['cases'];prior=next(c for c in old if c['id']=='reward-controlled-hud-needs-branch-resolution')
    assert suite['cases'][0]['source']==prior['source']and suite['cases'][0]['source_sha256']==prior['source_sha256']
    for a,b in zip(json.loads((ROOT/'research/branch_views/original-gates-v1.json').read_text(encoding='utf-8'))['cases'],old[:2]):
        a['authority_timeline'].pop('branch_views');assert a==b
    maximum=dict(seconds=0,work=0,private_commit_bytes=0);changed=0
    for group,r in data.items():
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for row in r['cases']:
            assert row['passed'];left,right=row['reports'][-2:];assert left['semantic']==right['semantic']and left['steps']==right['steps']and left['branch_views']==right['branch_views']
            if'stock_control'in row:
                pairs=list(zip(row['reports'],row['artifacts']))+[(row['stock_control'],row['stock_artifact'])]
                assert left['semantic']['world']==row['stock_control']['semantic']['world']and left['semantic']['menu_snapshot']==row['stock_control']['semantic']['menu_snapshot']
            else:pairs=list(zip(row['reports'],row['artifacts']))
            if group=='branch':
                c=spec[row['id']];owner=c.get('owner')or next(iter(c['mod_sdk']['stores'][1]));saved=json.loads(bytes.fromhex(left['semantic']['mod_stores'][1][owner]['data_hex']));assert saved==c.get('saved',c['settings'])
                if c.get('ordinary_values')is not None:assert[s['values']for s in left['steps']if'values'in s][-1]==c['ordinary_values']
                if c.get('presentation_values')is not None:assert[s['presentation_values']for s in left['steps']if'presentation_values'in s][-1]==c['presentation_values']
            for p,a in pairs:
                assert p['abi']=='ia-lua533-branch-views-1'and a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['budget']['used']<=10000000
                assert p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']and not p['personal_draws_publishable']
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['private_commit_bytes']=max(maximum['private_commit_bytes'],p['private_commit_bytes'])
                graphs=[g for g in p['sparse_provenance']if g is not None]
                if p['branch_views']['enabled']:
                    b=p['branch_views'];assert b['game_world_unchanged_by_projection']and not b['trusted_menu_boundary_implemented']and not b['world_paths_may_diverge']
                    assert b['personal']['lane']==1 and b['presentation']['lane']==2 and not b['presentation']['presentation_saves_published'];graphs.append(b['presentation_sources'])
                    assert b['presentation']['changed_conditions']<=8
                for g in graphs:assert g['audit_files_read']==0 and len(g['nodes'])<=4096 and g['bytes']<=1024**2
                for step in p['steps']:
                    if'branch_views'not in step:continue
                    b=step['branch_views'];assert not b['shadow_saves_published']and step['draws']==b['draws']and b['proof']['changed_conditions']<=8
                    assert len(b['proof']['proofs'])<=64
                    for proof in b['proof']['proofs']:
                        assert proof['kind']=='isolated-branch-choice'and not proof['personal_state_written']and proof['authority_operations']
                        assert parent.decision(proof['comparison'],proof['ordinary_operands'])==proof['ordinary_decision']
                        assert parent.decision(proof['comparison'],proof['game_operands'])==proof['selected_decision']
                        changed+=int(proof['ordinary_decision']!=proof['selected_decision'])
    assert changed>0
    rows={c['id']:c for c in data['branch']['cases']}
    for id in ['configuration-reload-without-sidecar-remains-rejected','ambiguous-world-contributions-do-not-select-a-branch','unknown-branch-operand-is-not-assumed-a-constant','changed-branch-budget-restores-all-pending-effects','lua-pcall-cannot-hide-projection-evidence-failure']:
        assert rows[id]['boundary_diagnostic']and any('error'in s for s in rows[id]['reports'][0]['steps'])
    fixture=rows['branch-local-setting-writes-never-publish-shadow-save']['reports'][0];saved=json.loads(bytes.fromhex(fixture['semantic']['mod_stores'][1]['mods/branch-views-fixture']['data_hex']));shadow=json.loads(bytes.fromhex(fixture['branch_views']['presentation_stores']['mods/branch-views-fixture']['data_hex']));assert saved['amount']==202 and shadow['amount']==102
    frames=[s['draws']for s in fixture['steps']if'draws'in s];assert bytes.fromhex(frames[0][0]['text_hex']).decode('utf-8')=='zh|amount=1|ui=one|hits=0|count=0'
    assert not load(ROOT/'reports/branch-views-preview/result.json.gz')['passed']
    return dict(integrity_verified=True,functional_or_recovery_cases=14,boundary_diagnostics=6,original_linked_model_gates_passed=2,unchanged_reward_cases=26,unchanged_world_api_cases=35,real_three_context_initialization_cases=3,maximum_completed_child=maximum,resolved_divergent_ui_branches_implemented=True,arbitrary_deferred_branch_solver_implemented=False,trusted_menu_boundary_implemented=False,configuration_reload_sidecar_implemented=False,long_session_memory_bounded=False,general_mod_compatibility_gate_passed=False,rendering_verified=False,network_verified=False,playable=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args()
    if a.seal:
        if FINAL.exists():raise RuntimeError('Preserved seal already exists')
        summary=audit(False)
        with FINAL.open('x',encoding='utf-8')as f:json.dump(dict(schema='branch-views-seal-1',abi='ia-lua533-branch-views-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},**summary),f,indent=2);f.write('\n')
    print(json.dumps(audit()))
