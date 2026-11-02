"""Five-second real-source diagnostics only after current short gates."""
import argparse,sys,os
from pathlib import Path
sys.dont_write_bytecode=True
import run_audit_batch_initialization as base
from audit_wire import prefix
ROOT=base.ROOT
base.previous.DLL=ROOT/'build-audit-volume/Release/ia_lua533_audit_volume.dll';base.previous.EXE=base.previous.DLL.with_name('authority-audit-volume-real.exe')
base.previous.prefix=prefix
def run(out,gate,bench):
    prior=os.environ.pop('IA_AUDIT_WIRE_RAW',None)
    try:r=base.run(out,gate,bench)
    finally:
        if prior is not None:os.environ['IA_AUDIT_WIRE_RAW']=prior
    r['schema']='audit-volume-initialization-1';base.previous.save(out/'result.json',r);return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);p.add_argument('--benchmark',type=Path,required=True);a=p.parse_args();run(a.output.resolve(),a.gate.resolve(),a.benchmark.resolve())
