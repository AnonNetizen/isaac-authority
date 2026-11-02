"""Run a single-computer host-side Lua isolation MODEL without starting or patching Isaac."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.isolation import HostIsolation,IsolationFailure,ModSource,config_store,sha

def visible(record):
    return {slot:[{**cmd,'text':bytes.fromhex(cmd['text_hex']).decode('utf-8','replace')} for cmd in cmds]
            for slot,cmds in record['draws'].items()}

def demo(run):
    run.mkdir(parents=True,exist_ok=False)
    src=ModSource.directory(ROOT/'fixtures'/'legacy_chaos')
    manifest=src.manifest()
    configs=config_store('Authority Research Legacy Chaos Fixture',
        {'language':'zh','x':24,'key':76}, {'language':'en','x':124,'key':77})
    instance=HostIsolation(src,configs,seed=20261010,journal=run/'personal-contexts.json')
    examples=[]
    for frame,inputs in [(1,{}),(2,{'1':{'triggered':[77]}}),(3,{'0':{'triggered':[76]}})]:
        record=instance.step(frame,1000000+frame*33,inputs)
        examples.append({'frame':frame,'world':record['world'],'authority_effects':record['effects'],
                         'personal_huds':visible(record)})
    saved=instance.journal.read_bytes()
    duplicate=instance.step(3,1000099,{'0':{'triggered':[76]}})
    duplicate_did_not_recommit=instance.journal.read_bytes()==saved and len(instance.history)==3
    resumed=HostIsolation.resume(src,instance.journal)
    next_record=resumed.step(4,1000132)
    private_counter_restored=all('|4|' in cmds[0]['text'] for cmds in visible(next_record).values())
    driver=ModSource.directory(ROOT/'fixtures'/'config_drives_world')
    driver_config=config_store('Config Drives World Fixture',
        {'language':'zh','x':24,'key':76,'amount':1}, {'language':'en','x':124,'key':77,'amount':1})
    negative=HostIsolation(driver,driver_config,journal=run/'rejection-checkpoint.json')
    accepted=negative.step(1,100); unchanged=negative.journal.read_bytes()
    rejection=None
    try: negative.step(2,101,{'1':{'triggered':[77]}})
    except IsolationFailure as error: rejection=str(error)
    rollback_ok=negative.world.snapshot()==accepted['world'] and negative.journal.read_bytes()==unchanged
    recovered=negative.step(2,101)
    recovery_ok=all(cmds[0]['text'].endswith('|2') for cmds in visible(recovered).values())
    passed=all((duplicate_did_not_recommit,private_counter_restored,rejection is not None,rollback_ok,recovery_ok))
    return {'experiment':'host_side_shadow_contexts','single_computer':True,'native_game_used':False,
        'all_lua_contexts_on_host':True,'mod_source_modified':False,
        'source_manifest':manifest,'source_unchanged':ModSource.directory(ROOT/'fixtures'/'legacy_chaos').manifest()==manifest,
        'limited_model_experiment_passed':passed,'generic_mod_compatibility_passed':False,'playable':False,
        'frames':examples,'duplicate_did_not_recommit':duplicate_did_not_recommit,
        'resumed_personal_huds':visible(next_record),'private_counter_restored':private_counter_restored,
        'personal_setting_changes_world_rejected':rejection,'world_and_config_rollback_ok':rollback_ok,
        'private_vm_reconstruction_ok':recovery_ok,
        'scope':'Lua 5.3 with a small simulated API profile; no J460 userdata, combat, Steam or native saves.'}

def probe(directory,definitions=None):
    source=ModSource.directory(directory,definitions.read_bytes() if definitions else None)
    began=time.perf_counter()
    report={'mod_directory':source.name,'unmodified_source':True,'source_files':len(source.files),
            'main_sha256':sha(source.files[source.entry]),'native_game_used':False,'playable':False,
            'source_manifest':source.manifest(),'api_profile':'offline-coins-and-text-v1',
            'j460_enum_definitions_supplied':definitions is not None}
    try:
        session=HostIsolation(source)
        session.step(1,100)
        report['load_and_first_model_frame_passed']=True
    except Exception as error:
        report['load_and_first_model_frame_passed']=False
        report['failure']=str(error)
    report['elapsed_seconds']=time.perf_counter()-began
    report['source_unchanged']=ModSource.directory(directory,definitions.read_bytes() if definitions else None).manifest()==source.manifest()
    report['interpretation']='Profile coverage probe only; success would not establish live-game compatibility.'
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--demo',action='store_true')
    selection.add_argument('--probe-mod',type=Path)
    parser.add_argument('--definitions',type=Path,help='Optional read-only J460 enums.lua')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.probe_mod and not args.worker:
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--worker'],
                capture_output=True,text=True,timeout=20)
            if result.returncode: raise RuntimeError(result.stderr[-2000:] or 'probe worker failed')
            print(result.stdout.strip()); return 0
        except (subprocess.TimeoutExpired,RuntimeError) as error:
            report={'mod_directory':args.probe_mod.name,'worker_failed_or_timed_out':True,
                    'load_and_first_model_frame_passed':False,'failure':str(error),'playable':False}
    elif args.demo:
        run=args.run_dir or ROOT/'runs'/('isolation-'+uuid.uuid4().hex)
        report=demo(run)
    else: report=probe(args.probe_mod,args.definitions)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:report[k] for k in report if k in ('limited_model_experiment_passed','mod_directory',
        'load_and_first_model_frame_passed','failure','source_unchanged','playable')},ensure_ascii=False))
    return 1 if args.demo and not report['limited_model_experiment_passed'] else 0

if __name__=='__main__': raise SystemExit(main())
