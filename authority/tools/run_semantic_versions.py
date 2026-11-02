"""Stage 3b bounded gate: separate physical layout and semantic invalidation."""
import argparse, copy, gzip, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_scoped_versions as scoped
gate=scoped.gate;ROOT=gate.ROOT
gate.MANIFEST=ROOT/'research/ui_scoped_versions_v2.json'
gate.BINARY=ROOT/'build-semantic-versions/Release';gate.DLL=gate.BINARY/'ia_lua533_semantic_versions.dll';gate.EXE=gate.BINARY/'authority-semantic-versions.exe'
previous_protected=gate.protected
def protected():
    result=previous_protected()
    for folder in ['scoped_versions_runtime','build-scoped-versions/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='scoped_versions_runtime' or p.suffix in ['.dll','.exe','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    result['research/ui_scoped_versions_v1.json']=gate.digest(ROOT/'research/ui_scoped_versions_v1.json')
    return result
gate.protected=protected
previous_canonical=gate.canonical
def canonical(report):
    result=previous_canonical(report)
    # Physical layout epochs remain recorded, but are not portable semantics.
    for o in (result.get('cache_evidence') or {}).get('objects',[]):o.pop('layout_version',None)
    for p in result.get('phases',[]):
        for value in p.get('snapshots',{}).values():value.pop('layout_version',None)
    return result
gate.canonical=canonical
def baseline_equal(first,old):
    a=canonical(copy.deepcopy(first));b=canonical(copy.deepcopy(old))
    # The fix intentionally changes content certificate versions/hits. Preserve
    # exact value/control provenance; validate new certificates by full oracle,
    # complete audit reconstruction and exact candidate repeat instead.
    for value in [a,b]:
        value.pop('cache_evidence',None)
        for phase in value.get('phases',[]):
            for snapshot in phase.get('snapshots',{}).values():
                snapshot.pop('version',None)
    return a==b
gate.baseline_equal=baseline_equal

def freeze():
    spec=json.loads((ROOT/'research/ui_scoped_versions_v1.json').read_text(encoding='utf-8'));spec['schema']='scoped-versions-short-2'
    originals=json.loads((ROOT/'research/ui_userdata_roots_v7.json').read_text(encoding='utf-8'))
    for c in spec['cases']:
        if c['id'].startswith('userdata-'):
            original=next(o for o in originals['cases'] if o['id']==c['id'])
            if 'expected' in original:c['expected']=[copy.deepcopy(original['expected']) for _ in c['chunks']]
        if c['kind']=='functional':c['verify_full_origins']=True
    spec['acceptance']['baseline_certificate_versions']='intentionally changed; exact value/control graph and observations required'
    spec['acceptance']['candidate_certificate_validation']='full traversal oracle, exact candidate repeat, full independent audit reconstruction'
    spec['acceptance']['layout_epochs']='physical diagnostic only; retained in raw reports'
    if gate.MANIFEST.exists():
        if json.loads(gate.MANIFEST.read_text(encoding='utf-8'))!=spec:raise RuntimeError('Frozen semantic versions manifest differs')
    else:gate.save(gate.MANIFEST,spec)
    print(json.dumps({'manifest':str(gate.MANIFEST),'sha256':gate.digest(gate.MANIFEST),'cases':len(spec['cases'])}))

def run(out,only):
    result=scoped.run(out,only);result['schema']='scoped-versions-step3b-gate'
    result['baseline_comparison']='exact observations/origins/value/control graph; semantic certificate versions intentionally changed'
    result['full_oracle_functional_cases']=[]
    for row in result['cases']:
        if row['kind']!='functional':continue
        with gzip.open(out/(row['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:r=json.load(f)
        inc=r.get('trace',{}).get('incremental',{})
        check=inc.get('full_oracle_enabled') is True and inc.get('full_oracle_checks',0)>0
        result['full_oracle_functional_cases'].append({'id':row['id'],'passed':check,'checks':inc.get('full_oracle_checks'),'calls':inc.get('full_oracle_calls')})
        if row['id'].startswith('userdata-config-'):
            c=next(c for c in json.loads(gate.MANIFEST.read_text())['cases'] if c['id']==row['id'])
            check=check and all([v.get('value') for v in p['views']]==[c['authority'],137,'en','amount='+str(c['authority'])] for p in r['phases'])
        row['full_oracle_gate']=check
        result['passed']=result['passed'] and check
    result['field_and_upvalue_invalidation_changed']='live immutable proofs survive unrelated changes; layout only invalidates address index; actual field/upvalue changes retain full-object invalidation'
    gate.save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['cases','growth','full_oracle_functional_cases']},ensure_ascii=False));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--case',action='append');a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve(),a.case)['passed'] else 1)
