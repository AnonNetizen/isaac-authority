"""Keep every prior value/SDK/model expectation unchanged."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_engine_services as e
import run_value_regressions as prior
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('kind',choices=['values','core','objects','modules','gc','sdk']);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 e.setup()
 r=e.v.run(e.v.CURRENT,a.output.resolve())if a.kind=='values'else prior.main(a.kind,a.output.resolve())
 sys.exit(0 if r['passed']else 1)
