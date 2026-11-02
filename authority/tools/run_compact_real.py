"""One frozen real MCM/EID case per bounded process; no installed files written."""
import argparse,gc,gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import digest,write
from audit_baseline import audit
ROOT=Path(__file__).resolve().parents[1]
IDS=['mcm-en','mcm-zh','eid-en','eid-zh','combined-en','combined-zh']

def functional(r):
    return {k:r.get(k) for k in ['initialization_passed','contract_passed','observations','source_unchanged','world','world_effects','host_stack_restored']}

def invoke(case,trace,repeat,output):
    binary=ROOT/'build-ui-incremental2/compact/Release';dll=binary/'ia_lua533_ui_compact.dll' if trace else ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_reference.dll'
    stem=case+('-candidate-' if trace else '-reference-')+str(repeat);raw=output/(stem+'.json.tmp');err=output/(stem+'.stderr.txt');journal=output/(stem+'.audit')
    env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None)
    if trace:env['IA_COMPACT_AUDIT_FILE']=str(journal)
    else:env.pop('IA_COMPACT_AUDIT_FILE',None)
    command=[str(binary/'authority-compact-real.exe'),'--suite',str(dll),digest(dll),str(ROOT),str(ROOT/'research/ui_incremental_suite_10m_v1.json'),case,'trace' if trace else 'plain']
    start=time.perf_counter()
    with raw.open('xb') as out,err.open('xb') as errors:
        try:r=subprocess.run(command,stdout=out,stderr=errors,env=env,timeout=90)
        except subprocess.TimeoutExpired:return {'process_failure':True,'timeout':True}, {'seconds':time.perf_counter()-start,'stderr_file':err.name}
    elapsed=time.perf_counter()-start;data=raw.read_bytes();target=output/(stem+'.json.gz')
    with gzip.open(target,'xb',compresslevel=6) as stream:stream.write(data)
    raw.unlink();artifact={'file':target.name,'sha256':digest(target),'seconds':elapsed,'returncode':r.returncode,'stderr_file':err.name}
    if r.returncode:return {'process_failure':True,'error':err.read_text(encoding='utf-8',errors='replace')},artifact
    report=json.loads(data);return report['case'],artifact

def run(output,only=None):
    output.mkdir(parents=True,exist_ok=False);rows=[]
    before=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-before.json',before)
    for name in IDS:
        if only and name not in only:continue
        print('Real initialization '+name,flush=True);references=[];candidates=[];artifacts=[]
        for trace,target in [(False,references),(True,candidates)]:
            for repeat in (1,2):
                case,artifact=invoke(name,trace,repeat,output);target.append(case);artifacts.append(artifact)
        ref_ok=all(c.get('compatibility_passed') for c in references)
        repeated=all(not c.get('process_failure') for c in candidates) and functional(candidates[0])==functional(candidates[1]) and candidates[0].get('budget')==candidates[1].get('budget') and candidates[0].get('first_unsupported_entry')==candidates[1].get('first_unsupported_entry')
        ordinary_equal=all(functional(c)==functional(references[0]) for c in candidates)
        bounded=all(c.get('budget',{}).get('limit')==10000000 and c.get('budget',{}).get('used',10000001)<=10000000 and c.get('budget',{}).get('used')==sum(c.get('budget',{}).get('categories',{}).values()) for c in candidates)
        journals=[output/(name+'-candidate-'+str(i)+'.audit') for i in (1,2)];equal=all(p.is_file() for p in journals) and digest(journals[0])==digest(journals[1])
        row={'id':name,'reference_passed':ref_ok,'candidate_passed':all(c.get('compatibility_passed',False) for c in candidates),'functional_equal_reference':ordinary_equal,'repeat_equal':repeated,'budget_valid':bounded,'audit_repeat_equal':equal,'candidates':candidates,'artifacts':artifacts}
        row['passed']=bool(ref_ok and row['candidate_passed'] and ordinary_equal and repeated and bounded and equal)
        if equal:journals[1].unlink();row['duplicate_audit_removed']=True
        write(output/(name+'-result.json'),row);rows.append(row)
        print(json.dumps({'id':name,'passed':row['passed'],'reference_passed':ref_ok,'repeat_equal':repeated,'work':[c.get('budget',{}).get('used') for c in candidates],'failures':[c.get('first_unsupported_entry',c.get('error')) for c in candidates]},ensure_ascii=False),flush=True)
        del candidates,references;gc.collect()
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-after.json',after)
    binary=ROOT/'build-ui-incremental2/compact/Release';result={'schema':'compact-real-gate-1','passed':len(rows)==6 and all(r['passed'] for r in rows),'cases':rows,'work_limit':10000000,'runtime_sha256':digest(binary/'ia_lua533_ui_compact.dll'),'runner_sha256':digest(binary/'authority-compact-real.exe'),'manifest_sha256':digest(ROOT/'research/ui_incremental_suite_10m_v1.json'),'saves_unchanged':before['files']==after['files'],'game_started':False,'menu_navigation_tested':False,'draw_capture_tested':False}
    write(output/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');a=p.parse_args();r=run(a.output.resolve(),a.case);sys.exit(0 if r['passed'] else 1)
