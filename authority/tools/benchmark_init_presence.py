"""Same binary, frozen workloads, typed vs original reads; 5s children/45s batch."""
import argparse,copy,hashlib,json,os,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_init_profile_gate as experiment
from init_profile_page import ProfilePage
gate=experiment.gate

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def run(out,gate_path):
    out.mkdir(parents=True,exist_ok=False);spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'))
    accepted=json.loads(gate_path.read_text(encoding='utf-8'))
    if not accepted['passed'] or not accepted['complete_manifest'] or accepted['dll_sha256']!=gate.digest(gate.DLL):raise RuntimeError('Full short gate must pass for this DLL')
    names=['legacy-scalar-leaf-shared-upvalue','graph-churn-16','dual-config-2'];rows=[];started=time.perf_counter();before=gate.protected()
    envkeys=['IA_INIT_PROFILE','IA_INIT_LEGACY_PRESENCE','IA_INIT_LEGACY_EVIDENCE','IA_INIT_PRESENCE_VERIFY','IA_CONSUMER_VERIFY','IA_INIT_EVIDENCE_COLLISION'];prior={k:os.environ.get(k) for k in envkeys}
    try:
        for name in names:
            case=next(c for c in spec['cases'] if c['id']==name)
            for repeat in range(2):
                for mode in (['legacy','typed','typed-hash'] if repeat==0 else ['typed-hash','typed','legacy']):
                    remaining=45-(time.perf_counter()-started)
                    if remaining<=0:raise RuntimeError('Presence benchmark batch deadline reached')
                    page=ProfilePage();os.environ['IA_INIT_PROFILE']=page.name
                    os.environ.pop('IA_INIT_PRESENCE_VERIFY',None);os.environ.pop('IA_INIT_EVIDENCE_COLLISION',None);os.environ['IA_CONSUMER_VERIFY']='1'
                    if mode=='legacy':os.environ['IA_INIT_LEGACY_PRESENCE']='1'
                    else:os.environ.pop('IA_INIT_LEGACY_PRESENCE',None)
                    if mode!='typed-hash':os.environ['IA_INIT_LEGACY_EVIDENCE']='1'
                    else:os.environ.pop('IA_INIT_LEGACY_EVIDENCE',None)
                    try:
                        report,artifact,journal=experiment.previous.old_invoke(case,mode+'-'+str(repeat),gate.DLL,out,min(5,remaining));profile=page.read()
                    finally:page.close()
                    if report.get('process_failure'):raise RuntimeError('Bounded benchmark failed: '+str(artifact))
                    metrics=gate.compact_metrics(report);budget=report['budget']
                    if metrics['all_execution_journal_reads']!=0 or not profile or not profile['work_accounting_valid']:raise RuntimeError('Execution read or accounting regression')
                    row={'id':name,'mode':mode,'repeat':repeat,'seconds':artifact['seconds'],'metrics':metrics,'budget':budget,'profile':profile,'proof_sha256':fingerprint(gate.canonical(copy.deepcopy(report))),'audit_sha256':gate.digest(journal)}
                    if journal.parent.resolve()!=out.resolve():raise RuntimeError('Audit cleanup path mismatch')
                    journal.unlink();rows.append(row)
                    gate.save(out/'progress.json',{'rows':rows})
    finally:
        for key,value in prior.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    checks=[]
    for name in names:
        cases=[r for r in rows if r['id']==name]
        checks.append({'id':name,'proof_equal':len({r['proof_sha256'] for r in cases})==1,'audit_equal':len({r['audit_sha256'] for r in cases})==1})
    result={'schema':'typed-presence-benchmark-1','passed':all(c['proof_equal'] and c['audit_equal'] for c in checks) and gate.protected()==before,'rows':rows,'checks':checks,'seconds':time.perf_counter()-started,'work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':45,'dll_sha256':gate.digest(gate.DLL),'exe_sha256':gate.digest(gate.EXE),'manifest_sha256':gate.digest(gate.MANIFEST),'preserved_files_unchanged':gate.protected()==before,'timing_repeats':2,'no_statistical_speed_claim':True}
    gate.save(out/'result.json',result);(out/'progress.json').unlink();print(json.dumps({'passed':result['passed'],'cases':len(names),'runs':len(rows),'seconds':result['seconds']}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.output.resolve(),a.gate.resolve())['passed'] else 1)
