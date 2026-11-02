"""Verify finite lifecycle progress, not a playable or arbitrary-mod claim."""
import argparse,contextlib,gzip,hashlib,io,json,sys,unittest
from pathlib import Path
sys.dont_write_bytecode=True
import check_native_pressure as driver
import check_settings_value as core
import verify_trusted_settings as parent
import test_shared_draw_audit as codec_tests
ROOT=core.ROOT;CHECKPOINT=ROOT/'reports/native-pressure-progress.json'
REPORTS={
 'stress':'native-pressure-stress-v4','codec':'native-pressure-codec-v2',
 'contracts':'native-pressure-contracts-v3','values':'native-pressure-values-v1',
 'saves':'native-pressure-saves-v1','roots':'native-pressure-roots-v1',
 'branch':'native-pressure-branch-regressions','original':'native-pressure-original-gates',
 'controls':'native-pressure-controls','real':'native-pressure-real-mcm',
 'capture':'native-pressure-capture-regressions','api':'native-pressure-api-regressions',
 'storage':'native-pressure-storage-regressions','natives':'native-pressure-natives',
 'init':'native-pressure-real-init',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    paths={Path(__file__),ROOT/'docs/NATIVE_PRESSURE_RESULTS.md',ROOT/'reports/trusted-settings-final.json',core.EXE,core.REF}
    paths.update(ROOT/'tools'/p for p in ['check_native_pressure.py','check_source_reclamation.py','check_settings_value.py','check_settings_serialization.py','check_settings_natives.py','shared_draw_audit.py','test_shared_draw_audit.py'])
    dpath=ROOT/'build-settings-value/generated/derived_sha256.json';paths.add(dpath)
    derived=json.loads(dpath.read_text(encoding='utf-8'))
    for key in ['inputs','outputs']:paths.update(ROOT/p for p in derived[key])
    for folder in ['settings_value_runtime','research/settings_value']:paths.update(p for p in(ROOT/folder).rglob('*')if p.is_file())
    paths.update(ROOT/'reports'/p/'result.json.gz'for p in REPORTS.values())
    for p in ['native-pressure-stress-v1','native-pressure-stress-v2','native-pressure-stress-v3','native-pressure-codec-v1','native-pressure-contracts-v1','native-pressure-contracts-v2','source-reclamation-stress-v1']:paths.add(ROOT/'reports'/p/'result.json.gz')
    return sorted(paths)
def audit(checkpoint=True):
    argv=sys.argv
    try:
        sys.argv=[argv[0]]
        with contextlib.redirect_stdout(io.StringIO()):parent.audit()
    finally:sys.argv=argv
    if checkpoint:
        for p,h in json.loads(CHECKPOINT.read_text(encoding='utf-8'))['files'].items():assert sha(ROOT/p)==h,('Stale research checkpoint',p)
    d=json.loads((ROOT/'build-settings-value/generated/derived_sha256.json').read_text(encoding='utf-8'))
    assert d['parent_final_sha256']==sha(ROOT/'reports/trusted-settings-final.json')
    for key in ['inputs','outputs']:
        for p,h in d[key].items():assert sha(ROOT/p)==h
    for exe in [core.EXE,core.REF]:
        data=exe.read_bytes();pe=int.from_bytes(data[60:64],'little');assert data[pe:pe+4]==b'PE\0\0'and int.from_bytes(data[pe+4:pe+6],'little')==0x14c
    counts=dict(zip(REPORTS,[1,1,4,7,14,6,20,2,2,2,16,35,28,2,3]));reports={}
    maximum=dict(seconds=0,work=0,end_private_commit_bytes=0)
    for group,name in REPORTS.items():
        r=load(ROOT/'reports'/name/'result.json.gz');assert len(r['cases'])==counts[group]
        if group in ['stress','codec','contracts']:reports[group]=r
        assert r['passed']and r['protected_files_unchanged']and not r['playable']
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for row in r['cases']:
            assert row['passed'];checks=row['checks'];assert all(checks.values())if isinstance(checks,dict)else all(c['passed']for c in checks)
            pairs=list(zip(row['artifacts'],row['reports']))
            if row.get('stock_control')is not None:pairs.append((row['stock_artifact'],row['stock_control']))
            for a,p in pairs:
                assert p is not None and a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-settings-value-1'and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['budget']['used']<=10000000 and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['end_private_commit_bytes']=max(maximum['end_private_commit_bytes'],p['private_commit_bytes'])
                for state in p['native_value_pressure'].values():
                    if state is None:continue
                    assert state['registry_limit']==1024 and state['user_gc_stop_respected']and not state['custom_native_finalizer_supported']
                    if state['last']is not None:assert state['last']['finalizers_invoked_by_pressure']==0 and state['last']['policy']=='lua533-emergency-deferred-finalizers-1'
                graphs=p['sparse_provenance']+([p['branch_views']['presentation_sources']]if p['branch_views']['enabled']else[])
                for graph in graphs:
                    if graph is not None:assert graph['audit_files_read']==0 and graph.get('node_count',len(graph.get('nodes',[])))<=4096 and graph['bytes']<=1024**2
    stress=reports['stress']['cases'][0]
    assert stress['id']=='serialization-ten-frame-changes'
    for p in stress['reports']:
        normal=json.loads(bytes.fromhex(p['semantic']['mod_stores'][1][core.OWNER]['data_hex']));game=json.loads(bytes.fromhex(p['branch_views']['presentation_stores'][core.OWNER]['data_hex']))
        assert normal['amount']==game['amount']==12 and normal['private']==20 and game['private']==10 and p['semantic']['world']['coins']==1 and len(p['semantic']['world']['effects'])==1
        for key in ['personal','presentation']:
            pressure=p['native_value_pressure'][key];assert pressure['enabled']and pressure['cycles']>0 and pressure['retired_registrations']>0
            incremental=p['source_collection'][key]['incremental_fingerprints'];assert incremental['persistent_storage_only']and incremental['dependency_depth_limit']==64 and incremental['fingerprints_computed']>0
        transport=p['draw_audit_transport'];assert transport['self_round_trip_verified']and transport['dictionary_bytes']<=2*1024**2 and transport['expanded_frame_byte_bound']<=16*1024**2
    contracts={c['id']:c for c in reports['contracts']['cases']}
    for row in contracts.values():assert row['checks']['world-and-saves-not-changed-by-pressure']
    deferred=contracts['native-pressure-deferred-finalizers']['reports'][0]
    assert deferred['native_value_pressure']['personal']['last']['pending_finalizers_after']>0
    assert contracts['native-pressure-gc-stop']['reports'][0]['native_value_pressure']['personal']['cycles']==0
    assert contracts['native-pressure-failure-restore']['checks']['failed-pressure-rebuilds-history']
    assert contracts['native-pressure-native-finalizer-aba-refuses']['checks']['pcall-cannot-hide-finalizer-mutation']
    codec=reports['codec']['cases'][0];assert codec['checks']['exact-restored-draw-values-config-and-proofs']
    suite=unittest.defaultTestLoader.loadTestsFromModule(codec_tests);test_result=unittest.TextTestRunner(stream=io.StringIO()).run(suite);assert test_result.wasSuccessful()and test_result.testsRun==9
    for old in ['native-pressure-stress-v1','native-pressure-stress-v2','source-reclamation-stress-v1']:assert not load(ROOT/'reports'/old/'result.json.gz')['passed']
    return dict(integrity_verified=True,abi='ia-lua533-settings-value-1',ten_menu_changes_finite_gate_passed=True,native_lifecycle_contracts=4,decoder_safety_checks=9,shared_audit_content_equivalence=True,real_initialization_cases=3,unchanged_regression_cases=101,maximum_completed_child=maximum,full_real_ui_gate_passed=False,long_session_memory_bounded=False,realtime_frame_performance_verified=False,configuration_reload_sidecar_implemented=False,custom_native_finalizer_supported=False,arbitrary_mod_compatibility=False,native_pixels_verified=False,network_verified=False,playable=False)
def main(record=False):
    if record:
        summary=audit(False);CHECKPOINT.write_text(json.dumps(dict(schema='native-pressure-mutable-checkpoint-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},**summary),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit()))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--record',action='store_true');args=p.parse_args();main(args.record)
