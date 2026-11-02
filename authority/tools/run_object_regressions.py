"""Run the 153 sealed old expectations against the optional object runtime."""
import gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_model_objects as o
import run_module_regressions as prior

def main(out):
    prior.m.EXE=o.EXE
    prior.m.invoke=o.invoke
    r=prior.run(out)
    r['object_runtime_abi']='ia-lua533-model-objects-1';r['object_profile_enabled']=False
    r['object_regression_driver_sha256']=o.old.digest(Path(__file__))
    p=out/'result.json';data=(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8');p.write_bytes(data)
    archive=p.with_name(p.name+'.gz');archive.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(archive.read_bytes())==p.read_bytes();p.unlink()
    # Verifier requests are derivable from frozen inputs and do not hold results.
    for name in ['verification-request.json']:
        request=out/name
        if request.exists():
            assert request.resolve().is_relative_to(out.resolve())and not request.is_symlink();request.unlink()
    return r

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if main(a.output.resolve())['passed']else 1)
