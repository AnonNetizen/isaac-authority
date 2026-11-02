"""Run original EID text callbacks with the new scene/clock capability enabled."""
import argparse,copy,gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as f
ROOT=f.ROOT;MANIFEST=ROOT/'research/ui_flow_real_text_v1.json'

def freeze():
    data=copy.deepcopy(f.load(f.parent.REAL));data['schema']='ui-flow-real-text-1';data['cases']=[c for c in data['cases']if c['id'].endswith('-render-string')]
    for c in data['cases']:c['ui_flow_profile']=dict(path=f.PROFILE.relative_to(ROOT).as_posix(),sha256=f.digest(f.PROFILE));c['objects']['scene']['is_paused']=False
    f.freeze_json(MANIFEST,data)

def run(out):
    f.parent.EXE=f.EXE;f.parent.REF=f.REF;f.parent.invoke=f.invoke;passed=f.parent.run(MANIFEST,out)
    path=out/'result.json.gz';result=json.loads(gzip.decompress(path.read_bytes()));result['ui_flow_adapter_sha256']=f.digest(Path(__file__));raw=json.dumps(result,separators=(',',':')).encode();path.write_bytes(gzip.compress(raw,mtime=0));return passed

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output.resolve())else 1)
