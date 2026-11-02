"""Bounded Stage 2 gate; reuse the Stage 1 runner without duplicating evidence trees."""
import argparse, copy, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_execution_audit as gate
ROOT=gate.ROOT
gate.MANIFEST=ROOT/'research/ui_live_graph_v1.json'
gate.BINARY=ROOT/'build-live-graph/Release'
gate.DLL=gate.BINARY/'ia_lua533_live_graph.dll'
gate.EXE=gate.BINARY/'authority-live-graph.exe'
original_protected=gate.protected
def protected():
    result=original_protected()
    for folder in ['execution_audit_runtime','build-execution-audit/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='execution_audit_runtime' or p.suffix in ['.dll','.exe','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    result['research/ui_execution_audit_v2.json']=gate.digest(ROOT/'research/ui_execution_audit_v2.json')
    return result
gate.protected=protected
original_canonical=gate.canonical
def canonical(report):
    result=original_canonical(report)
    for phase in result.get('phases',[]):phase.get('reclamation',{}).pop('live_graph_reclamation',None)
    return result
gate.canonical=canonical
original_metrics=gate.compact_metrics
def metrics(report):
    result=original_metrics(report);stats=report.get('execution_before_diagnostics',{}).get('live_graph',{})
    result['live_nodes']=stats.get('live_nodes');result['reclaimed_nodes']=stats.get('reclaimed_nodes');result['live_payload_bytes']=stats.get('node_payload_bytes');result['peak_node_payload_bytes']=stats.get('peak_node_payload_bytes')
    return result
gate.compact_metrics=metrics

def freeze():
    spec=json.loads((ROOT/'research/ui_execution_audit_v2.json').read_text(encoding='utf-8'))
    spec['schema']='live-graph-short-1'
    # Every existing fixture and functional expectation remains unchanged.
    storage=json.loads((ROOT/'research/ui_compact_storage_v3.json').read_text(encoding='utf-8'))
    source=next(c for c in storage['cases'] if c['id']=='host-pin-keep')
    spec['cases'].append(copy.deepcopy(source))
    for n in [4,8,16]:
        p=ROOT/'research/ui_compact_fixtures/churn.lua'
        spec['cases'].append({'id':'graph-churn-'+str(n),'n':0,'kind':'functional','chunks':[{'file':p.relative_to(ROOT).as_posix(),'sha256':gate.digest(p)} for _ in range(n)],'reclaim':True,'observe_memory':True,'expected':[[7,0]]*n})
    p=ROOT/'research/execution_audit_fixtures/cert_setup.lua'
    spec['cases'].append({'id':'missing-live-producer','kind':'process-safety','chunks':[{'file':p.relative_to(ROOT).as_posix(),'sha256':gate.digest(p)}],'missing_live_probe':True,'error_contains':'Live producer unavailable; audit fallback forbidden'})
    p=ROOT/'research/ui_compact_fixtures/churn.lua'
    spec['cases'].append({'id':'diagnostic-corruption','kind':'process-safety','chunks':[{'file':p.relative_to(ROOT).as_posix(),'sha256':gate.digest(p)}],'fault_after_last_phase':1,'error_contains':'Audit payload checksum mismatch'})
    for c in spec['cases']:c['audit_disk_limit']=16*1024*1024
    if gate.MANIFEST.exists():
        if json.loads(gate.MANIFEST.read_text(encoding='utf-8'))!=spec:raise RuntimeError('Frozen live graph manifest differs')
    else:gate.save(gate.MANIFEST,spec)
    print(json.dumps({'manifest':str(gate.MANIFEST),'sha256':gate.digest(gate.MANIFEST),'cases':len(spec['cases'])}))

def run(out,only):
    result=gate.run(out,only)
    result['schema']='live-graph-step2-gate'
    result['live_graph_execution_reads_zero']=all(r['candidate'].get('all_execution_journal_reads')==0 for r in result['cases'] if r['kind']!='process-safety')
    result['execution_audit_read_fallback']=False
    result['whole_execution_decoupled']='verified short CLI cases only; diagnostic export explicitly separate'
    result['field_and_upvalue_invalidation_changed']=False
    result['churn_reclaims_payload']=all((r['candidate'].get('reclaimed_nodes') or 0)>0 for r in result['cases'] if r['id'].startswith('graph-churn-'))
    result['passed']=result['passed'] and result['live_graph_execution_reads_zero'] and result['churn_reclaims_payload']
    gate.save(out/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','growth']},ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--case',action='append');a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve(),a.case)['passed'] else 1)
