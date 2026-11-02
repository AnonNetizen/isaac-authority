"""Validate evidence before sealing; finite RNG contracts never imply playable co-op."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import verify_authority_timeline as parent
ROOT=Path(__file__).resolve().parents[1];FINAL=ROOT/'reports/reward-timeline-final.json'
REPORTS={
    'reward':ROOT/'reports/reward-timeline-v3/result.json.gz',
    'regressions':ROOT/'reports/reward-timeline-world-regressions/result.json.gz',
    'init':ROOT/'reports/reward-timeline-real-init/result.json.gz',
    'original':ROOT/'reports/reward-timeline-original-gates/result.json.gz',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    d=ROOT/'build-reward-timeline/generated/derived_sha256.json';m=json.loads(d.read_text(encoding='utf-8'))
    paths={d,ROOT/'reports/authority-timeline-final.json',ROOT/'docs/REWARD_TIMELINE_RESULTS.md',ROOT/'tools/check_reward_timeline.py',Path(__file__)}
    paths.update(ROOT/p for p in m['inputs']);paths.update(ROOT/p for p in m['outputs'])
    for folder in ['reward_timeline_runtime','research/reward_timeline']:paths.update(p for p in (ROOT/folder).iterdir()if p.is_file())
    paths.update((ROOT/'build-reward-timeline/Release')/p for p in ['authority-reward.exe','authority-reward-reference.exe'])
    paths.update(REPORTS.values());paths.update(ROOT/'reports'/name/'result.json.gz'for name in ['reward-timeline-v1','reward-timeline-v2'])
    return sorted(paths)
def scalar(v):
    t=v['type']
    if t=='nil':return None
    if t=='string':return bytes.fromhex(v['hex'])
    assert t in ['integer','number','boolean'];return v['value']
def decision(op,args):
    a=[scalar(v)for v in args]
    if op in ['branch-test','branch-testset']:return not(a[0]is None or a[0]is False)
    if op=='branch-eq':return a[0]==a[1]
    if op=='branch-lt':return a[0]<a[1]
    if op=='branch-le':return a[0]<=a[1]
    raise AssertionError(op)
def audit(require_seal=True):
    with contextlib.redirect_stdout(io.StringIO()):parent.verify()
    if require_seal:
        sealed=json.loads(FINAL.read_text(encoding='utf-8'))
        for p,h in sealed['files'].items():assert sha(ROOT/p)==h,('Changed sealed input',p)
        assert not sealed['playable']and not sealed['general_mod_compatibility_gate_passed']
    derived=json.loads((ROOT/'build-reward-timeline/generated/derived_sha256.json').read_text(encoding='utf-8'))
    assert derived['parent_final_sha256']==sha(ROOT/'reports/authority-timeline-final.json')
    for collection in ['inputs','outputs']:
        for p,h in derived[collection].items():assert sha(ROOT/p)==h
    reports={k:load(p)for k,p in REPORTS.items()};reward=reports['reward']
    assert all(r['passed']and r['protected_files_unchanged']and not r['playable']for r in reports.values())
    assert [len(reports[k]['cases'])for k in ['reward','regressions','init','original']]==[26,35,3,2]
    assert reward['functional_cases']==18 and reward['boundary_diagnostic_cases']==8 and not reward['general_mod_compatibility_gate_passed']
    for p in [ROOT/'research/reward_timeline/suite-v5.json',ROOT/'research/reward_timeline/controls-v5.json']:
        for c in json.loads(p.read_text(encoding='utf-8'))['cases']:assert sha(ROOT/c['source'])==c['source_sha256']
    original=json.loads((ROOT/'research/reward_timeline/original-gates-v1.json').read_text(encoding='utf-8'))['cases']
    prior=json.loads((ROOT/'research/authority_timeline/suite-v8.json').read_text(encoding='utf-8'))['cases'][:2];assert original==prior
    maximum=dict(seconds=0,work=0,private_commit_bytes=0);branch_proofs=0;random_proofs=0
    for group,r in reports.items():
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for c in r['cases']:
            assert c['passed'];left,right=c['reports'][-2:];assert left['semantic']==right['semantic']and left['steps']==right['steps']
            if group in ['reward','original']:
                pairs=list(zip(c['reports'],c['artifacts']))+[(c['stock_control'],c['stock_artifact'])]
                assert left['semantic']['world']==c['stock_control']['semantic']['world']
                assert left['timeline_proofs']==right['timeline_proofs']and left['authority_timeline']==right['authority_timeline']
            else:pairs=list(zip(c['reports'],c['artifacts']))
            for p,a in pairs:
                assert p['abi']=='ia-lua533-reward-timeline-1'and a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['budget']['used']<=10000000
                assert p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']and not p['personal_draws_publishable']
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['private_commit_bytes']=max(maximum['private_commit_bytes'],p['private_commit_bytes'])
                for g in p['sparse_provenance']:
                    if g is not None:assert g['audit_files_read']==0 and len(g['nodes'])<=4096 and g['bytes']<=1024**2
                for rp in p['reward_proofs']:assert rp['provider']=='coin-model-mt19937-v1'and not rp['native_game_rng_verified']and not rp['divergent_branch_solver_implemented']
                frames=[]
                if p['authority_timeline']is not None:
                    book=p['authority_timeline'];assert book['retained_bytes']<=8*1024**2 and len(book['frame_index'])<=128;frames.extend(book['frames'])
                frames.extend(s for s in p['steps']if'key'in s and'operations'in s and'states'in s)
                for f in frames:
                    for i,o in enumerate(f['operations']):
                        assert o['before']==i and o['after']==i+1 and o['signature']['site']
                        before,after=f['states'][i:i+2];api=o['signature']['api']
                        if api in ['math.random','math.randomseed']:
                            assert o['actual']['rng_before']==before['rng_sha256']and o['actual']['rng_after']==after['rng_sha256']
                            assert after['rng_draw_calls']-before['rng_draw_calls']==int(api=='math.random')and after['rng_seed_calls']-before['rng_seed_calls']==int(api=='math.randomseed')
                            if api=='math.randomseed':assert o['actual']['return_count']==0
                proofs=[proof for t in p['timeline_proofs']for proof in t['proofs']]+[proof for s in p['steps']if'timeline'in s for proof in s['timeline']['proofs']]
                for proof in proofs:
                    kind=proof['kind']
                    if kind=='random-result-reference':assert not proof['generator_executed'];random_proofs+=1
                    elif kind=='world-reference':assert not proof['native_executed']
                    elif kind=='reward-branch-proof':assert proof['same_path_proven']and decision(proof['comparison'],proof['ordinary_operands'])==decision(proof['comparison'],proof['game_operands'])==proof['decision'];branch_proofs+=1
                    elif kind=='hud-reference':assert not proof['personal_storage_written']and proof['rule']=='personal-settings-authority-hud-v1'
                    elif kind=='matched-operation-query-frontier':assert proof['all_operations_matched']and proof['state']>0
    assert branch_proofs>0 and random_proofs>0
    rows={c['id']:c for c in reward['cases']}
    for name in ['divergent-game-view-branch-still-explicitly-rejected','personal-added-random-has-no-authority-operation','unregistered-time-source-remains-rejected']:
        assert rows[name]['boundary_diagnostic']and any('error'in s for s in rows[name]['reports'][0]['steps'])
    assert not load(ROOT/'reports/reward-timeline-v1/result.json.gz')['passed']
    return dict(integrity_verified=True,functional_or_recovery_cases=18,boundary_diagnostics=8,original_linked_model_gates_passed=2,unchanged_world_api_cases=35,real_initialization_cases=3,maximum_completed_child=maximum,divergent_branch_solver_implemented=False,native_game_rng_verified=False,general_mod_compatibility_gate_passed=False,long_session_memory_bounded=False,rendering_verified=False,network_verified=False,playable=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args()
    if a.seal:
        if FINAL.exists():raise RuntimeError('Preserved seal already exists')
        summary=audit(False)
        with FINAL.open('x',encoding='utf-8')as f:json.dump(dict(schema='reward-timeline-seal-1',abi='ia-lua533-reward-timeline-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},**summary),f,indent=2);f.write('\n')
    print(json.dumps(audit()))
