"""Seal exact MCM callback auditing without promoting value forwarding or co-op."""
import argparse, contextlib, gzip, hashlib, io, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import verify_menu_capture as parent
import check_trusted_settings as driver
import freeze_trusted_settings as catalog
ROOT=driver.ROOT
FINAL=ROOT/'reports/trusted-settings-final.json'
REPORTS={
    'audit':ROOT/'reports/trusted-settings-audit-v5/result.json.gz',
    'stack':ROOT/'reports/trusted-settings-stack/result.json.gz',
    'real':ROOT/'reports/trusted-settings-real-v2/result.json.gz',
    'capture':ROOT/'reports/trusted-settings-capture-regressions-v2/result.json.gz',
    'branch':ROOT/'reports/trusted-settings-branch-regressions-v2/result.json.gz',
    'api':ROOT/'reports/trusted-settings-api-regressions-v2/result.json.gz',
    'original':ROOT/'reports/trusted-settings-original-gates-v2/result.json.gz',
}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    paths={Path(__file__),ROOT/'tools/check_trusted_settings.py',ROOT/'tools/freeze_trusted_settings.py',ROOT/'reports/menu-capture-final.json',ROOT/'docs/TRUSTED_SETTINGS_RESULTS.md'}
    d=ROOT/'build-trusted-settings/generated/derived_sha256.json'
    paths.add(d);derived=json.loads(d.read_text(encoding='utf-8'))
    for group in ['inputs','outputs']:paths.update(ROOT/p for p in derived[group])
    for folder in ['trusted_settings_runtime','research/trusted_settings']:
        paths.update(p for p in (ROOT/folder).rglob('*')if p.is_file())
    paths.update(REPORTS.values())
    paths.update((ROOT/'build-trusted-settings/Release')/name for name in ['authority-trusted-settings.exe','authority-trusted-settings-reference.exe'])
    for name in ['audit-v1','audit-v2','audit-v3','audit-v4']:
        paths.add(ROOT/('reports/trusted-settings-'+name+'/result.json.gz'))
    return sorted(paths)

def audit(require_seal=True):
    with contextlib.redirect_stdout(io.StringIO()):parent.audit()
    if require_seal:
        seal=json.loads(FINAL.read_text(encoding='utf-8'))
        for p,h in seal['files'].items():assert sha(ROOT/p)==h,('Changed sealed input',p)
        assert not seal['personal_value_forwarding_implemented']and not seal['playable']
    d=json.loads((ROOT/'build-trusted-settings/generated/derived_sha256.json').read_text(encoding='utf-8'))
    assert d['parent_final_sha256']==sha(ROOT/'reports/menu-capture-final.json')
    for group in ['inputs','outputs']:
        for p,h in d[group].items():assert sha(ROOT/p)==h
    profile=json.loads((ROOT/'research/trusted_settings/profile-v2.json').read_text(encoding='utf-8'))
    assert sha(ROOT/profile['source'])==profile['source_sha256']
    proof=load(ROOT/'research/trusted_settings/catalog-proof-v2.json.gz')
    assert proof['profile_sha256']==sha(ROOT/'research/trusted_settings/profile-v2.json')
    dumps=[[bytes.fromhex(v['hex'])for v in row['report']['steps'][0]['values']]for row in proof['pairs']]
    assert dumps[1]==dumps[2]
    names=['AddSetting','PostRender','ConvertDisplayToTextTable']
    protos={}
    for i,name in enumerate(names):
        assert dumps[0][2*i+1]==dumps[1][2*i+1]
        assert hashlib.sha256(dumps[1][2*i+1]).hexdigest()==profile['functions'][name]['sha256']
        protos[name]=catalog.Chunk(dumps[1][2*i]).root
    assert len(profile['sites'])==11 and len(profile['renderer_sites'])==47
    for s in profile['sites']:
        p=protos[s['caller']];assert p['code'][s['pc']]==s['instruction']and s['instruction']&63==36 and p['lines'][s['pc']]==s['line']
        assert profile['functions'][s['caller']]['sha256']==s['caller_sha256']
        if s['receiver_kind']=='upvalue':assert p['upvalues'][s['receiver_index']-1]==s['receiver_name']
        elif s['receiver_kind']=='local':
            active=[v for v in p['locals']if v['start']<=s['pc']<v['end']]
            assert active[s['receiver_index']-1]['name']==s['receiver_name']
        else:assert s['role']=='Info'and protos['PostRender']['upvalues'][profile['info_receiver_upvalue']-1]=='currentMenuOption'
    results={k:load(p)for k,p in REPORTS.items()}
    assert [len(results[k]['cases'])for k in REPORTS]==[16,1,2,16,20,35,2]
    assert all(r['passed']and r['protected_files_unchanged']and not r['playable']for r in results.values())
    maximum=dict(seconds=0,work=0,end_private_commit_bytes=0)
    specs={c['id']:c for c in json.loads(driver.MANIFEST.read_text(encoding='utf-8'))['cases']}
    for group,r in results.items():
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for row in r['cases']:
            checks=row['checks']
            assert row['passed']
            assert all(checks.values())if isinstance(checks,dict)else all(c['passed']for c in checks)
            for p,a in zip(row['reports'],row['artifacts']):
                assert p is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-trusted-settings-1'and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['budget']['used']<=10000000 and p['seconds']<5 and not p['game_started']and not p['full_trace_enabled']
                if 'semantic'not in p:
                    assert group=='audit'and specs[row['id']].get('fatal')and a['returncode']!=0
                    assert specs[row['id']]['fatal']in p['first_unsupported_entry'];continue
                assert a['returncode']==0 and p['private_commit_bytes']<1024**3
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['end_private_commit_bytes']=max(maximum['end_private_commit_bytes'],p['private_commit_bytes'])
                states=p['settings_audit']+[s for s in p['steps']if'registered_objects'in s]
                if p['branch_views']['enabled']:states.append(p['branch_views']['presentation_settings'])
                for state in states:
                    assert state['active_scopes']==0 and state['entries']==state['returns']and state['registered_objects']<=256
                    assert not state['personal_result_forwarding_implemented']and not state['configuration_sidecar_implemented']
                    assert len(state['proofs'])<=512
                    for event in state['proofs']:
                        if event['kind']=='settings-enter':
                            assert event['identity_matched']and len(event['callee_source_sha256'])==64
                            assert any(s['caller_sha256']==event['caller_sha256']and s['pc']==event['pc']and s['role']==event['role']for s in profile['sites'])
                        elif event['kind']=='settings-return':assert event['actual_arity']==len(event['values'])and not event['return_rewritten']
                        else:raise AssertionError(event['kind'])
                for g in p['sparse_provenance']:
                    if g is not None:assert g['audit_files_read']==0 and len(g['nodes'])<=4096 and g['bytes']<=1024**2
            left,right=row['reports'][-2:]
            if'semantic'in left:assert left['semantic']==right['semantic']and left['steps']==right['steps']and left['settings_audit']==right['settings_audit']
    rows={r['id']:r for r in results['audit']['cases']}
    r=rows['real-framework-navigation-change-and-info']['reports'][0]
    state=next(s for s in r['steps']if'registered_objects'in s)
    assert {e['role']for e in state['proofs']}=={'CurrentSetting','OnChange','Display','Info'}
    stores=r['semantic']['mod_stores'];assert [json.loads(bytes.fromhex(stores[i][driver.OWNER]['data_hex']))['amount']for i in range(2)]==[1,3]
    for c in results['real']['cases']:
        r=c['reports'][0];assert r['settings_audit'][0]['entries']==0 and r['settings_audit'][1]['entries']==12
        assert all(not d.get('settings_audit',{}).get('settings_context_granted',False)for s in r['steps']for d in s.get('draws',[]))
        assert r['semantic']['world']['coins']==0 and not r['semantic']['world']['effects']and r['semantic']['menu_snapshot']['entities']
    # Preserve why earlier checks failed; they are not changed into green history.
    assert not load(ROOT/'reports/trusted-settings-audit-v1/result.json.gz')['passed']
    assert not load(ROOT/'reports/trusted-settings-audit-v2/result.json.gz')['passed']
    return dict(integrity_verified=True,real_framework_call_identity_audit_passed=True,
        identity_and_behavior_cases=13,explicit_refusal_diagnostics=3,deep_stack_equivalence_cases=1,
        real_mcm_two_and_three_context_capture_cases=2,unchanged_regression_cases=73,
        maximum_completed_child=maximum,personal_value_forwarding_implemented=False,
        full_setting_return_purpose_propagation_implemented=False,configuration_sidecar_implemented=False,
        full_real_ui_gate_passed=False,native_pixels_verified=False,long_session_memory_bounded=False,
        general_mod_compatibility_gate_passed=False,network_verified=False,playable=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seal',action='store_true');args=parser.parse_args()
    if args.seal:
        assert not FINAL.exists(),'Seal is immutable'
        summary=audit(False)
        with FINAL.open('x',encoding='utf-8')as out:
            json.dump(dict(schema='trusted-settings-audit-seal-1',abi='ia-lua533-trusted-settings-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},**summary),out,indent=2);out.write('\n')
    print(json.dumps(audit()))
