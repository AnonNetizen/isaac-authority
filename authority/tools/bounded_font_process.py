"""Bound both output streams while enforcing the existing five-second deadline."""
import subprocess,threading,time
REPORT_LIMIT=2*1024**2
DIAGNOSTIC_LIMIT=256*1024

def run(argv):
    start=time.perf_counter();p=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    data=[bytearray(),bytearray()];overflow=threading.Event();failures=[]
    def read(index,stream,limit):
        try:
            while True:
                part=stream.read(16384)
                if not part:break
                if len(part)>limit-len(data[index]):
                    data[index].extend(part[:limit-len(data[index])]);overflow.set()
                    try:p.kill()
                    except ProcessLookupError:pass
                    break
                data[index].extend(part)
        except Exception as e:failures.append(type(e).__name__)
        finally:stream.close()
    readers=[threading.Thread(target=read,args=(i,stream,limit),daemon=True)for i,stream,limit in [(0,p.stdout,REPORT_LIMIT),(1,p.stderr,DIAGNOSTIC_LIMIT)]]
    for reader in readers:reader.start()
    timeout=False
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:timeout=True;p.kill();p.wait(timeout=1)
    for reader in readers:reader.join(timeout=1)
    if any(reader.is_alive()for reader in readers):raise RuntimeError('CLI stream remained live after process termination')
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stdout=bytes(data[0]),stderr=bytes(data[1]),timed_out=timeout,output_limit_exceeded=overflow.is_set(),reader_failures=failures)
