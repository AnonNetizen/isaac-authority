"""Keep old-mode expectations separate from SDK-enabled contracts."""
import argparse,gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_mod_sdk as s
import run_module_regressions as prior

def run(kind,out):
    if kind=='core':
        prior.m.EXE=s.EXE;prior.m.invoke=s.invoke;r=prior.run(out)
        p=out/'result.json';data=p.read_bytes();archive=p.with_name(p.name+'.gz');archive.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(archive.read_bytes())==data;p.unlink()
        request=out/'verification-request.json'
        if request.exists():assert request.resolve().is_relative_to(out.resolve())and not request.is_symlink();request.unlink()
        return r
    path={'objects':s.o.MANIFEST,'modules':s.o.MODULES,'gc':s.ROOT/'research/model_objects_gc_v1.json'}[kind]
    return s.run(path,out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['core','objects','modules','gc']);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.kind,a.output.resolve())['passed']else 1)
