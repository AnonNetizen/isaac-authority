"""Regression and profiling-neutrality gate, 5s children and 90s batch."""
import argparse,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_consumers as previous
from init_profile_page import ProfilePage
gate=previous.gate;ROOT=gate.ROOT
gate.DLL=ROOT/'build-init-profile/Release/ia_lua533_init_profile.dll';gate.EXE=gate.DLL.with_name('authority-init-profile.exe')
gate.OLD=ROOT/'build-consumers/Release/ia_lua533_consumers.dll'
old_protected=gate.protected
def protected():
    result=old_protected()
    for folder in ['consumer_runtime','build-consumers/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='consumer_runtime' or p.suffix in ['.exe','.dll','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    result['research/ui_consumers_v1.json']=gate.digest(ROOT/'research/ui_consumers_v1.json');return result
gate.protected=protected
old_invoke=gate.invoke
PAGES={}
def invoke(case,label,dll,out,timeout):
    if dll!=gate.DLL:return old_invoke(case,label,dll,out,timeout)
    page=ProfilePage();prior={k:os.environ.get(k) for k in ['IA_INIT_PROFILE','IA_INIT_PRESENCE_VERIFY','IA_INIT_LEGACY_PRESENCE','IA_INIT_LEGACY_EVIDENCE']};os.environ['IA_INIT_PROFILE']=page.name
    os.environ['IA_INIT_PRESENCE_VERIFY']='1';os.environ.pop('IA_INIT_LEGACY_PRESENCE',None);os.environ.pop('IA_INIT_LEGACY_EVIDENCE',None)
    try:
        result=old_invoke(case,label,dll,out,timeout);PAGES[(case['id'],label)]=page.read();return result
    finally:
        for key,value in prior.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        page.close()
gate.invoke=invoke
def run(out,only):
    result=previous.run(out,only);checks=[]
    for row in result['cases']:
        profile=PAGES.get((row['id'],'candidate-1'))
        check=profile is not None and profile['work_accounting_valid']
        # A forced process refusal may skip stop(); complete children must stop.
        if row['kind'] not in ['process-safety']:check=check and bool(profile['flags']&1)
        checks.append({'id':row['id'],'passed':check,'profile':profile})
    result['schema']='initialization-profile-gate';result['profile_checks']=checks;result['passed']=result['passed'] and all(c['passed'] for c in checks)
    result['experiment']={'per_miss_original_presence_oracle':True,'forced_evidence_hash_collision':os.environ.get('IA_INIT_EVIDENCE_COLLISION') is not None,'unchanged_frozen_manifest':True}
    gate.save(out/'result.json',result);print(json.dumps({'passed':result['passed'],'cases':len(result['cases']),'profile_failures':[c['id'] for c in checks if not c['passed']]}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');p.add_argument('--collision',action='store_true');a=p.parse_args()
    if a.collision:os.environ['IA_INIT_EVIDENCE_COLLISION']='1'
    else:os.environ.pop('IA_INIT_EVIDENCE_COLLISION',None)
    sys.exit(0 if run(a.output.resolve(),a.case)['passed'] else 1)
