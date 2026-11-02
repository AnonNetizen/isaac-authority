"""Measure frozen initialization in an independent 2M, 5M or 10M process."""
import argparse,copy,ctypes,json,os,statistics,subprocess,sys,threading,time
from ctypes import wintypes
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,write,real_manifest

class Counters(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ['peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile']]

def measure(binary,limit,case_id,repeat,output,inspect=None):
    original=real_manifest(limit)
    spec=json.loads(original.read_bytes());case=copy.deepcopy(next(c for c in spec['cases'] if c['id']==case_id));spec['cases']=[case]
    spec['purpose']='Timing only: frozen code, identical options and unchanged profile limits'
    prefix=f'{limit}-{case_id}-{repeat}';manifest=output/(prefix+'-suite.json');write(manifest,spec)
    dll=binary/'ia_lua533_ui_incremental.dll';env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    marks=[];peak=[0];stop=threading.Event()
    with (output/(prefix+'.json')).open('xb') as out,(output/(prefix+'.stderr.txt')).open('x',encoding='utf-8') as err:
        start=time.perf_counter();p=subprocess.Popen([str(binary/'authority-ui-incremental-research.exe'),'--suite',str(dll),digest(dll),str(ROOT/'research/slice3_ui_inputs'),str(ROOT),str(manifest)],stdout=out,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env)
        handle=kernel.OpenProcess(0x0400|0x0010,False,p.pid)
        if not handle:p.kill();p.wait();raise ctypes.WinError(ctypes.get_last_error())
        def memory():
            c=Counters();c.cb=ctypes.sizeof(c)
            if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb):return None
            peak[0]=max(peak[0],c.peak_ws);return c.ws
        def sample():
            while not stop.wait(0.05):memory()
        thread=threading.Thread(target=sample,daemon=True);thread.start()
        try:
            for line in p.stderr:
                now=time.perf_counter();err.write(line);err.flush();marks.append({'line':line.rstrip(),'seconds':now-start,'working_set_bytes':memory()})
            code=p.wait()
        finally:stop.set();thread.join();kernel.CloseHandle(handle)
        elapsed=time.perf_counter()-start
    if code:raise ValueError('Measurement process failed; inspect stderr')
    report=json.loads((output/(prefix+'.json')).read_bytes());c=report['cases'][0];b=c['execution_dependencies']['runtime']['bounded_work']
    if b['limit']!=limit or b['used']>limit or b['used']!=sum(b['categories'].values()):raise ValueError('Budget accounting differs')
    beginning=next(m for m in marks if m['line']=='bootstrap complete')
    refusal=next((m for m in marks if m['line'].startswith('refusal ')),None)
    ready=next((m for m in marks if m['line']=='modules complete'),None);end=refusal or ready
    row={'profile':limit,'case':case_id,'repeat':repeat,'runtime_sha256':digest(dll),'seconds_traced_initialization_to_outcome':end['seconds']-beginning['seconds'] if end else None,'outcome_working_set_mib':end['working_set_bytes']/1048576 if end and end['working_set_bytes'] else None,'peak_process_working_set_mib':peak[0]/1048576,'whole_process_seconds':elapsed,'initialization_passed':c['initialization_passed'],'contract_passed':c['contract_passed'],'first_unsupported_entry':c['first_unsupported_entry'],'work_used':b['used'],'work_limit':b['limit'],'markers':marks}
    if inspect is not None:row['case_summary']=inspect(report)
    return row

def run(baseline,candidate,output,runs):
    if not 1<=runs<=10:raise ValueError('Use 1 to 10 runs')
    output.mkdir(parents=True,exist_ok=False);rows=[]
    for repeat in range(1,runs+1):
        for case in ['mcm-en','eid-en']:
            for limit,binary in [(2000000,baseline),(5000000,candidate)]:
                row=measure(binary,limit,case,repeat,output);rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='markers'}),flush=True)
    summary={}
    for limit in [2000000,5000000]:
        summary[str(limit)]={}
        for case in ['mcm-en','eid-en']:
            samples=[r for r in rows if r['profile']==limit and r['case']==case];summary[str(limit)][case]={k:statistics.median(r[k] for r in samples) for k in ['seconds_traced_initialization_to_outcome','outcome_working_set_mib','peak_process_working_set_mib']}
    result={'schema':'isaac-incremental-budget-comparison-1','samples':rows,'summary_medians':summary,'timing_scope':'after untraced bootstrap until initialization completes or refuses; excludes report serialization','memory_scope':'process working set at outcome; peak includes resources, harness and serialization; not isolated tracking allocation','game_process_used':False,'oracle_enabled':False}
    write(output/'comparison.json',result);print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--runs',type=int,default=2);a=p.parse_args();run(a.baseline.resolve(),a.candidate.resolve(),a.output.resolve(),a.runs)
