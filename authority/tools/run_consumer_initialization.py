"""Try frozen real initialization only after the complete bounded consumer gate."""
import argparse,gzip,hashlib,json,os,struct,subprocess,sys,time,zlib
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from run_incremental2 import digest
from audit_baseline import audit
DLL=ROOT/'build-consumers/Release/ia_lua533_consumers.dll';EXE=DLL.with_name('authority-consumers-real.exe')
REFERENCE=ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_reference.dll'
MANIFEST=ROOT/'research/ui_incremental_suite_10m_v1.json'
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def prefix(path):
    total=0;sequence=0;counts={};error=None
    with path.open('rb') as stream:
        while header:=stream.read(32):
            if len(header)!=32:error='partial header after forced termination';break
            magic,channel,identity,size,seq,crc,hcrc=struct.unpack('<IIIIQII',header)
            if size>8*1024*1024:error='record size exceeds frozen limit';break
            data=stream.read(size)
            if magic!=0x31414349 or seq!=sequence+1 or zlib.crc32(header[:28])!=hcrc:error='header integrity failure';break
            if len(data)!=size:error='partial record after forced termination';break
            if zlib.crc32(data)!=crc:error='payload integrity failure';break
            counts[str(channel)]=counts.get(str(channel),0)+1;sequence=seq;total+=32+size
    return {'complete_records':sequence,'complete_record_bytes':total,'channels':counts,'tail_error':error,'file_bytes':path.stat().st_size}
def run(out,gate_path):
    accepted=json.loads(gate_path.read_text(encoding='utf-8'))
    if not accepted.get('passed') or not accepted.get('complete_manifest') or accepted.get('schema')!='consumer-readsets-gate':raise RuntimeError('Complete consumer short gate must pass first')
    if digest(DLL)!=accepted['dll_sha256']:raise RuntimeError('Initialization DLL differs from accepted short gate')
    out.mkdir(parents=True,exist_ok=False);before=audit(ROOT.parent/'artifacts/authority-baseline-20261009');save(out/'save-before.json',before)
    suite=json.loads(MANIFEST.read_text(encoding='utf-8'));names=[c['id'] for c in suite['cases']];print(json.dumps({'available':names}),flush=True)
    selected=['mcm-zh','eid-zh','combined-zh']
    if not all(c in names for c in selected):raise RuntimeError('Expected frozen initialization cases missing')
    expected={}
    for c in suite['cases']:
        for mod in c['mods']:
            for p,h in mod['sha256'].items():expected[str(Path(mod['root'])/p)]=h
    def sources():return {p:digest(ROOT/'research/slice3_ui_inputs'/p) for p in expected}
    if sources()!=expected:raise RuntimeError('Frozen mod sources changed')
    started=time.perf_counter();deadline=started+45;rows=[]
    for name in selected:
        row={'id':name}
        for label,dll in [('reference',REFERENCE),('candidate',DLL)]:
            remaining=deadline-time.perf_counter()
            if remaining<=0:raise RuntimeError('Bounded initialization batch deadline reached')
            timeout=min(5,remaining);env=os.environ.copy();env['IA_CONSUMER_VERIFY']='1'
            journal=out/(name+'.audit');env['IA_COMPACT_AUDIT_FILE']=str(journal)
            if label=='reference':env.pop('IA_COMPACT_AUDIT_FILE',None)
            command=[str(EXE),'--suite',str(dll),digest(dll),str(ROOT),str(MANIFEST),name,'trace' if label=='candidate' else 'plain']
            begin=time.perf_counter();report=None;timed_out=False
            try:
                process=subprocess.run(command,capture_output=True,env=env,timeout=timeout)
                stdout,stderr=process.stdout,process.stderr;code=process.returncode
                if len(stdout)>1024*1024:raise RuntimeError('Initialization report exceeds 1 MiB')
                if code==0:report=json.loads(stdout)
            except subprocess.TimeoutExpired as e:
                timed_out=True;stdout=e.stdout or b'';stderr=e.stderr or b'';code=None
            item={'seconds':time.perf_counter()-begin,'timeout_seconds':timeout,'timed_out':timed_out,'returncode':code,'stderr_tail':stderr[-8192:].decode('utf-8',errors='replace'),'report':report,'work_limit':10000000}
            if journal.exists():
                if journal.stat().st_size>16*1024*1024:raise RuntimeError('Initialization audit disk cap exceeded')
                item['audit_prefix']=prefix(journal);raw_hash=digest(journal);packed=journal.with_suffix('.audit.gz')
                with journal.open('rb') as src,packed.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as dest:
                    while block:=src.read(65536):dest.write(block)
                with gzip.open(packed,'rb') as f:
                    if hashlib.file_digest(f,'sha256').hexdigest()!=raw_hash:raise RuntimeError('Compressed failure evidence differs')
                item['audit_evidence']={'file':packed.name,'raw_sha256':raw_hash,'compressed_sha256':digest(packed),'compressed_bytes':packed.stat().st_size};journal.unlink()
            row[label]=item;save(out/(name+'-'+label+'.json'),item);print(json.dumps({'id':name,'label':label,'seconds':item['seconds'],'timed_out':timed_out,'first_unsupported':report.get('case',{}).get('first_unsupported_entry') if report else None}),flush=True)
        rows.append(row)
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');save(out/'save-after.json',after)
    result={'schema':'bounded-consumer-real-initialization-1','cases':rows,'seconds':time.perf_counter()-started,'case_timeout_seconds':5,'batch_timeout_seconds':45,'work_limit':10000000,'dll_sha256':digest(DLL),'manifest_sha256':digest(MANIFEST),'mod_sources_unchanged':sources()==expected,'mod_source_count':len(expected),'save_files_unchanged':before['files']==after['files'],'game_started':False,'compatibility_passed':all((r['candidate'].get('report') or {}).get('case',{}).get('compatibility_passed',False) for r in rows),'short_gate':str(gate_path),'no_unbounded_retry':True}
    save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False));return result
def recover_summary(out,gate_path):
    if (out/'result.json').exists():raise RuntimeError('Summary already exists')
    suite=json.loads(MANIFEST.read_text(encoding='utf-8'));expected={}
    for c in suite['cases']:
        for mod in c['mods']:
            for p,h in mod['sha256'].items():expected[str(Path(mod['root'])/p)]=h
    rows=[{'id':name,**{label:json.loads((out/(name+'-'+label+'.json')).read_text(encoding='utf-8')) for label in ['reference','candidate']}} for name in ['mcm-zh','eid-zh','combined-zh']]
    before=json.loads((out/'save-before.json').read_text(encoding='utf-8'));after=json.loads((out/'save-after.json').read_text(encoding='utf-8'))
    result={'schema':'bounded-consumer-real-initialization-1','cases':rows,'seconds':None,'child_seconds_total':sum(r[label]['seconds'] for r in rows for label in ['reference','candidate']),'case_timeout_seconds':5,'batch_timeout_seconds':45,'work_limit':10000000,'dll_sha256':digest(DLL),'manifest_sha256':digest(MANIFEST),'mod_sources_unchanged':all(digest(ROOT/'research/slice3_ui_inputs'/p)==h for p,h in expected.items()),'mod_source_count':len(expected),'save_files_unchanged':before['files']==after['files'],'game_started':False,'compatibility_passed':all((r['candidate'].get('report') or {}).get('case',{}).get('compatibility_passed',False) for r in rows),'short_gate':str(gate_path),'no_unbounded_retry':True,'summary_recovered_from_completed_cases':True,'reason':'Timeout reports were saved; aggregation attempted .get on None. No simulation rerun.'}
    save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--gate',required=True,type=Path);p.add_argument('--recover-summary',action='store_true');a=p.parse_args()
    (recover_summary if a.recover_summary else run)(a.output.resolve(),a.gate.resolve())
