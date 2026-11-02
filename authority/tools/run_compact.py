"""CLI-only, byte-for-byte semantic/producer comparison with the frozen gate."""
import argparse,gc,gzip,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_incremental2 as old
ROOT=Path(__file__).resolve().parents[1]
GROUPS=[('research/ui_incremental2_stage1_v7.json','native-v7'),('research/ui_incremental2_legacy_oracle_v2.json','legacy-v4')]

def run(output,only=None,storage='memory'):
    output.mkdir(parents=True,exist_ok=False)
    old.EXE=ROOT/'build-ui-incremental2/compact/Release/authority-compact-research.exe'
    dll=old.EXE.with_name('ia_lua533_ui_compact.dll');rows=[]
    preserved=old.preservation()
    for folder in ['incremental2_ui_runtime']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:preserved[p.relative_to(ROOT).as_posix()]=old.digest(p)
    for p in (ROOT/'build-ui-incremental2/Release').iterdir():
        if p.suffix in ('.exe','.dll','.lib'):preserved[p.relative_to(ROOT).as_posix()]=old.digest(p)
    old.write(output/'preserved.json',preserved)
    from audit_baseline import audit
    saves=audit(ROOT.parent/'artifacts/authority-baseline-20261009');old.write(output/'save-before.json',saves)
    for manifest,report in GROUPS:
        old.MANIFEST=ROOT/manifest;suite=json.loads(old.MANIFEST.read_text(encoding='utf-8'))
        for case in suite['cases']:
            if only and case['id'] not in only:continue
            with gzip.open(ROOT/'reports/ui-incremental2-stage1'/report/(case['id']+'-candidate-1.json.gz'),'rt',encoding='utf-8') as f:baseline=json.load(f)
            print('Compact '+case['id'],flush=True)
            if storage=='journal':os.environ['IA_COMPACT_AUDIT_FILE']=str(output/(case['id']+'-first.audit'))
            else:os.environ.pop('IA_COMPACT_AUDIT_FILE',None)
            first,a=old.invoke(case,'compact-1',dll,output,True)
            if storage=='journal':os.environ['IA_COMPACT_AUDIT_FILE']=str(output/(case['id']+'-second.audit'))
            second,b=old.invoke(case,'compact-2',dll,output,True)
            same=not first.get('process_failure') and old.proof(first)==old.proof(baseline)
            repeated=not second.get('process_failure') and old.proof(first)==old.proof(second)
            budget=first.get('budget',{});bounded=budget.get('limit')==10000000 and budget.get('used',10000001)<=10000000 and budget.get('used')==sum(budget.get('categories',{}).values())
            if case['kind']!='safety':bounded=bounded and not budget.get('failure') and first.get('diagnostic_export_budget_ok',False)
            sources=old.graph_sources(first) if same else None
            origin_equal=sources==[p.get('origins',[]) for p in first.get('phases',[])]
            row={'id':case['id'],'kind':case['kind'],'proof_equal_frozen':same,'repeat_equal':repeated,'budget_valid':bounded,'sources_equal':origin_equal,
                 'budget':budget,'compact_storage':first.get('compact_storage'),'private_commit_bytes':first.get('private_commit_bytes'),
                 'baseline_private_commit_bytes':baseline.get('private_commit_bytes'),'artifacts':[a,b]}
            row['passed']=same and repeated and bounded and origin_equal
            if storage=='journal':
                first_path=output/(case['id']+'-first.audit');second_path=output/(case['id']+'-second.audit')
                row['audit_first_sha256']=old.digest(first_path);row['audit_second_sha256']=old.digest(second_path)
                row['audit_bytes']=first_path.stat().st_size;row['audit_repeat_equal']=row['audit_first_sha256']==row['audit_second_sha256']
                from read_compact_audit import read
                decoded=read(first_path);graph=first.get('value_graph',{});incremental=first.get('trace',{}).get('incremental',{})
                row['audit_independent_reconstruction_equal']=all(decoded[k]==graph[k] for k in ['nodes','consumption_records','storage_versions','static_regions','code','purpose_records']) and all(decoded[k]==incremental[k] for k in ['cache_descriptors','cache_sites','cache_uses']) and decoded['root']=={k:v for k,v in graph.items() if k not in ['nodes','consumption_records','storage_versions','static_regions','code','purpose_records']}
                row['passed']=row['passed'] and row['audit_repeat_equal'] and row['audit_independent_reconstruction_equal'] and first.get('compact_storage',{}).get('audit_streamed',False)
                if row['audit_repeat_equal']:
                    # The duplicate was just hashed and belongs to this fresh
                    # case output directory. Keep the unique first audit only.
                    if not second_path.resolve().is_relative_to(output.resolve()):raise ValueError('Audit cleanup escaped output')
                    second_path.unlink();row['duplicate_audit_removed']=True
            rows.append(row);old.write(output/(case['id']+'-result.json'),row)
            print(json.dumps({k:row[k] for k in ['id','passed','proof_equal_frozen','repeat_equal','budget_valid','private_commit_bytes']}),flush=True)
            del baseline,first,second;gc.collect()
    unchanged=all((ROOT/name).is_file() and old.digest(ROOT/name)==sha for name,sha in preserved.items())
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');old.write(output/'save-after.json',after)
    result={'stage':'typed-compact-graph','cases':rows,'case_count':len(rows),'complete_51_case_gate':len(rows)==51,
            'passed':bool(rows) and all(r['passed'] for r in rows) and unchanged and saves['files']==after['files'],
            'preserved_unchanged':unchanged,'saves_unchanged':saves['files']==after['files'],'runtime_sha256':old.digest(dll),
            'runner_sha256':old.digest(old.EXE),'work_limit':10000000,'game_started':False,'storage':storage,'audit_stream_complete':storage=='journal','graph_gc_complete':False}
    old.write(output/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');p.add_argument('--storage',choices=['memory','journal'],default='memory')
    a=p.parse_args();result=run(a.output.resolve(),a.case,a.storage);sys.exit(0 if result['passed'] else 1)
