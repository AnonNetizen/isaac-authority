"""Reuse old-mode and SDK expectations with value support opt-in disabled."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_value_objects as v
import run_sdk_regressions as prior
def main(kind,out):
    v.s.EXE=v.EXE;v.s.REF=v.REF;v.s.invoke=v.invoke
    if kind=='sdk':return v.s.run(v.s.CURRENT,out)
    return prior.run(kind,out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['core','objects','modules','gc','sdk']);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if main(a.kind,a.output.resolve())['passed']else 1)
