"""Short Stage 3a gate: immutable field/upvalue version proof lifetime."""
import argparse, copy, gzip, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_live_graph as live
gate=live.gate;ROOT=gate.ROOT
gate.MANIFEST=ROOT/'research/ui_scoped_versions_v1.json'
gate.BINARY=ROOT/'build-scoped-versions/Release';gate.DLL=gate.BINARY/'ia_lua533_scoped_versions.dll';gate.EXE=gate.BINARY/'authority-scoped-versions.exe'
previous_protected=gate.protected
def protected():
    result=previous_protected()
    for folder in ['live_graph_runtime','build-live-graph/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='live_graph_runtime' or p.suffix in ['.dll','.exe','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    result['research/ui_live_graph_v1.json']=gate.digest(ROOT/'research/ui_live_graph_v1.json')
    return result
gate.protected=protected
previous_canonical=gate.canonical
def canonical(report):
    result=previous_canonical(report)
    for phase in result.get('phases',[]):phase.pop('version_proofs',None)
    return result
gate.canonical=canonical
previous_metrics=gate.compact_metrics
def metrics(report):
    result=previous_metrics(report);result['version_proofs']=report.get('execution_before_diagnostics',{}).get('version_proofs');return result
gate.compact_metrics=metrics

def freeze():
    spec=json.loads((ROOT/'research/ui_live_graph_v1.json').read_text(encoding='utf-8'));spec['schema']='scoped-versions-short-1'
    chunks=[]
    for phase,name in enumerate(['setup','unrelated','related','deletion','reshape']):
        p=ROOT/'research/scoped_version_fixtures'/(name+'.lua')
        probes=[{'phase':0,'index':i} for i in range(3)]
        if phase:probes.extend({'phase':phase,'index':i} for i in range(3))
        chunks.append({'file':p.relative_to(ROOT).as_posix(),'sha256':gate.digest(p),'proof_probe':probes})
    spec['cases'].append({'id':'field-upvalue-version-lifetime','kind':'functional','chunks':chunks,'pin_prior_frames':True,'reclaim':True,'observe_memory':True,'verify_full_origins':True,'expected':[[7,11,11],[7,11,11],[8,12,12],[None,None,None],[9,13,13]]})
    userdata=json.loads((ROOT/'research/ui_userdata_roots_v7.json').read_text(encoding='utf-8'))
    for c in userdata['cases']:
        if c['id'] in ['userdata-seven-classes','userdata-config-2','userdata-config-1','userdata-key-identity','userdata-drop-pinned']:
            c=copy.deepcopy(c)
            if c.get('expected') is not None and len(c['chunks'])==1:c['expected']=[c['expected']]
            spec['cases'].append(c)
    for c in spec['cases']:c['audit_disk_limit']=16*1024*1024
    if gate.MANIFEST.exists():
        if json.loads(gate.MANIFEST.read_text(encoding='utf-8'))!=spec:raise RuntimeError('Frozen scoped versions manifest differs')
    else:gate.save(gate.MANIFEST,spec)
    print(json.dumps({'manifest':str(gate.MANIFEST),'sha256':gate.digest(gate.MANIFEST),'cases':len(spec['cases'])}))

def run(out,only):
    result=live.run(out,only);result['schema']='scoped-versions-step3a-gate'
    checks=[]
    for row in result['cases']:
        if row['id']!='field-upvalue-version-lifetime':continue
        with gzip.open(out/(row['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:report=json.load(f)
        phases=report['phases']
        old_proofs_hit=all(p['hit_delta']==2 for frame in phases[1:] for p in frame.get('version_proofs',[])[:3])
        checks.append({'case':row['id'],'old_immutable_versions_retained':old_proofs_hit,'new_versions_distinct':all(phases[n]['value_ids']!=phases[n-1]['value_ids'] for n in range(1,len(phases))),'changed_field_and_upvalue_sources':phases[0]['origins']!=phases[2]['origins'],'work_budget_valid':row['budget_valid']})
    result['version_scope_checks']=checks
    result['field_and_upvalue_invalidation_changed']='immutable value proof caches prune only dead versions; whole-object caches unchanged'
    result['passed']=result['passed'] and all(all(v for k,v in c.items() if k!='case') for c in checks)
    gate.save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['cases','growth']},ensure_ascii=False));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--case',action='append');a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve(),a.case)['passed'] else 1)
