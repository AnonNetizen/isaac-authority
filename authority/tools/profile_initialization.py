"""One bounded 5s attempt per frozen case with a fixed-size sampler page."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from init_profile_page import ProfilePage
from run_incremental2 import digest
from run_consumer_initialization import prefix
from audit_baseline import audit
ROOT=Path(__file__).resolve().parents[1]
DLL=ROOT/'build-init-profile/Release/ia_lua533_init_profile.dll';EXE=DLL.with_name('authority-init-profile-real.exe')
MANIFEST=ROOT/'research/ui_incremental_suite_10m_v1.json'
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def compact_cases(out):
    # Completed summary already embeds the full case objects. Retain case files
    # only while a batch is incomplete, for recovery without re-running a model.
    summary=out/'result.json';result=json.loads(summary.read_text(encoding='utf-8'));removed=[]
    for case in result['cases']:
        path=out/(case['id']+'.json')
        if not path.exists():continue
        if path.is_symlink() or path.resolve().parent!=out.resolve():raise RuntimeError('Case cleanup path escapes result directory')
        if json.loads(path.read_text(encoding='utf-8'))!=case:raise RuntimeError('Case file differs from embedded complete summary')
        removed.append({'file':path.name,'bytes':path.stat().st_size,'sha256':digest(path)})
    for row in removed:(out/row['file']).unlink()
    if removed:
        result['duplicate_case_objects_removed']=removed;save(summary,result)
    return result
def invoke(case,out,label='measured',legacy=False,legacy_evidence=False):
    page=ProfilePage();journal=out/(case+'-'+label+'.audit');env=os.environ.copy();env['IA_INIT_PROFILE']=page.name;env['IA_COMPACT_AUDIT_FILE']=str(journal)
    # Match ordinary initialization; expensive correctness oracles are short-model gates.
    for key in ['IA_INCREMENTAL_VERIFY','IA_CONSUMER_VERIFY','IA_INIT_PRESENCE_VERIFY','IA_INIT_LEGACY_PRESENCE','IA_INIT_LEGACY_EVIDENCE','IA_INIT_EVIDENCE_COLLISION']:env.pop(key,None)
    if legacy:env['IA_INIT_LEGACY_PRESENCE']='1'
    if legacy_evidence:env['IA_INIT_LEGACY_EVIDENCE']='1'
    command=[str(EXE),'--suite',str(DLL),digest(DLL),str(ROOT),str(MANIFEST),case,'trace']
    points=[];started=time.perf_counter();timed_out=False
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    try:
        while process.poll() is None:
            sample=page.read()
            if sample and (not points or sample['checkpoints']!=points[-1]['checkpoints']):
                sample['elapsed_seconds']=time.perf_counter()-started;points.append(sample)
                if len(points)>64:raise RuntimeError('Bounded profile progress cap exceeded')
            remaining=5-(time.perf_counter()-started)
            if remaining<=0:timed_out=True;process.kill();break
            try:process.wait(timeout=min(.1,remaining))
            except subprocess.TimeoutExpired:pass
        stdout,stderr=process.communicate(timeout=1)
        sample=page.read()
        if sample:sample['elapsed_seconds']=time.perf_counter()-started;points.append(sample)
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=1)
        page.close()
    if len(stdout)>1024*1024:raise RuntimeError('Initialization report exceeds 1 MiB')
    result={'id':case,'presence_mode':'legacy-json' if legacy else 'typed-live','evidence_index':'ordered' if legacy_evidence else 'hash-exact','timed_out':timed_out,'seconds':time.perf_counter()-started,'timeout_seconds':5,'returncode':process.returncode,'stderr_tail':stderr[-8192:].decode('utf-8',errors='replace'),'progress':points,'last_profile':points[-1] if points else None,'report':json.loads(stdout) if process.returncode==0 else None,'work_limit':10000000}
    if journal.exists():
        if journal.stat().st_size>16*1024*1024:raise RuntimeError('Audit quota exceeded')
        result['audit_prefix']=prefix(journal);result['audit_sha256']=digest(journal)
        # Unique source-level timing evidence is in this compact result. No new
        # multi-MiB audit clone is retained for a repeated initialization attempt.
        journal.unlink()
    save(out/(case+'.json'),result);print(json.dumps({'id':case,'timed_out':timed_out,'used':(result['last_profile'] or {}).get('used'),'first_unsupported':(result['report'] or {}).get('case',{}).get('first_unsupported_entry')}),flush=True);return result
def run(out,only,legacy=False,legacy_evidence=False):
    out.mkdir(parents=True,exist_ok=False);before=audit(ROOT.parent/'artifacts/authority-baseline-20261009');started=time.perf_counter();rows=[]
    for case in only or ['mcm-zh','eid-zh','combined-zh']:
        if time.perf_counter()-started>25:raise RuntimeError('Initialization profile batch deadline reached')
        rows.append(invoke(case,out,legacy=legacy,legacy_evidence=legacy_evidence))
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    expected={}
    for c in json.loads(MANIFEST.read_text(encoding='utf-8'))['cases']:
        for mod in c['mods']:
            for p,h in mod['sha256'].items():expected[str(Path(mod['root'])/p)]=h
    result={'schema':'bounded-initialization-profile-1','cases':rows,'work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':30,'seconds':time.perf_counter()-started,'dll_sha256':digest(DLL),'exe_sha256':digest(EXE),'manifest_sha256':digest(MANIFEST),'save_files_unchanged':before['files']==after['files'],'frozen_sources_unchanged':all(digest(ROOT/'research/slice3_ui_inputs'/p)==h for p,h in expected.items()),'frozen_source_count':len(expected),'game_started':False,'profiling_is_sampled_wall_time':True}
    save(out/'result.json',result);return compact_cases(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--case',action='append');p.add_argument('--legacy',action='store_true');p.add_argument('--legacy-evidence',action='store_true');p.add_argument('--compact-only',action='store_true');a=p.parse_args()
    if a.compact_only:compact_cases(a.output.resolve())
    else:run(a.output.resolve(),a.case,a.legacy,a.legacy_evidence)
