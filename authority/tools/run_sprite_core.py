"""Original assertions with shared preflight and independently bounded analysis."""
import argparse,gzip,hashlib,inspect,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_sprite_state as s
import run_module_regressions as original
WORKER=Path(__file__).with_name('sprite_core_worker.py')
def call(args):
 start=time.perf_counter()
 try:p=subprocess.run([sys.executable,'-B',str(WORKER),*args],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
 except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second worker timeout; killed and reaped'),None
 if len(p.stdout)>2*1024**2:raise RuntimeError('Analysis output capacity exceeded')
 try:r=json.loads(p.stdout)
 except ValueError:r=None
 return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace')),r

def main(out,resume=None):
 s.setup();original.m.EXE=s.EXE;original.m.invoke=s.invoke;out.mkdir(parents=True,exist_ok=False)
 binary=s.old.digest(s.EXE);audit,before=call(['--preflight'])
 if not before:raise RuntimeError('Preflight failed: '+audit['stderr'])
 real_protected=original.m.protected;original.m.protected=lambda:before['protected'];analyses=[];request=out/'analysis-request.json'
 def bounded_inspect(capture,available_work):
  request.write_text(json.dumps(dict(capture=capture,available_work=available_work)),encoding='utf-8');a,r=call(['--inspect',str(request)]);analyses.append(a)
  if a['returncode']or not r:raise RuntimeError('Bounded analysis failed: '+a['stderr'])
  return r['plan']
 original.b.recipes.inspect=bounded_inspect
 source=inspect.getsource(original.run)
 def change(t,x,y):assert t.count(x)==1,x;return t.replace(x,y)
 derived=change(source,'def run(out):','def run(out,selected,low,high):')
 derived=change(derived,'out.mkdir(exist_ok=False,parents=True);','assert out.is_dir();')
 end="(c.MANIFEST,'compact-values')]";derived=change(derived,end,end+';sources=[x for x in sources if x[1]==selected]')
 derived=change(derived,"for case in json.loads(path.read_text(encoding='utf-8'))['cases']:","for case in json.loads(path.read_text(encoding='utf-8'))['cases'][low:high]:")
 derived=change(derived,'len(rows)==153','len(rows)==high-low');derived=change(derived,"m.old.save(out/'result.json',result);",'pass;')
 derived=change(derived,'rows.append(row)',"rows.append(row);print(json.dumps(dict(case_finished=case['id'],passed=row['passed'])),flush=True)")
 namespace=dict(original.__dict__);exec(compile(derived,'<unchanged-assertions-bounded-inspection>','exec'),namespace)
 b=original.b;c=original.c;suites=[(b.reads.MANIFEST,'reads'),(b.writes.MANIFEST,'writes'),(b.old.MANIFEST,'handoff'),(b.compact.MANIFEST,'compact-reads'),(b.draws.MANIFEST,'draw-plans'),(c.MANIFEST,'compact-values')]
 rows=[];groups=[];expected=[];start=time.perf_counter();resume_sha=None
 full_expected=[(kind,x['id'])for path,kind in suites for x in json.loads(path.read_text(encoding='utf-8'))['cases']]
 if resume:
  previous=json.loads(gzip.decompress(resume.read_bytes()));assert previous['binary_sha256']==binary
  rows=previous['cases'];groups=previous['groups'];analyses.extend(previous['analyses']);resume_sha=s.old.digest(resume)
  assert all(x['passed']and all(t['passed']for t in x['checks'])for x in rows)and [(x['suite'],x['id'])for x in rows]==full_expected[:len(rows)]
  assert all(g['passed']for g in groups)and sum(g['count']for g in groups)==len(rows)
 completed={(x['suite'],x['id'])for x in rows}
 for path,kind in suites:
  cases=json.loads(path.read_text(encoding='utf-8'))['cases'];expected.extend((kind,x['id'])for x in cases)
  width=1 if kind=='compact-values'else 6
  for low in range(0,len(cases),width):
   high=min(low+width,len(cases))
   if all((kind,x['id'])in completed for x in cases[low:high]):continue
   r=namespace['run'](out,kind,low,high);rows.extend(r['cases']);groups.append(dict(suite=kind,low=low,high=high,count=len(r['cases']),passed=r['passed'],seconds=r['seconds']))
   raw=json.dumps(dict(complete=False,groups=groups,cases=rows,analyses=analyses,binary_sha256=binary),separators=(',',':')).encode();(out/'checkpoint.json.gz').write_bytes(gzip.compress(raw,mtime=0))
   if not r['passed']:break
  if not groups[-1]['passed']:break
 original.m.protected=real_protected;after_audit,after=call(['--preflight']);coverage=len(rows)==153 and [(x['suite'],x['id'])for x in rows]==expected
 passed=coverage and all(x['passed']for x in groups)and after is not None and before['protected']==after['protected']and binary==s.old.digest(s.EXE)
 result=dict(schema='sprite-core-supervised-analysis-1',passed=passed,cases=rows,groups=groups,analyses=analyses,audits=[audit,after_audit],resumed_checkpoint_sha256=resume_sha,preflight_shared=True,protected_files_unchanged=after is not None and before['protected']==after['protected'],seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,worker_timeout_seconds=5,worker_memory_limit_bytes=1024**3,game_started=False,full_trace_enabled=False,binary_sha256=binary,driver_sha256=s.old.digest(Path(__file__)),worker_sha256=s.old.digest(WORKER),original_driver_sha256=s.old.digest(Path(original.__file__)),derived_function_sha256=hashlib.sha256(derived.encode()).hexdigest(),ordered_case_coverage_verified=coverage)
 raw=(json.dumps(result,separators=(',',':'))+'\n').encode();p=out/'result.json.gz';p.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(p.read_bytes())==raw
 for p in [out/'checkpoint.json.gz',request,out/'verification-request.json']:
  if p.exists():assert p.resolve().is_relative_to(out.resolve())and not p.is_symlink();p.unlink()
 print(json.dumps(dict(finished=True,passed=passed,cases=len(rows),analyses=len(analyses))),flush=True);return passed
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',type=Path);a=p.parse_args();sys.exit(0 if main(a.output.resolve(),a.resume.resolve()if a.resume else None)else 1)
