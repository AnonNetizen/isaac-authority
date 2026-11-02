"""Keep the two original functional gates unchanged, including their failures."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_sparse_values as sparse
import run_world_view as world

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    world.EXE=sparse.EXE;world.REF=sparse.REF;world.invoke=sparse.invoke
    projection=world.run(world.PROJECTION,a.output/'projection')
    mixed=world.run(world.ROOT/'research/world_view_required_mixed_v1.json',a.output/'mixed')
    # A reproduced refusal is evidence, never a compatibility pass.
    sys.exit(0 if projection and mixed else 1)
