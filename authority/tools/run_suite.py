"""Run the frozen coin-model suite twice without attaching to the game; save reproducibility evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

def run(binary_dir,lua,source,manifest,output):
    reports=[]
    command=[str(binary_dir/'authority-suite-tests.exe'),str(lua),str(lua.parent),str(source),str(manifest)]
    for _ in range(2):
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        if result.returncode:raise RuntimeError(result.stderr or result.stdout)
        reports.append(json.loads(result.stdout))
    if reports[0]!=reports[1]:raise ValueError('Fresh runs differ')
    report=reports[0]
    report['repeat_runs_identical']=True
    report['binary_sha256']={name:hashlib.sha256((binary_dir/name).read_bytes()).hexdigest()
                             for name in ('authority-suite-tests.exe','isaac_authority_probe.dll')}
    with output.open('x',encoding='utf-8') as target:json.dump(report,target,indent=2)
    return {k:report[k] for k in ('expected_outcomes_passed','failed','skipped','presentation_gate_passed','repeat_runs_identical')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('binary-dir','lua-runtime','source','manifest','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.binary_dir.resolve(),args.lua_runtime.resolve(),args.source.resolve(),args.manifest.resolve(),args.output.resolve())))
