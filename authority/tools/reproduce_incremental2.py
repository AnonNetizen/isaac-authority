"""Verify and replay a relocated stage-one bundle without game/save access."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_incremental2 as gate

def reproduce(bundle, output):
    bundle=bundle.resolve();output=output.resolve()
    if output.is_relative_to(bundle):raise ValueError('Keep unique replay results outside the extracted bundle')
    manifest=json.loads((bundle/'bundle-manifest.json').read_text(encoding='utf-8'))
    verified=0
    for entry in manifest['files']:
        path=(bundle/entry['path']).resolve()
        if not path.is_relative_to(bundle) or not path.is_file():raise ValueError('Missing/unsafe bundle entry')
        if path.stat().st_size!=entry['bytes'] or gate.digest(path)!=entry['sha256']:raise ValueError('Bundle entry changed: '+entry['path'])
        verified+=1
    output.mkdir(parents=True,exist_ok=False)
    gate.ROOT=bundle/'authority';gate.EXE=gate.ROOT/'build-ui-incremental2/Release/authority-incremental2-research.exe'
    runtime=gate.EXE.with_name('ia_lua533_ui_incremental2.dll');rows=[]
    for group in manifest['groups']:
        gate.MANIFEST=gate.ROOT/group['manifest']
        frozen=json.loads(gate.MANIFEST.read_text(encoding='utf-8'))
        for case in frozen['cases']:
            folder=output/case['id'];folder.mkdir()
            expected_path=bundle/'reports'/group['report']/(case['id']+'-candidate-1.json.gz')
            with gzip.open(expected_path,'rt',encoding='utf-8') as stream:expected=json.load(stream)
            actual,artifact=gate.invoke(case,'replayed',runtime,folder,True)
            equal=not actual.get('process_failure') and gate.proof(actual)==gate.proof(expected)
            budget=actual.get('budget',{});bounded=budget.get('limit')==10000000 and budget.get('failure')==expected.get('budget',{}).get('failure') and budget.get('used',10000001)<=10000000 and budget.get('used')==sum(budget.get('categories',{}).values())
            sources=gate.graph_sources(actual) if equal else None
            row={'id':case['id'],'proofs_equal_frozen_run':equal,'budget_valid':bounded,
                 'producer_sources_equal_origins':sources==[p.get('origins',[]) for p in actual.get('phases',[])],
                 'artifact':artifact}
            rows.append(row);gate.write(folder/'result.json',row)
            print(json.dumps({k:v for k,v in row.items() if k!='artifact'}),flush=True)
    result={'verified_files':verified,'cases':rows,'replay_passed':all(r['proofs_equal_frozen_run'] and r['budget_valid'] and r['producer_sources_equal_origins'] for r in rows),
            'game_started':False,'save_accessed':False,'entire_refactor_passed':False}
    gate.write(output/'result.json',result)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=reproduce(args.bundle,args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)
    sys.exit(0 if result['replay_passed'] else 1)
