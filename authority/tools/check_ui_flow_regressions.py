"""Re-run the original scene/object and sprite cases without UI-flow opt-in."""
import argparse,gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as f

def run(out):
    before=f.parent.protection.protection();rows=[]
    for group,manifest,previous in [('objects','research/model_objects_v1.json','reports/model-objects-v3/result.json.gz'),('sprites','research/sprite_state_v2.json','reports/sprite-state-v2/result.json.gz')]:
        baseline={c['id']:c['reports'][1]for c in json.loads(gzip.decompress((f.ROOT/previous).read_bytes()))['cases']};path=f.ROOT/manifest
        for case in f.load(path)['cases']:
            artifact,r=f.invoke(path,case);b=baseline[case['id']];passed=r is not None and not artifact['timed_out']and not artifact['output_limit_exceeded']and all(r.get(k)==b.get(k)for k in ['semantic','steps','first_unsupported_entry']);rows.append(dict(group=group,id=case['id'],passed=passed,artifact=artifact,report=r))
        print(json.dumps(dict(group=group,cases=sum(c['group']==group for c in rows),failed=[c['id']for c in rows if c['group']==group and not c['passed']])),flush=True)
    assert before==f.parent.protection.protection();result=dict(schema='ui-flow-legacy-regressions-1',passed=all(c['passed']for c in rows),cases=rows,binary_sha256=f.digest(f.EXE),driver_sha256=f.digest(Path(__file__)),work_limit=10000000,child_timeout_seconds=5,protected_files_unchanged=True);out.mkdir(parents=True,exist_ok=False);raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((out/'result.json.gz').read_bytes())==raw;return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.output.resolve())else 1)
