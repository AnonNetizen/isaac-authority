"""Verify every extracted file and compare complete normalized model evidence."""
import argparse,json,subprocess
from pathlib import Path
from freeze_suite import digest

def frozen_filename_maps(source,game,manifest):
    # luaO_chunkid in the pinned Lua 5.3.3 source uses a 60-byte buffer:
    # a long @filename becomes "..." + its last 56 bytes. Build exact maps
    # for frozen files, rather than discarding diagnostic messages or graphs.
    mapping=[]
    for case in manifest['cases']:
        for mod in case['mods']:
            root=source if mod['base']=='research' else game
            prefix='<SOURCE>' if mod['base']=='research' else '<GAME>'
            for name in mod['sha256']:
                relative=mod['root']+'/'+name
                raw=(Path(root)/relative).as_posix().encode()
                if len(raw)>=60:mapping.append(((b'...'+raw[-56:]).decode(),prefix+'/'+relative))
    return sorted(set(mapping),key=lambda x:-len(x[0]))

def normalize(value,roots,key=None):
    if isinstance(value,dict):
        for k,v in value.items():value[k]=normalize(v,roots,k)
    elif isinstance(value,list):
        for i,v in enumerate(value):value[i]=normalize(v,roots,key)
    elif isinstance(value,str):
        if key in ('hex','text_hex'):
            raw=bytes.fromhex(value)
            for root,label in roots:
                for variant in (root,root.replace('\\','/'),root.replace('/','\\')):raw=raw.replace(variant.encode(),label.encode())
            return raw.hex()
        for root,label in roots:
            for variant in (root,root.replace('\\','/'),root.replace('/','\\')):value=value.replace(variant,label)
    return value

def run(bundle,output,archive):
    manifest=json.loads((bundle/'bundle-manifest.json').read_text())
    archive_sha=digest(archive)
    if archive_sha!=archive.with_suffix(archive.suffix+'.sha256').read_text().split()[0]:raise ValueError('Archive hash mismatch')
    for item in manifest['files']:
        p=(bundle/item['path']).resolve()
        if not p.is_relative_to(bundle) or p.stat().st_size!=item['bytes'] or digest(p)!=item['sha256']:raise ValueError('Extracted file mismatch: '+item['path'])
    validation=json.loads((bundle/'reports/current/validation.json').read_text());binary=bundle/'bin';source=bundle/'source';game=bundle/'model_game';dll=binary/'ia_lua533_slice3.dll'
    raw=output.with_name(output.stem+'-suite.json')
    with raw.open('xb') as stream:
        p=subprocess.run([str(binary/'authority-slice3-research.exe'),'--suite',str(dll),digest(dll),str(game),str(source),str(source/'research/slice3_suite_v3.json')],stdout=stream,stderr=subprocess.PIPE,timeout=600)
    if p.returncode:raise RuntimeError('Portable suite failed: '+p.stderr.decode())
    actual=json.loads(raw.read_text());expected=json.loads((bundle/'reports/current/slice3_suite_v3-1.json').read_text())
    if not actual['diagnostic_passed']:raise ValueError('Portable diagnostic failed')
    frozen=json.loads((source/'research/slice3_suite_v3.json').read_text())
    expected_maps=frozen_filename_maps(validation['original_source_root'],validation['original_game_root'],frozen)
    actual_maps=frozen_filename_maps(source,game,frozen)
    accepted=rejected=duplicates=0
    for left,right in zip(expected['cases'],actual['cases'],strict=True):
        normalize(left,[(validation['original_source_root'],'<SOURCE>'),(validation['original_game_root'],'<GAME>')]+expected_maps)
        normalize(right,[(str(source),'<SOURCE>'),(str(game),'<GAME>')]+actual_maps)
        if left!=right:raise ValueError('Complete case evidence changed after relocation: '+left['id'])
        for f in right['frames']:
            if f['outcome']=='reject':
                if not f['rollback_passed']:raise ValueError('Portable rollback failed')
                rejected+=1
            else:accepted+=1
            if f.get('output',{}).get('duplicate'):
                if not f['duplicate_state_unchanged']:raise ValueError('Portable deduplication failed')
                duplicates+=1
    result={'schema':'isaac-slice3-portable-reproduction-1','archive_sha256':archive_sha,'files_verified':len(manifest['files']),'cases':len(actual['cases']),
        'diagnostic_passed':True,'complete_case_evidence_equal_after_path_normalization':True,'value_graphs_and_authority_references_equal':True,'branch_proofs_and_budgets_equal':True,
        'accepted_frames_compared':accepted,'rejected_frames_with_rollback':rejected,'duplicate_frames_unchanged':duplicates,'only_source_and_game_directory_relocations_normalized':True,'lua533_short_filename_rule_applied_to_frozen_files':True,
        'functional_gate_passed':validation['functional_gate_passed'],'game_process_used':False,'game_installation_needed':False,'playable':False,'real_mcm_eid_tested':False,'generic_mod_compatibility_passed':False}
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','output','archive'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(*[getattr(a,n).resolve() for n in ('bundle','output','archive')]),indent=2))
