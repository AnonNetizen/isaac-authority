"""Check original callback regressions and native protocol font compatibility."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_font_capture as f

WIRE=f.ROOT/'build-font-capture/Release/authority-font-wire-check.exe'
def archived(path):return json.loads(gzip.decompress(path.read_bytes()))
def save(out,result):
    out.mkdir(parents=True,exist_ok=False);raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((out/'result.json.gz').read_bytes())==raw

def callbacks(out):
    before=f.protection.protection();baseline={c['id']:c['reports'][1]for c in archived(f.ROOT/'reports/font-metrics-callbacks-v2/result.json.gz')['cases']};manifest=f.old.c.CURRENT;rows=[]
    for case in f.load(manifest)['cases']:
        a,p=f.invoke(manifest,case);b=baseline[case['id']];passed=p is not None and not a['timed_out']and not a['output_limit_exceeded']and p.get('semantic')==b.get('semantic')and p.get('steps')==b.get('steps')and p.get('first_unsupported_entry')==b.get('first_unsupported_entry');rows.append(dict(id=case['id'],passed=passed,artifact=a,report=p));print(json.dumps(dict(id=case['id'],passed=passed)),flush=True)
    assert before==f.protection.protection()
    result=dict(schema='font-capture-callback-regressions-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=f.digest(manifest),binary_sha256=f.digest(f.EXE),driver_sha256=f.digest(Path(__file__)),work_limit=10000000,child_timeout_seconds=5,protected_files_unchanged=True);save(out,result);return result['passed']

def wire(out):
    frames=[];sources={}
    for name in ['font-capture-v3','font-capture-real-v2']:
        path=f.ROOT/'reports'/name/'result.json.gz';source=archived(path);assert source['passed'];sources[path.relative_to(f.ROOT).as_posix()]=f.digest(path)
        for case in source['cases']:
            report=case['reports'][1]
            if report is None:continue
            for step in report.get('steps',[]):
                commands=[x for x in step.get('draws',[])if x.get('op')=='font']
                if commands:frames.append(dict(commands=commands))
    assert frames
    def execute(body):
        body=dict(body,manifest=f.digest(f.PROFILE));start=time.perf_counter();p=subprocess.run([str(WIRE)],input=json.dumps(body,separators=(',',':')).encode(),capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW);report=json.loads(p.stdout);return dict(returncode=p.returncode,seconds=time.perf_counter()-start,report=report,stderr_hex=p.stderr.hex())
    good=execute(dict(frames=frames));assert good['returncode']==0 and good['report']['commands']==sum(len(x['commands'])for x in frames)
    refusals=[]
    for name,mutate in [
        ('invalid-byte-encoding',lambda c:c.update(text_hex='gg')),
        ('invalid-resource-path',lambda c:c.update(asset='../outside.fnt')),
        ('invalid-coordinate',lambda c:c.update(x=None)),
        ('invalid-settings-flag',lambda c:c['settings'].update(auto_wrap=1)),
        ('packet-capacity',lambda c:c.update(text_hex='61'*30000))]:
        c=copy.deepcopy(frames[0]['commands'][0]);mutate(c);r=execute(dict(frames=[dict(commands=[copy.deepcopy(c)for _ in range(12)]if name=='packet-capacity'else[c])]))
        refusals.append(dict(id=name,passed=r['returncode']==1 and r['report']['passed']==False,result=r))
    result=dict(schema='font-capture-native-wire-1',passed=good['returncode']==0 and all(x['passed']for x in refusals),valid=good,refusals=refusals,sources=sources,binary_sha256=f.digest(WIRE),runtime_sha256=f.digest(f.EXE),driver_sha256=f.digest(Path(__file__)),native_core_sha256=f.digest(f.ROOT/'build-ui-incremental-encoded/Release/authority_core.lib'),child_timeout_seconds=5,rendering_verified=False,network_connection_verified=False);save(out,result);print(json.dumps(result));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['callbacks','wire']);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if(callbacks if a.phase=='callbacks'else wire)(a.output.resolve())else 1)
