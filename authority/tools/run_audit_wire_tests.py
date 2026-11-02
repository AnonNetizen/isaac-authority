"""Bounded native codec/recovery and independent malformed-wire checks."""
import argparse,json,os,struct,subprocess,sys,time,zlib
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental2 import digest
from audit_wire import prefix,unpack
ROOT=Path(__file__).resolve().parents[1];EXE=ROOT/'build-audit-volume/Release/authority-audit-wire-tests.exe';MANIFEST=ROOT/'research/audit_wire_tests_v1.json'
NAMES=['roundtrip','workspace-bound','wire-parity','bad-tokens','physical-quota','corrupt-wire','encoded-recovery-save','encoded-recovery-private','encoded-recovery-draw']
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def freeze():
    spec={'schema':'audit-wire-tests-1','work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':60,'native_source_sha256':digest(ROOT/'audit_volume_runtime/wire_tests.cpp'),'parent_fixture_sha256':digest(ROOT/'audit_batch_runtime/journal_tests.cpp'),'cases':NAMES}
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text())!=spec:raise RuntimeError('Frozen codec fixture changed')
    else:save(MANIFEST,spec)
def run(out):
    spec=json.loads(MANIFEST.read_text());assert spec['native_source_sha256']==digest(ROOT/'audit_volume_runtime/wire_tests.cpp')
    out.mkdir(parents=True,exist_ok=False);started=time.perf_counter();rows=[]
    for name in spec['cases']:
        remaining=60-(time.perf_counter()-started)
        if remaining<=0:raise RuntimeError('Codec batch deadline reached')
        target=out/name;target.mkdir();env=os.environ.copy();env.pop('IA_AUDIT_WIRE_RAW',None);env.pop('IA_AUDIT_IMMEDIATE',None)
        begin=time.perf_counter()
        try:p=subprocess.run([str(EXE),name,str(target)],capture_output=True,env=env,timeout=min(5,remaining));code=p.returncode;stdout=p.stdout;stderr=p.stderr;timeout=False
        except subprocess.TimeoutExpired as e:code=None;stdout=e.stdout or b'';stderr=e.stderr or b'';timeout=True
        if len(stdout)>64*1024:raise RuntimeError('Codec report too large')
        report=json.loads(stdout) if stdout else None;passed=not timeout and code==0 and report and report.get('passed') is True;files=[]
        for path in target.iterdir():
            if path.is_symlink() or path.suffix!='.audit' or path.resolve().parent!=target.resolve() or path.stat().st_size>16*1024*1024:raise RuntimeError('Unexpected codec artifact')
            decoded=prefix(path);files.append({'file':path.name,'sha256':digest(path),'prefix':decoded})
            if name not in ['corrupt-wire','encoded-recovery-save','encoded-recovery-private','encoded-recovery-draw']:passed=passed and decoded['tail_error'] is None
            if name.startswith('encoded-recovery-') and path.name=='failed.audit':passed=passed and decoded['complete_record_bytes']==report['result']['failed']['submitted_bytes']
        if name=='wire-parity' and passed:
            a=next(f for f in files if f['file']=='raw.audit');b=next(f for f in files if f['file']=='packed.audit');passed=a['prefix']['canonical_sha256']==b['prefix']['canonical_sha256'] and b['prefix']['compressed_records']>0 and b['prefix']['file_bytes']<a['prefix']['file_bytes']
        if passed:
            for path in target.iterdir():path.unlink()
            target.rmdir()
        rows.append({'id':name,'passed':bool(passed),'seconds':time.perf_counter()-begin,'timed_out':timeout,'returncode':code,'stderr':stderr[-8192:].decode('utf-8',errors='replace'),'report':report,'files':files});save(out/'progress.json',{'cases':rows});print(json.dumps({'id':name,'passed':bool(passed)}),flush=True)
    good=struct.pack('<II',128,zlib.crc32(b'A'*128))+bytes([0,65,0xfb,1,0]);assert unpack(good)==b'A'*128
    malformed=[struct.pack('<II',262145,0)+b'\0A',struct.pack('<II',128,0)+bytes([0x80,0,0]),struct.pack('<II',128,0)+bytes([127,65]),good[:-1],struct.pack('<II',128,1)+good[8:]];independent=[]
    for number,data in enumerate(malformed):
        try:unpack(data);ok=False
        except ValueError:ok=True
        independent.append({'id':number,'passed':ok})
    result={'schema':'audit-wire-gate-1','passed':all(r['passed'] for r in rows) and all(r['passed'] for r in independent),'cases':rows,'independent_malformed':independent,'seconds':time.perf_counter()-started,'case_timeout_seconds':5,'batch_timeout_seconds':60,'work_limit':10000000,'exe_sha256':digest(EXE),'manifest_sha256':digest(MANIFEST),'implementation_sha256':digest(ROOT/'audit_volume_runtime/wire_codec.hpp')};save(out/'result.json',result);(out/'progress.json').unlink();return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve())['passed'] else 1)
