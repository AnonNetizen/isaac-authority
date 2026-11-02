"""One original regression or integrity preflight, supervised by a 5s parent."""
import argparse,contextlib,ctypes,hashlib,inspect,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
def memory_job():
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',ctypes.c_uint32),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',ctypes.c_uint32),('affinity',ctypes.c_size_t),('priority',ctypes.c_uint32),('scheduling',ctypes.c_uint32)]
    class IO(ctypes.Structure):_fields_=[(x,ctypes.c_uint64)for x in ['read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes']]
    class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_limit',ctypes.c_size_t),('job_limit',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateJobObjectW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p];k.CreateJobObjectW.restype=ctypes.c_void_p;k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetInformationJobObject.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32];k.AssignProcessToJobObject.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
    handle=k.CreateJobObjectW(None,None);quota=Extended();quota.basic.flags=0x2100;quota.process_limit=1024**3
    if not handle or not k.SetInformationJobObject(handle,9,ctypes.byref(quota),ctypes.sizeof(quota))or not k.AssignProcessToJobObject(handle,k.GetCurrentProcess()):raise RuntimeError('Cannot bound integrity/analysis worker memory')
    return handle
def main():
    p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--request',type=Path);p.add_argument('--inspect',type=Path);a=p.parse_args();job=memory_job()
    if a.inspect:
        import inspect_draw_plans
        request=json.loads(a.inspect.read_text(encoding='utf-8'));plan=inspect_draw_plans.inspect(request['capture'],request['available_work']);print(json.dumps(dict(plan=plan,worker_memory_limit=1024**3),separators=(',',':')));return
    import run_sprite_state as s
    import run_module_regressions as original
    s.setup();original.m.EXE=s.EXE;original.m.invoke=s.invoke
    with contextlib.redirect_stdout(io.StringIO()):
        if a.preflight:result=dict(protected=original.m.protected())
        else:
            request=json.loads(a.request.read_text(encoding='utf-8'));snapshot=json.loads(Path(request['snapshot']).read_text(encoding='utf-8'));original.m.protected=lambda:snapshot
            source=inspect.getsource(original.run)
            def change(text,x,y):assert text.count(x)==1,x;return text.replace(x,y)
            source=change(source,'def run(out):','def run(out,selected,case_id):')
            source=change(source,'out.mkdir(exist_ok=False,parents=True);','assert out.is_dir();')
            end="(c.MANIFEST,'compact-values')]";source=change(source,end,end+';sources=[x for x in sources if x[1]==selected]')
            source=change(source,"for case in json.loads(path.read_text(encoding='utf-8'))['cases']:","for case in [x for x in json.loads(path.read_text(encoding='utf-8'))['cases']if x['id']==case_id]:")
            source=change(source,'len(rows)==153','len(rows)==1');source=change(source,"m.old.save(out/'result.json',result);",'pass;')
            namespace=dict(original.__dict__);exec(compile(source,'<original-single-case-with-shared-preflight>','exec'),namespace)
            r=namespace['run'](Path(request['out']),request['suite'],request['id']);result=dict(result=r,derived_function_sha256=hashlib.sha256(source.encode()).hexdigest())
    result.update(worker_memory_limit=1024**3,preflight_shared=not a.preflight);print(json.dumps(result,separators=(',',':')))
if __name__=='__main__':main()
