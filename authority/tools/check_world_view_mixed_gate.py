"""Required mixed-callback compatibility gate; current refusal is a functional failure."""
import argparse,copy,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as w
MANIFEST=w.ROOT/'research/world_view_required_mixed_v1.json'
def freeze():
    c=copy.deepcopy(next(c for c in w.parent.f.load(w.MANIFEST)['cases']if c['id']=='authority-query-timepoints'))
    c.update(id='required-same-callback-query-timeline-and-write-isolation',kind='required-functional-mixed',steps=[w.dispatch(event=1,role='host'),dict(w.dispatch(event=1),phase='presentation'),w.ev('return Trace,P.Position.X,Seeds:HasSeedEffect(10)')],values=w.values('false:160.0>true:17.0',17.0,True))
    w.parent.f.freeze_json(MANIFEST,dict(schema='required-mixed-callback-gate-1',work_limit=10000000,timeout_seconds=5,cases=[c]))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();freeze();sys.exit(0 if w.run(MANIFEST,a.output)else 1)
