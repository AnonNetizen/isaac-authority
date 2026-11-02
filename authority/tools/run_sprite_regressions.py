"""Old manifests stay frozen; new resource/state profile remains opt-in."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_sprite_state as s
import run_value_regressions as prior
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('kind',choices=['services','values','core','sdk','objects','modules','gc']);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s.setup()
 r=s.e.run(s.e.CURRENT,a.output.resolve())if a.kind=='services'else(s.e.v.run(s.e.v.CURRENT,a.output.resolve())if a.kind=='values'else prior.main(a.kind,a.output.resolve()))
 sys.exit(0 if r['passed']else 1)
