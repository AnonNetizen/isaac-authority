"""Inspect the linked original gates and their explicit remaining compatibility limits."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];FINAL=ROOT/'reports/authority-timeline-final.json'
import verify_storage_values
REPORTS={
 'model':ROOT/'reports/authority-timeline-v7/result.json.gz',
 'regressions':ROOT/'reports/authority-timeline-world-regressions-v3/result.json.gz',
 'init':ROOT/'reports/authority-timeline-real-init-v3/result.json.gz',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    d=ROOT/'build-authority-timeline/generated/derived_sha256.json';m=json.loads(d.read_text(encoding='utf-8'))
    paths={d,ROOT/'reports/storage-values-final.json',ROOT/'docs/AUTHORITY_TIMELINE_RESULTS.md',ROOT/'tools/check_authority_timeline.py',Path(__file__)}
    paths.update(ROOT/p for p in m['inputs']);paths.update(ROOT/p for p in m['outputs'])
    paths.update(p for p in (ROOT/'authority_timeline_runtime').iterdir()if p.is_file())
    paths.update(p for p in (ROOT/'research/authority_timeline').iterdir()if p.is_file())
    paths.update((ROOT/'build-authority-timeline/Release')/p for p in ['authority-timeline.exe','authority-timeline-reference.exe'])
    paths.update(REPORTS.values());return sorted(paths)
def verify():
    with contextlib.redirect_stdout(io.StringIO()):verify_storage_values.verify()
    seal=json.loads(FINAL.read_text(encoding='utf-8'))
    for p,h in seal['files'].items():assert sha(ROOT/p)==h,('Changed sealed input',p)
    data={k:load(p)for k,p in REPORTS.items()};suite=json.loads((ROOT/'research/authority_timeline/suite-v8.json').read_text(encoding='utf-8'));cases=suite['cases'];spec={c['id']:c for c in cases}
    legacy=[json.loads((ROOT/'research/world_view_required_mixed_v1.json').read_text(encoding='utf-8'))['cases'][0],json.loads((ROOT/'research/world_view_required_projection_v3.json').read_text(encoding='utf-8'))['cases'][0]]
    for c,old in zip(cases[:2],legacy):
        stripped={k:v for k,v in c.items()if k not in ['id','authority_timeline']};prior={k:v for k,v in old.items()if k!='id'}
        assert stripped==prior and sha(ROOT/c['source'])==c['source_sha256']
    model=data['model'];assert model['passed']and model['original_linked_model_gates_passed']and not model['general_mod_compatibility_gate_passed']and not model['playable']
    assert len(model['cases'])==30 and model['functional_cases']==18 and model['boundary_diagnostic_cases']==12
    assert data['regressions']['passed']and len(data['regressions']['cases'])==35
    assert data['init']['passed']and len(data['init']['cases'])==3
    maxima=dict(seconds=0,work=0,private_commit_bytes=0)
    for group,r in data.items():
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for c in r['cases']:
            assert c['passed'];left,right=c['reports'][-2:];assert left['semantic']==right['semantic']
            if group=='model':
                assert left['authority_timeline']==right['authority_timeline']and left['timeline_proofs']==right['timeline_proofs']
                stock=c['stock_control'];assert stock['semantic']['world']==left['semantic']['world']and stock['semantic']['menu_snapshot']==left['semantic']['menu_snapshot']
                for s in left['steps']:
                    if'draws'in s:assert all(isinstance(x['text_hex'],str)for x in s['draws'])
                definition=spec[c['id']]
                if'expected_frames'in definition:assert[[bytes.fromhex(x['text_hex']).decode()for x in s['draws']]for s in left['steps']if'draws'in s]==definition['expected_frames']
                if'values'in definition:assert[s['values']for s in left['steps']if'values'in s][-1]==definition['values']
                pairs=list(zip(c['reports'],c['artifacts']))+[(c['stock_control'],c['stock_artifact'])]
            else:pairs=list(zip(c['reports'],c['artifacts']))
            for p,a in pairs:
                assert p and a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-authority-timeline-1'and p['budget']['limit']==10000000 and p['budget']['used']<=10000000
                assert p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']and not p['personal_draws_publishable']
                maxima['seconds']=max(maxima['seconds'],p['seconds']);maxima['work']=max(maxima['work'],p['budget']['used']);maxima['private_commit_bytes']=max(maxima['private_commit_bytes'],p['private_commit_bytes'])
                book=p['authority_timeline']
                if book is None:continue
                assert book['retained_bytes']<=8*1024**2 and len(book['frame_index'])<=128 and len(book['frames'])<=1
                for f in book['frames']:
                    assert len(f['operations'])<=128 and len(f['queries'])<=1024
                    for i,op in enumerate(f['operations']):assert op['before']==i and op['after']==i+1 and op['signature']['site']
                for g in p['sparse_provenance']:
                    assert g['audit_files_read']==0 and len(g['nodes'])<=4096 and g['bytes']<=1024**2
                for t in p['timeline_proofs']:
                    assert t['text_projection_implemented']and not t['native_equivalence_verified']
                    for proof in t['proofs']:
                        if proof['kind']=='world-reference':assert not proof['native_executed']and proof['state_after']==proof['state_before']+1
                        elif proof['kind']=='hud-reference':assert not proof['personal_storage_written']and proof['rule']=='personal-settings-authority-hud-v1'and proof['authority_operations']
    rows={c['id']:c for c in model['cases']}
    mixed=rows['original-mixed-callback-bound-to-authority-frame']['reports'][0];f=mixed['authority_timeline']['frames'][0]
    assert len(f['states'])==5 and f['states'][0]['coins']==0 and f['states'][-1]['coins']==1
    assert f['states'][0]['menu']['players'][0]['position'][0]==160 and f['states'][-1]['menu']['players'][0]['position']==[17,20]
    assert len(mixed['semantic']['world']['effects'])==1 and len(mixed['timeline_proofs'][1]['proofs'])==4
    hud=rows['original-authority-hud-keeps-personal-save']['reports'][0];saved=json.loads(bytes.fromhex(hud['semantic']['mod_stores'][1]['mods/world-view-fixture']['data_hex']))
    assert saved==dict(amount=2,language='zh',x=147)
    frames=[s['draws']for s in hud['steps']if'draws'in s]
    assert bytes.fromhex(frames[0][0]['text_hex']).decode()=='zh|setting=1|coins=1|worldx=17.0|hud=true|private=1'and frames[0][0]['x']==147
    for id in ['reward-controlled-hud-needs-branch-resolution','cycles-require-an-iteration-proof','random-is-not-executed-without-a-contract','same-number-captured-upvalue-is-not-a-literal-proof']:
        assert rows[id]['boundary_rejection']and any('error'in s for s in rows[id]['reports'][0]['steps'])
    print(json.dumps(dict(integrity_verified=True,original_source_and_expectations_preserved=True,original_linked_model_gates_passed=2,functional_or_recovery_cases=18,boundary_diagnostics=12,unchanged_world_api_cases=35,real_initialization_cases=3,maximum_completed_child=maxima,general_mod_compatibility_gate_passed=False,rendering_verified=False,network_verified=False,long_session_memory_bounded=False,playable=False)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args()
    if a.seal:
        if FINAL.exists():raise RuntimeError('Preserved seal already exists')
        FINAL.write_text(json.dumps(dict(schema='authority-timeline-seal-1',abi='ia-lua533-authority-timeline-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},original_linked_model_gates_passed=True,general_mod_compatibility_gate_passed=False,playable=False),indent=2)+'\n',encoding='utf-8')
    verify()
