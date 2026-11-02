"""Drain both Windows pipes while polling fixed-size progress; never wait on EOF first."""
import subprocess,threading,time
def collect(command,env,page,timeout=5):
    if timeout>5:raise RuntimeError('Child timeout cannot exceed 5s')
    started=time.perf_counter();process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    captured=[bytearray(),bytearray()];overflow=threading.Event();errors=[]
    def drain(stream,index,limit):
        try:
            while chunk:=stream.read(4096):
                remaining=limit-len(captured[index]);captured[index].extend(chunk[:max(0,remaining)])
                if len(chunk)>remaining:
                    overflow.set()
                    if process.poll() is None:process.kill()
                    break
        except Exception as error:errors.append(str(error));overflow.set()
        finally:stream.close()
    workers=[threading.Thread(target=drain,args=(process.stdout,0,1024*1024),daemon=True),threading.Thread(target=drain,args=(process.stderr,1,64*1024),daemon=True)]
    for worker in workers:worker.start()
    points=[];timed_out=False
    try:
        while process.poll() is None:
            sample=page.read() if page else None
            if sample and (not points or sample['checkpoints']!=points[-1]['checkpoints']):
                sample['elapsed_seconds']=time.perf_counter()-started;points.append(sample)
                if len(points)>64:overflow.set();process.kill();break
            remaining=timeout-(time.perf_counter()-started)
            if remaining<=0:timed_out=True;process.kill();break
            try:process.wait(timeout=min(.1,remaining))
            except subprocess.TimeoutExpired:pass
        process.wait(timeout=1)
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=1)
        for worker in workers:worker.join(timeout=1)
    if any(worker.is_alive() for worker in workers):raise RuntimeError('Bounded output worker did not close')
    if errors:raise RuntimeError('Bounded output drain failed: '+str(errors))
    sample=page.read() if page else None
    if sample:sample['elapsed_seconds']=time.perf_counter()-started;points.append(sample)
    return {'stdout':bytes(captured[0]),'stderr':bytes(captured[1]),'returncode':process.returncode,'timed_out':timed_out,'output_limit_exceeded':overflow.is_set(),'progress':points,'seconds':time.perf_counter()-started}
