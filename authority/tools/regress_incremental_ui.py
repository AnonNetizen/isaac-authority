"""Re-run preserved 166 cases on original DLLs with the updated shared runner."""
import argparse,gc,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,invoke,preserved,write
from run_slice3_ui_research import HISTORY,verify_inputs
from run_trace_research import verify_pristine
from validate import validate
from audit_baseline import audit
def run(binary,game,output):
    output.mkdir(parents=True,exist_ok=False)
    before={'historical_files':preserved(),'frozen':verify_inputs(ROOT,game),'pristine_lua':verify_pristine(),'saves':audit(ROOT.parent/'artifacts/authority-baseline-20261009')}
    write(output/'before.json',before);records={}
    for name,mode in HISTORY:
        print('Historical '+name,flush=True);dll=ROOT/'build-slice3-release/Release'/f'ia_lua533_{mode}.dll'
        report=invoke([binary/'authority-trace-research.exe','--suite',dll,digest(dll),game,ROOT,ROOT/'research'/name],output/(Path(name).stem+'.json'))
        original=json.loads((ROOT/'reports/slice3-final-verified'/(Path(name).stem+'-1.json')).read_bytes())
        identical=report['cases']==original['cases']
        records[name]={'cases':len(report['cases']),'complete_cases_identical':identical,'runtime_sha256':digest(dll),'manifest_sha256':digest(ROOT/'research'/name)}
        if not report['diagnostic_passed'] or not identical:raise ValueError('Historical behavior changed: '+name)
        del report,original;gc.collect()
    checks=validate(binary,game/'Lua5.3.3r.dll');write(output/'base-checks.json',checks)
    after={'historical_files':preserved(),'frozen':verify_inputs(ROOT,game),'saves':audit(ROOT.parent/'artifacts/authority-baseline-20261009')}
    write(output/'after.json',after)
    save=lambda a:[(f['file'],f['current_sha256']) for f in a['files']]
    if before['frozen']!=after['frozen'] or save(before['saves'])!=save(after['saves']):raise ValueError('Installed input or personal save changed')
    result={'schema':'isaac-incremental-regression-1','original_suites':records,'original_cases':sum(v['cases'] for v in records.values()),'saved_files_unchanged':len(after['saves']['files']),'frozen_inputs_unchanged':True,'historical_artifacts_unchanged':True,'new_shared_runner_sha256':digest(binary/'authority-trace-research.exe'),'game_process_used':False}
    write(output/'validation.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--game',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.binary.resolve(),a.game.resolve(),a.output.resolve())
