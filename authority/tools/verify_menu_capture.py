"""Preserve successful captures and real EID failures without promoting the UI gate."""
import argparse,contextlib,gzip,hashlib,io,json,re,sys
from pathlib import Path
sys.dont_write_bytecode=True
import verify_branch_views as parent
ROOT=Path(__file__).resolve().parents[1];FINAL=ROOT/'reports/menu-capture-final.json'
REPORTS={
    'model':ROOT/'reports/menu-capture-model-v4/result.json.gz',
    'real':ROOT/'reports/menu-capture-real-v5/result.json.gz',
    'contracts':ROOT/'reports/menu-capture-contracts/result.json.gz',
    'api':ROOT/'reports/menu-capture-world-regressions-v3/result.json.gz',
    'branch':ROOT/'reports/menu-capture-branch-regressions-v3/result.json.gz',
    'original':ROOT/'reports/menu-capture-original-gates/result.json.gz',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    d=ROOT/'build-menu-capture/generated/derived_sha256.json';m=json.loads(d.read_text(encoding='utf-8'))
    paths={d,ROOT/'reports/branch-views-final.json',ROOT/'docs/MENU_CAPTURE_RESULTS.md',ROOT/'tools/check_menu_capture.py',ROOT/'tools/freeze_mcm_capture_contract.py',Path(__file__)}
    for k in ['inputs','outputs']:paths.update(ROOT/p for p in m[k])
    for folder in ['menu_capture_runtime','research/menu_capture']:paths.update(p for p in (ROOT/folder).iterdir()if p.is_file())
    paths.update(REPORTS.values());paths.update((ROOT/'build-menu-capture/Release')/n for n in ['authority-menu-capture.exe','authority-menu-capture-reference.exe'])
    for name in ['menu-capture-model-v1','menu-capture-model-v2','menu-capture-model-v3','menu-capture-real-v1','menu-capture-real-v2','menu-capture-real-v3','menu-capture-real-v4']:
        paths.add(ROOT/'reports'/name/'result.json.gz')
    return sorted(paths)
def audit(require_seal=True):
    with contextlib.redirect_stdout(io.StringIO()):parent.audit()
    if require_seal:
        seal=json.loads(FINAL.read_text(encoding='utf-8'))
        for p,h in seal['files'].items():assert sha(ROOT/p)==h,('Changed sealed input',p)
        assert not seal['full_real_ui_gate_passed']and not seal['playable']
    d=json.loads((ROOT/'build-menu-capture/generated/derived_sha256.json').read_text(encoding='utf-8'));assert d['parent_final_sha256']==sha(ROOT/'reports/branch-views-final.json')
    for k in ['inputs','outputs']:
        for p,h in d[k].items():assert sha(ROOT/p)==h
    reports={k:load(p)for k,p in REPORTS.items()};assert[len(reports[k]['cases'])for k in ['model','real','contracts','api','branch','original']]==[16,5,4,35,20,2]
    assert all(r['passed']for k,r in reports.items()if k!='real')and not reports['real']['passed']
    spec={c['id']:c for c in json.loads((ROOT/'research/menu_capture/suite-v3.json').read_text(encoding='utf-8'))['cases']}
    assert sum(c.get('boundary',False)for c in spec.values())==5
    for c in spec.values():assert sha(ROOT/c['source'])==c['source_sha256']
    contract=json.loads((ROOT/'research/menu_capture/mcm-contract-v1.json').read_text(encoding='utf-8'));assert sha(ROOT/contract['source'])==contract['source_sha256']and not contract['runtime_purpose_enforcement_implemented']and contract['locations_are_diagnostic_only']
    maximum=dict(seconds=0,work=0,private_commit_bytes=0)
    for group,r in reports.items():
        assert r['protected_files_unchanged']and not r['playable']
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for row in r['cases']:
            if group!='real':assert row['passed']
            pairs=list(zip(row['reports'],row['artifacts']))
            if row.get('stock_control')is not None:pairs.append((row['stock_control'],row['stock_artifact']))
            for p,a in pairs:
                assert p is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-menu-capture-1'and p['budget']['limit']==10000000 and p['budget']['used']<=10000000 and p['seconds']<5 and not p['game_started']and not p['full_trace_enabled']
                if'semantic'not in p:
                    assert group=='real'and not row['passed']and a['returncode']!=0;continue
                assert a['returncode']==0 and p['private_commit_bytes']<1024**3
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['private_commit_bytes']=max(maximum['private_commit_bytes'],p['private_commit_bytes'])
                for u in p['ui_vectors']:assert u['origin_bytes']<=262144 and not u['initialization_lua_trace_enabled']
                for g in p['sparse_provenance']:
                    if g is not None:assert g['audit_files_read']==0 and len(g['nodes'])<=4096 and g['bytes']<=1024**2
                if p['branch_views']['enabled']:
                    u=p['branch_views']['presentation_ui_vectors'];assert u['origin_bytes']<=262144 and not u['initialization_lua_trace_enabled']
                for step in p['steps']:
                    for draw in step.get('draws',[]):
                        if draw.get('op')!='sprite':continue
                        state=draw['capture_state'];ops=state['program'];assert ops[0]['op']=='Construct'and len(ops)<=128 and state['program_version']==len(ops)and not state['native_render_verified']
                        assert[o['order']for o in ops]==sorted({o['order']for o in ops})and any(o['op']=='Load'for o in ops)
                        assert all(len(i['sha256'])==64 for i in state['loaded_images'])
                        if not state['model_state_queryable']:assert state['model_root_frame']is None
            if row['passed']:
                left,right=row['reports'][-2:];assert left['semantic']==right['semantic']and left['steps']==right['steps']
    real=reports['real'];assert[c['passed']for c in real['cases']]==[True,True,False,False,False]
    for c in real['cases'][:2]:
        p=c['reports'][0];frames=[s['draws']for s in p['steps']if'draws'in s];assert[len(f)for f in frames]==[20,0,20]
        assert sum(d.get('op')=='sprite'for f in frames for d in f)==12 and sum(d.get('op')=='font'for f in frames for d in f)==28
        values=[s['values']for s in p['steps']if'values'in s];assert values[-2]==[dict(type='boolean',value=True)]and values[-1]==[dict(type='boolean',value=False)]
        assert p['semantic']['world']['coins']==0 and p['semantic']['world']['effects']==[]and len(p['semantic']['menu_snapshot']['entities'])>0
        text=[bytes.fromhex(d['text_hex']).decode('utf-8')for f in frames for d in f if d.get('op')=='font'];assert all(t in text for t in ['通用','Mod配置菜单','同步游戏设置: 是','ESCAPE','ENTER'])
    for c in real['cases'][2:4]:
        p=c['reports'][0];w=p['texture_state']['first_failure'];assert p['first_unsupported_entry']=='Frozen module path outside registered roots'and w['operation']==69
        assert w['arguments'][1]['integer']==0 and w['arguments'][2]['bytes_hex']==''
    p=real['cases'][4]['reports'][0];assert p['first_unsupported_entry']=='Font control character behavior unverified'and p['texture_state']['first_failure']['operation']==84 and p['texture_state']['first_failure']['arguments'][1]['bytes_hex']=='07'
    assert not load(ROOT/'reports/menu-capture-model-v1/result.json.gz')['passed']and not load(ROOT/'reports/menu-capture-model-v3/result.json.gz')['passed']
    return dict(integrity_verified=True,model_functional_or_recovery_cases=11,model_boundary_diagnostics=5,real_mcm_contract_cases=4,real_mcm_capture_cases_passed=2,real_eid_or_combined_capture_cases_failed=3,original_linked_model_gates_passed=2,unchanged_branch_cases=20,unchanged_world_api_cases=35,maximum_completed_child=maximum,full_real_ui_gate_passed=False,trusted_settings_purpose_implemented=False,configuration_sidecar_implemented=False,native_pixels_verified=False,general_mod_compatibility_gate_passed=False,long_session_memory_bounded=False,network_verified=False,playable=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args()
    if a.seal:
        if FINAL.exists():raise RuntimeError('Preserved seal already exists')
        summary=audit(False)
        with FINAL.open('x',encoding='utf-8')as f:json.dump(dict(schema='menu-capture-seal-1',abi='ia-lua533-menu-capture-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},**summary),f,indent=2);f.write('\n')
    print(json.dumps(audit()))
