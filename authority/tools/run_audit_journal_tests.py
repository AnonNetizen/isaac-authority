"""Frozen Journal boundary/recovery tests: 5s per child, 60s batch."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import digest
from run_consumer_initialization import prefix
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build-audit-batch/Release/authority-audit-journal-tests.exe'
MANIFEST=ROOT/'research/audit_batch_journal_v1.json'
NAMES=['empty-close','byte-parity','boundaries','large-stream','read-then-append','execution-read-guard','quota','work-budget','short-write','partial-write','flush-failure','close-failure','corruption','thread-guard','recovery-save','recovery-private','recovery-draw','duplicates','abort-unsealed','kill-pending']
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def freeze():
    harness=ROOT/'audit_batch_runtime/journal_tests.cpp'
    spec={'schema':'audit-batch-journal-1','work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':60,'buffer_capacity':262144,'harness_sha256':digest(harness),'cases':[{'id':n,'exit':73 if n=='kill-pending' else 0} for n in NAMES]}
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text())!=spec:raise RuntimeError('Frozen Journal manifest differs')
    else:save(MANIFEST,spec)
    print(json.dumps({'manifest_sha256':digest(MANIFEST),'cases':len(NAMES)}))
def run(out):
    spec=json.loads(MANIFEST.read_text());assert spec['harness_sha256']==digest(ROOT/'audit_batch_runtime/journal_tests.cpp')
    out.mkdir(parents=True,exist_ok=False);rows=[];started=time.perf_counter()
    for case in spec['cases']:
        remaining=60-(time.perf_counter()-started)
        if remaining<=0:raise RuntimeError('Journal batch deadline reached')
        target=out/case['id'];target.mkdir();env=os.environ.copy();env.pop('IA_AUDIT_IMMEDIATE',None)
        begin=time.perf_counter();timed_out=False
        try:p=subprocess.run([str(EXE),case['id'],str(target)],env=env,capture_output=True,timeout=min(5,remaining));stdout,stderr,code=p.stdout,p.stderr,p.returncode
        except subprocess.TimeoutExpired as e:timed_out=True;stdout=e.stdout or b'';stderr=e.stderr or b'';code=None
        if len(stdout)>64*1024:raise RuntimeError('Journal result exceeds bound')
        report=json.loads(stdout) if stdout else None
        passed=not timed_out and code==case['exit'] and report is not None and (report.get('passed') is True or case['id']=='kill-pending' and report.get('forced_exit') is True)
        files=[]
        for path in target.iterdir():
            if path.suffix!='.audit' or path.is_symlink() or path.resolve().parent!=target.resolve():raise RuntimeError('Unexpected Journal output')
            if path.stat().st_size>16*1024*1024:raise RuntimeError('Journal file quota exceeded')
            physical=prefix(path);files.append({'file':path.name,'sha256':digest(path),'prefix':physical})
            if case['id'] not in ['short-write','partial-write','corruption','recovery-save','recovery-private','recovery-draw']:passed=passed and physical['tail_error'] is None
            if case['id']=='kill-pending':passed=passed and physical['complete_records']==1 and physical['file_bytes']==64
            if case['id'].startswith('recovery-') and path.name=='failed.audit':passed=passed and physical['complete_record_bytes']==report['result']['failed']['submitted_bytes']
        if passed:
            for path in target.iterdir():path.unlink()
            target.rmdir()
        row={'id':case['id'],'passed':bool(passed),'seconds':time.perf_counter()-begin,'timed_out':timed_out,'returncode':code,'stderr':stderr[-8192:].decode('utf-8',errors='replace'),'report':report,'files':files};rows.append(row)
        save(out/'progress.json',{'cases':rows});print(json.dumps({'id':case['id'],'passed':row['passed'],'seconds':row['seconds']}),flush=True)
    result={'schema':'bounded-journal-gate-1','passed':all(r['passed'] for r in rows),'cases':rows,'seconds':time.perf_counter()-started,'case_timeout_seconds':5,'batch_timeout_seconds':60,'work_limit':10000000,'buffer_capacity':262144,'exe_sha256':digest(EXE),'manifest_sha256':digest(MANIFEST),'harness_sha256':spec['harness_sha256'],'rollback_scope':'transactional coin/config/private/RNG/save/draw model; failed context abandoned; accepted history replayed in new context'}
    save(out/'result.json',result);(out/'progress.json').unlink();return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve())['passed'] else 1)
