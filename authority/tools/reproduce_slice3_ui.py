"""Verify an extracted UI bundle and repeat full evidence including historical suites."""
import sys
sys.dont_write_bytecode=True
import argparse, json, subprocess
from pathlib import Path
from run_trace_research import digest, write
from run_slice3_ui_research import HISTORY, SUITE, run_ui, verify_inputs
from reproduce_slice3 import normalize, frozen_filename_maps

def ui_filename_maps(root,definition):
    maps=[]
    for case in definition['cases']:
        for mod in case['mods']:
            for name in mod['sha256']:
                rel='research/slice3_ui_inputs/'+mod['root']+'/'+name
                raw=(Path(root)/rel).as_posix().encode()
                if len(raw)>=60:maps.append(((b'...'+raw[-56:]).decode(),'<SOURCE>/'+rel))
    return sorted(set(maps),key=lambda x:-len(x[0]))

def compare_cases(expected,actual,old_roots,new_roots):
    for left,right in zip(expected['cases'],actual['cases'],strict=True):
        normalize(left,old_roots);normalize(right,new_roots)
        if left!=right:raise ValueError('Complete relocated evidence changed: '+left['id'])

def run(bundle,archive,output,game=None):
    sha=digest(archive)
    if sha!=archive.with_suffix(archive.suffix+'.sha256').read_text().split()[0]:raise ValueError('Archive hash mismatch')
    index=json.loads((bundle/'bundle-manifest.json').read_text());expected_paths=set()
    for record in index['files']:
        p=(bundle/record['path']).resolve();expected_paths.add(record['path'])
        if not p.is_relative_to(bundle) or p.stat().st_size!=record['bytes'] or digest(p)!=record['sha256']:
            raise ValueError('Extracted file mismatch: '+record['path'])
    actual_paths={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    if actual_paths!=expected_paths|{'bundle-manifest.json'}:raise ValueError('Extra or missing extracted file')
    output.mkdir(parents=True,exist_ok=False);source=bundle/'source';binary=bundle/'bin';model_game=bundle/'model_game'
    inputs=verify_inputs(source,game)
    validation=json.loads((bundle/'reports/current/validation.json').read_text())
    definition=json.loads((source/'research'/SUITE).read_text());results={}
    old_ui=[(validation['original_source_root'],'<SOURCE>')]+ui_filename_maps(validation['original_source_root'],definition)
    new_ui=[(str(source),'<SOURCE>')]+ui_filename_maps(source,definition)
    for label,reference in (('reference',True),('candidate',False)):
        print('Portable UI '+label,flush=True);target=output/(label+'.json');actual=run_ui(binary,source,target,reference)
        expected=json.loads((bundle/'reports/current'/(label+'-1.json')).read_text())
        compare_cases(expected,actual,old_ui,new_ui)
        results[label]={'cases':len(actual['cases']),'full_case_evidence_equal':True,
            'initialization_contract_gate_passed':actual['initialization_contract_gate_passed']}
    histories={}
    for suite,mode in HISTORY:
        print('Portable historical '+suite,flush=True);definition=json.loads((source/'research'/suite).read_text())
        dll=bundle/'history-bin'/('ia_lua533_'+mode+'.dll');target=output/(Path(suite).stem+'.json')
        with target.open('xb') as stream:
            p=subprocess.run([str(binary/'authority-trace-research.exe'),'--suite',str(dll),digest(dll),str(model_game),str(source),str(source/'research'/suite)],stdout=stream,stderr=subprocess.PIPE,timeout=1200)
        if p.stderr:target.with_suffix('.stderr.txt').write_bytes(p.stderr)
        if p.returncode:raise ValueError('Portable historical process failed: '+suite)
        actual=json.loads(target.read_text());expected=json.loads((bundle/'reports/current'/(Path(suite).stem+'-1.json')).read_text())
        if not actual['diagnostic_passed']:raise ValueError('Portable historical expectations failed: '+suite)
        old=[(validation['original_source_root'],'<SOURCE>'),(validation['original_game_root'],'<GAME>')]+frozen_filename_maps(validation['original_source_root'],validation['original_game_root'],definition)
        new=[(str(source),'<SOURCE>'),(str(model_game),'<GAME>')]+frozen_filename_maps(source,model_game,definition)
        compare_cases(expected,actual,old,new)
        histories[suite]={'cases':len(actual['cases']),'full_case_evidence_equal':True,'original_expected_outcomes_passed':True}
    report={'schema':'isaac-slice3-ui-portable-reproduction-1','archive_sha256':sha,'files_verified':len(index['files']),
        'ui_reports':results,'historical_suites':histories,'historical_cases':sum(c['cases'] for c in histories.values()),
        'complete_case_evidence_equal_after_path_normalization':True,'inputs':inputs,
        'local_assets_checked':game is not None,'metadata_only_run':game is None,
        'initialization_contract_gate_passed':validation['initialization_contract_gate_passed'],
        'reproduced_failure_is_functional_compatibility':False,'game_process_used':False,'render_capture_passed':False,'playable':False}
    write(output/'reproduction.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','archive','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--game',type=Path,help='Optional read-only check of local image/font dependencies')
    a=p.parse_args();print(json.dumps(run(a.bundle.resolve(),a.archive.resolve(),a.output.resolve(),a.game.resolve() if a.game else None),indent=2))
