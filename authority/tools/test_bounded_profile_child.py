"""Small reproducible pipe, capture-cap, and deadline checks; no Lua/game."""
import argparse,json,os,sys
from bounded_profile_child import collect
def run(out):
    cases=[('both-pipes',"import sys;sys.stdout.buffer.write(b'x'*65536);sys.stderr.buffer.write(b'y'*32768)",0),('output-limit',"import sys;sys.stdout.buffer.write(b'x'*(2*1024*1024))",1),('deadline',"import time;time.sleep(10)",2)];rows=[]
    for name,code,kind in cases:
        r=collect([sys.executable,'-B','-c',code],os.environ.copy(),None,timeout=.4 if kind==2 else 2)
        ok=(r['returncode']==0 and len(r['stdout'])==65536 and len(r['stderr'])==32768) if kind==0 else (r['output_limit_exceeded'] and len(r['stdout'])<=1024*1024) if kind==1 else r['timed_out']
        rows.append({'id':name,'passed':bool(ok),'seconds':r['seconds'],'stdout_bytes':len(r['stdout']),'stderr_bytes':len(r['stderr']),'timed_out':r['timed_out'],'output_limit_exceeded':r['output_limit_exceeded']})
    result={'schema':'bounded-profile-pipe-gate-1','passed':all(r['passed'] for r in rows),'cases':rows}
    with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    return result
if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.output)['passed'] else 1)
