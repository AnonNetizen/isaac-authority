"""Verify source/binary integrity plus the actual limited sparse-observer claims."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];FINAL=ROOT/'reports/sparse-values-final.json'
import verify_world_view
import analyze_sparse_sources

REPORTS={
 'source':ROOT/'reports/sparse-values-v3/result.json.gz',
 'regressions':ROOT/'reports/sparse-values-world-regressions-v2/result.json.gz',
 'init':ROOT/'reports/sparse-values-real-init-v2/result.json.gz',
 'required_hud':ROOT/'reports/sparse-values-required-v1/projection/result.json.gz',
 'required_mixed':ROOT/'reports/sparse-values-required-v1/mixed/result.json.gz',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def input_paths():
    derived=ROOT/'build-sparse-value/generated/derived_sha256.json';d=json.loads(derived.read_text())
    result={derived,ROOT/'reports/world-view-final.json',ROOT/'docs/SPARSE_VALUE_RESULTS.md',ROOT/'reports/sparse-values-source-anchors.json'}
    result.update(ROOT/p for p in d['inputs']);result.update(ROOT/p for p in d['outputs'])
    names=['sparse_value_runtime','world_view_runtime','menu_runtime','ui_flow_runtime','font_capture_runtime','font_runtime','callback_runtime','texture_runtime','sprite_state_runtime','engine_services_runtime','value_object_runtime','sdk_runtime','object_runtime','module_runtime','compact_value_runtime','read_set_runtime']
    for name in names:
        result.update(p for p in (ROOT/name).iterdir()if p.is_file()and(p.suffix in ['.py','.c','.cpp','.h','.hpp','.inc']or p.name=='CMakeLists.txt'))
    result.update(p for p in (ROOT/'build-world-view/generated').iterdir()if p.suffix in ['.c','.h','.cpp','.hpp','.inc'])
    result.update(p for p in (ROOT/'research/sparse_value').rglob('*')if p.is_file())
    for name in ['check_sparse_values.py','check_sparse_required.py','analyze_sparse_sources.py','verify_sparse_values.py','bounded_font_process.py','run_world_view.py']:
        result.add(ROOT/'tools'/name)
    result.update([ROOT/'compact_read_runtime/draw_site.c',ROOT/'build-boundary/Release/boundary_lua.lib',ROOT/'build-ui-incremental-encoded/Release/authority_core.lib'])
    result.update((ROOT/'build-sparse-value/Release')/p for p in ['authority-sparse-value.exe','authority-sparse-value-reference.exe','sparse_lua.lib'])
    result.update(REPORTS.values());return sorted(result)

def verify():
    with contextlib.redirect_stdout(io.StringIO()):verify_world_view.main()
    seal=json.loads(FINAL.read_text())
    for name,hash in seal['files'].items():assert sha(ROOT/name)==hash,('Changed sealed input',name)
    reports={name:load(p)for name,p in REPORTS.items()}
    assert all(reports[n]['passed']for n in ['source','regressions','init'])
    assert [len(reports[n]['cases'])for n in ['source','regressions','init']]==[12,35,3]
    maxima=dict(seconds=0,work=0,private_commit_bytes=0)
    for name,d in reports.items():
        for binary,h in d['binaries'].items():assert sha(ROOT/binary)==h
        for c in d['cases']:
            if name in ['source','regressions','init']:
                assert c['passed']
                left,right=c['reports'][-2:]
                assert left['semantic']==right['semantic']and left['sparse_provenance']==right['sparse_provenance']
            for r,a in zip(c['reports'],c['artifacts']):
                assert r and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert r['budget']['limit']==10000000 and r['budget']['used']<=10000000
                assert not r['game_started']and not r['full_trace_enabled']
                if'semantic'not in r:continue
                assert r['abi']=='ia-lua533-sparse-value-1'
                assert r['seconds']<5 and r['private_commit_bytes']<1024**3
                assert not r['automatic_projection_implemented']and not r['personal_draws_publishable']
                maxima['seconds']=max(maxima['seconds'],r['seconds']);maxima['work']=max(maxima['work'],r['budget']['used']);maxima['private_commit_bytes']=max(maxima['private_commit_bytes'],r['private_commit_bytes'])
                for g in r['sparse_provenance']:
                    if g is None:continue
                    assert len(g['nodes'])<=4096 and g['bytes']<=1024**2 and g['audit_files_read']==0
                    assert not g['projection_implemented']and not g['field_write_identity_complete']
                    for n in g['nodes']:
                        assert all(a['tag']<n['id']for a in n.get('args',[]))
                    for s in g['sinks']:assert not s['semantic_correspondence_proven']
    assert not reports['required_hud']['passed']and not reports['required_mixed']['passed']
    hud=reports['required_hud']['cases'][0]
    assert [c['check']for c in hud['checks']if not c['passed']]==['exact-hud']
    mixed=reports['required_mixed']['cases'][0]
    assert mixed['reports'][1]['first_unsupported_entry']=='World write requires authority phase'
    actual=analyze_sparse_sources.analyze(next(c['reports'][1]for c in reports['regressions']['cases']if c['id']=='authority-reward-personal-config'))
    assert actual==json.loads((ROOT/'reports/sparse-values-source-anchors.json').read_text())
    assert len(actual['candidates'])==1 and not actual['world_projection_gate_passed']
    summary=dict(integrity_verified=True,sparse_observation_cases=12,unchanged_world_api_cases=35,real_source_initialization_cases=3,required_functional_failures=2,source_anchor_candidates=1,maximum_completed_child=maxima,world_projection_gate_passed=False,playable=False)
    print(json.dumps(summary));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args()
    if a.seal:
        if FINAL.exists():raise RuntimeError('Preserved seal already exists')
        FINAL.write_text(json.dumps(dict(schema='sparse-values-seal-1',abi='ia-lua533-sparse-value-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in input_paths()},world_projection_gate_passed=False,playable=False),indent=2)+'\n')
    verify()
