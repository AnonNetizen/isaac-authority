"""Check a partial research candidate, including its required capacity failure."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_settings_value as core
import check_settings_serialization as saving
import verify_trusted_settings as parent
ROOT=core.ROOT;CHECKPOINT=ROOT/'reports/settings-value-progress.json'
REPORTS={
 'functional':'settings-value-functional-v8',
 'serialization':'settings-value-serialization-v2',
 'controls':'settings-value-controls-v8',
 'natives':'settings-value-natives-v4',
 'real':'settings-value-real-v6',
 'capture':'settings-value-capture-regressions-v3',
 'branch':'settings-value-branch-regressions-v4',
 'api':'settings-value-api-regressions-v3',
 'storage':'settings-value-storage-regressions-v2',
 'original':'settings-value-original-gates-v4',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def files():
    paths={Path(__file__),ROOT/'tools/check_settings_value.py',ROOT/'tools/check_settings_serialization.py',ROOT/'tools/check_settings_natives.py',ROOT/'docs/SETTINGS_VALUE_RESULTS.md',ROOT/'reports/trusted-settings-final.json',core.EXE,core.REF}
    derived=ROOT/'build-settings-value/generated/derived_sha256.json';paths.add(derived)
    d=json.loads(derived.read_text(encoding='utf-8'))
    for group in ['inputs','outputs']:paths.update(ROOT/p for p in d[group])
    for folder in ['settings_value_runtime','research/settings_value']:paths.update(p for p in(ROOT/folder).rglob('*')if p.is_file())
    paths.update(ROOT/'reports'/p/'result.json.gz'for p in REPORTS.values())
    return sorted(paths)

def audit(check_checkpoint=True):
    argv=sys.argv
    try:
        sys.argv=[argv[0]]
        with contextlib.redirect_stdout(io.StringIO()):parent.audit()
    finally:sys.argv=argv
    if check_checkpoint:
        checkpoint=json.loads(CHECKPOINT.read_text(encoding='utf-8'))
        for p,h in checkpoint['files'].items():assert sha(ROOT/p)==h,('Stale candidate checkpoint',p)
    derived=json.loads((ROOT/'build-settings-value/generated/derived_sha256.json').read_text(encoding='utf-8'))
    assert derived['parent_final_sha256']==sha(ROOT/'reports/trusted-settings-final.json')
    for group in ['inputs','outputs']:
        for p,h in derived[group].items():assert sha(ROOT/p)==h
    for binary in [core.EXE,core.REF]:
        raw=binary.read_bytes();pe=int.from_bytes(raw[60:64],'little');assert raw[pe:pe+4]==b'PE\0\0'and int.from_bytes(raw[pe+4:pe+6],'little')==0x14c
    reports={key:load(ROOT/'reports'/name/'result.json.gz')for key,name in REPORTS.items()}
    assert [len(reports[k]['cases'])for k in REPORTS]==[7,13,2,2,2,16,20,35,28,2]
    maximum=dict(seconds=0,work=0,end_private_commit_bytes=0)
    for group,r in reports.items():
        assert r['protected_files_unchanged']and not r['playable']
        assert r['passed']==(group!='serialization')
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for row in r['cases']:
            failed_capacity=group=='serialization'and row['id']=='serialization-second-frame'
            assert row['passed']!=failed_capacity
            checks=row['checks']
            if row['passed']:assert all(checks.values())if isinstance(checks,dict)else all(c['passed']for c in checks)
            for p,a in zip(row['reports'],row['artifacts']):
                assert p is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-settings-value-1'and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['budget']['used']<=10000000 and p['seconds']<5 and not p['game_started']and not p['full_trace_enabled']
                if failed_capacity:
                    assert a['returncode']!=0 and p['first_unsupported_entry']=='Sparse node capacity exceeded'and'semantic'not in p
                    continue
                assert a['returncode']==0 and p['private_commit_bytes']<1024**3
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['end_private_commit_bytes']=max(maximum['end_private_commit_bytes'],p['private_commit_bytes'])
                graphs=p['sparse_provenance']+([p['branch_views']['presentation_sources']]if p['branch_views']['enabled']else[])
                for graph in graphs:
                    if graph is not None:assert graph['audit_files_read']==0 and graph.get('node_count',len(graph.get('nodes',[])))<=4096 and graph['bytes']<=1024**2
            if row['passed']:
                left,right=row['reports'][-2:]
                assert left['semantic']==right['semantic']and left['steps']==right['steps']
    f=reports['functional']['cases'][-1]['reports'][0]
    saved=json.loads(bytes.fromhex(f['semantic']['mod_stores'][1][core.OWNER]['data_hex']));shadow=json.loads(bytes.fromhex(f['branch_views']['presentation_stores'][core.OWNER]['data_hex']))
    assert saved['amount']==shadow['amount']==3 and saved['private']==20 and shadow['private']==10
    controls=reports['controls']['cases'];assert all(c['boundary_diagnostic']and c['checks']['exact-explicit-refusal']for c in controls)
    specs={c['id']:c for c in json.loads(saving.MANIFEST.read_text(encoding='utf-8'))['cases']}
    functional=[c for c in reports['serialization']['cases']if not c['boundary_diagnostic']]
    refusals=[c for c in reports['serialization']['cases']if c['boundary_diagnostic']]
    assert len(functional)==6 and sum(c['passed']for c in functional)==5 and len(refusals)==7 and all(c['passed']for c in refusals)
    assert all(specs[c['id']]['required_compatibility']for c in functional)and all(not specs[c['id']]['required_compatibility']for c in refusals)
    # Old failure evidence remains a failure; it is not the current acceptance.
    for name in ['settings-value-functional-v4','settings-value-functional-v5','settings-value-controls-v3','settings-value-serialization-v1']:
        assert not load(ROOT/'reports'/name/'result.json.gz')['passed']
    return dict(integrity_verified=True,abi='ia-lua533-settings-value-1',actual_mcm_values_functional_passed=7,additional_save_functional_passed=5,additional_save_functional_required=6,save_refusal_and_recovery_diagnostics=7,boundary_diagnostics=2,native_scalar_contract_cases=2,real_mcm_capture_cases=2,unchanged_regression_cases=101,maximum_completed_child=maximum,required_failure='serialization-second-frame: Sparse node capacity exceeded',full_real_ui_gate_passed=False,configuration_reload_sidecar_implemented=False,long_session_memory_bounded=False,arbitrary_mod_compatibility=False,native_pixels_verified=False,network_verified=False,playable=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--record',action='store_true');a=p.parse_args()
    if a.record:
        summary=audit(False)
        CHECKPOINT.write_text(json.dumps(dict(schema='settings-value-mutable-checkpoint-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in files()},**summary),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit()))
