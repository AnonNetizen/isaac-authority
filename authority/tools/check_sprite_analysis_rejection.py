"""Reproduce the frozen expected analysis refusal under the same limits."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_sprite_core as core

def main():
    s=core.s;s.setup();manifest=core.original.b.draws.MANIFEST
    case=next(c for c in json.loads(manifest.read_text(encoding='utf-8'))['cases']if c['id']=='global-node-limit')
    assert case['check']=='analysis-rejected'
    artifact,result=s.invoke(manifest,case)
    assert artifact['returncode']==0 and result is not None
    request=dict(capture=result['steps'][0]['metadata'],available_work=10000000-result['budget']['used'])
    out=s.ROOT/'reports/sprite-state-verification-v2';out.mkdir(exist_ok=False)
    temporary=out/'request.json';temporary.write_text(json.dumps(request),encoding='utf-8')
    try:analysis,plan=core.call(['--inspect',str(temporary)])
    finally:
        assert temporary.resolve().is_relative_to(out.resolve())and not temporary.is_symlink()
        temporary.unlink()
    expected='RuntimeError: Draw recipe '+case['reason']
    passed=analysis['returncode']==1 and analysis['seconds']<5 and analysis['stderr'].strip().endswith(expected)and plan is None
    record=dict(schema='sprite-analysis-refusal-proof-1',passed=passed,id=case['id'],manifest=manifest.relative_to(s.ROOT).as_posix(),manifest_sha256=s.old.digest(manifest),binary_sha256=s.old.digest(s.EXE),worker_sha256=s.old.digest(core.WORKER),request=request,request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest(),artifact=artifact,analysis=analysis,expected_error=expected,work_limit=10000000,worker_timeout_seconds=5,worker_memory_limit_bytes=1024**3)
    raw=(json.dumps(record,separators=(',',':'))+'\n').encode();(out/'analysis-rejection.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    print(json.dumps(dict(passed=passed,case=case['id'],native_seconds=artifact['seconds'],analysis_seconds=analysis['seconds'],used_work=result['budget']['used'])))
    return passed
if __name__=='__main__':sys.exit(0 if main()else 1)
