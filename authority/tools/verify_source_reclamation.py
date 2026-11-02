"""Verify live graph progress while retaining the required long-chain failure."""
import argparse,contextlib,copy,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_source_reclamation as driver
import check_settings_value as core
import verify_trusted_settings as parent
ROOT=core.ROOT;CHECKPOINT=ROOT/'reports/source-reclamation-progress.json'
REPORTS={
 'values':'source-reclamation-values-v1','saves':'source-reclamation-saves-v2',
 'roots':'source-reclamation-roots-v2','stress':'source-reclamation-stress-v1',
 'branch':'source-reclamation-branch-regressions','original':'source-reclamation-original-gates',
 'controls':'source-reclamation-controls','real':'source-reclamation-real-mcm',
 'capture':'source-reclamation-capture-regressions','api':'source-reclamation-api-regressions',
 'storage':'source-reclamation-storage-regressions','natives':'source-reclamation-natives',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    paths={Path(__file__),ROOT/'tools/check_source_reclamation.py',ROOT/'tools/check_settings_value.py',ROOT/'tools/check_settings_serialization.py',ROOT/'tools/check_settings_natives.py',ROOT/'docs/SOURCE_RECLAMATION_RESULTS.md',ROOT/'reports/trusted-settings-final.json',core.EXE,core.REF}
    derived=ROOT/'build-settings-value/generated/derived_sha256.json';paths.add(derived)
    d=json.loads(derived.read_text(encoding='utf-8'))
    for group in ['inputs','outputs']:paths.update(ROOT/p for p in d[group])
    for folder in ['settings_value_runtime','research/settings_value']:paths.update(p for p in(ROOT/folder).rglob('*')if p.is_file())
    paths.update(ROOT/'reports'/name/'result.json.gz'for name in REPORTS.values())
    paths.update([ROOT/'reports/source-reclamation-roots-v1/result.json.gz',ROOT/'reports/source-reclamation-explicit-gc-diagnostic.json.gz'])
    return sorted(paths)
def stable_steps(p):
    steps=copy.deepcopy(p['steps'])
    for row in steps:
        if'collections'in row and'scanned_slots'in row:
            row.pop('scanned_slots')
            if row.get('last')is not None:row['last']['scan'].pop('slots')
    return steps
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
    for group in ['inputs','outputs']:
        for p,h in d[group].items():assert sha(ROOT/p)==h
    for binary in [core.EXE,core.REF]:
        raw=binary.read_bytes();pe=int.from_bytes(raw[60:64],'little');assert raw[pe:pe+4]==b'PE\0\0'and int.from_bytes(raw[pe+4:pe+6],'little')==0x14c
    reports={k:load(ROOT/'reports'/v/'result.json.gz')for k,v in REPORTS.items()}
    assert[len(reports[k]['cases'])for k in REPORTS]==[7,14,6,1,20,2,2,2,16,35,28,2]
    maximum=dict(seconds=0,work=0,end_private_commit_bytes=0)
    for group,r in reports.items():
        assert r['passed']==(group!='stress')and r['protected_files_unchanged']and not r['playable']
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for row in r['cases']:
            assert row['passed']==(group!='stress')
            if row['passed']:
                checks=row['checks'];assert all(checks.values())if isinstance(checks,dict)else all(c['passed']for c in checks)
            for p,a in zip(row['reports'],row['artifacts']):
                assert p is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-settings-value-1'and p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['budget']['used']<=10000000 and p['seconds']<5 and not p['game_started']and not p['full_trace_enabled']
                if group=='stress':
                    assert a['returncode']!=0 and p['first_unsupported_entry']=='Live value-object capacity exceeded'and'semantic'not in p
                    continue
                assert a['returncode']==0 and p['private_commit_bytes']<1024**3
                maximum['seconds']=max(maximum['seconds'],p['seconds']);maximum['work']=max(maximum['work'],p['budget']['used']);maximum['end_private_commit_bytes']=max(maximum['end_private_commit_bytes'],p['private_commit_bytes'])
                graphs=p['sparse_provenance']+([p['branch_views']['presentation_sources']]if p['branch_views']['enabled']else[])
                for graph in graphs:
                    if graph is not None:assert graph['stable_nonreused_ids']and graph['audit_files_read']==0 and graph.get('node_count',len(graph.get('nodes',[])))<=4096 and graph['bytes']<=1024**2
                if group in ['values','saves','roots']:
                    states=p['source_collection'];assert all(s['enabled']and s['active_nodes']<=4096 and not s['full_session_memory_bounded']for s in states.values())
                    for s in states.values():
                        if s['last']is not None:assert s['last']['stable_nonreused_ids']and not s['last']['audit_history_read']and not s['last']['scan']['lua_gc_forced']and not s['last']['scan']['lua_callbacks_executed']
            if row['passed']:
                a,b=row['reports'][-2:];assert a['semantic']==b['semantic']and stable_steps(a)==stable_steps(b)
    saves=reports['saves']['cases'];assert sum(c['boundary_diagnostic']for c in saves)==7 and all(c['passed']for c in saves)
    six=next(c for c in saves if c['id']=='serialization-six-frame-changes')['reports']
    for p in six:
        normal=json.loads(bytes.fromhex(p['semantic']['mod_stores'][1][core.OWNER]['data_hex']));game=json.loads(bytes.fromhex(p['branch_views']['presentation_stores'][core.OWNER]['data_hex']))
        assert normal['amount']==game['amount']==8 and normal['private']==20 and game['private']==10 and p['semantic']['world']['coins']==1 and len(p['semantic']['world']['effects'])==1
        assert p['source_collection']['personal']['retired_nodes']>4096 and p['source_collection']['presentation']['retired_nodes']>4096
    root=next(c for c in reports['roots']['cases']if c['id']=='source-roots-pool-invariants')['reports'][0]
    assert all(next(s for s in root['steps']if'retired-reference-refuses'in s).values())
    diagnostic=load(ROOT/'reports/source-reclamation-explicit-gc-diagnostic.json.gz')
    assert diagnostic['diagnostic_only']and diagnostic['explicit_lua_gc_inserted']and not diagnostic['fulfills_unmodified_execution_requirement']and not diagnostic['bounded_completed']and not diagnostic['playable']
    assert diagnostic['report']['first_unsupported_entry']=='Timeline provenance depth exceeded'
    p=diagnostic['report'];a=diagnostic['artifact'];assert a['returncode']!=0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p['seconds']<5 and p['budget']['limit']==10000000 and p['budget']['used']<=10000000 and not p['game_started']and not p['full_trace_enabled']
    for p,h in diagnostic['binaries'].items():assert sha(ROOT/p)==h
    assert not load(ROOT/'reports/source-reclamation-roots-v1/result.json.gz')['passed']
    return dict(integrity_verified=True,abi='ia-lua533-settings-value-1',mcm_functional_cases=7,save_functional_cases=7,save_refusal_recovery_diagnostics=7,live_root_cases=6,unchanged_regression_cases=101,native_scalar_contract_cases=2,real_mcm_capture_cases=2,boundary_diagnostics=2,maximum_completed_child=maximum,source_root_reclamation_small_cases_passed=True,required_bounded_stress_failure='serialization-ten-frame-changes: Live value-object capacity exceeded',explicit_gc_diagnostic_failure='Timeline provenance depth exceeded',sustained_execution_gate_passed=False,full_real_ui_gate_passed=False,long_session_memory_bounded=False,configuration_reload_sidecar_implemented=False,arbitrary_mod_compatibility=False,native_pixels_verified=False,network_verified=False,playable=False)
def main(record=False):
    if record:
        summary=audit(False);CHECKPOINT.write_text(json.dumps(dict(schema='source-reclamation-mutable-checkpoint-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},**summary),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit()))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--record',action='store_true');args=p.parse_args();main(args.record)
