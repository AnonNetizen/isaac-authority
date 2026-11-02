"""Preserve the old boundary/observer gates in the new module executable."""
import argparse,json,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_frozen_modules as m
c=m.compact;b=c.b;ROOT=m.ROOT
def run(out):
    before=m.protected();out.mkdir(exist_ok=False,parents=True);start=time.perf_counter();rows=[]
    sources=[(b.reads.MANIFEST,'reads'),(b.writes.MANIFEST,'writes'),(b.old.MANIFEST,'handoff'),(b.compact.MANIFEST,'compact-reads'),(b.draws.MANIFEST,'draw-plans'),(c.MANIFEST,'compact-values')]
    for path,kind in sources:
        for case in json.loads(path.read_text(encoding='utf-8'))['cases']:
            if time.perf_counter()-start>60:raise RuntimeError('Short regression batch deadline')
            artifact,r=m.invoke(path,case);tests=[];proofs=[]
            if case.get('process_error'):tests=[dict(check='work-budget-rejection',passed=r is not None and case['process_error']in r.get('first_unsupported_entry',''))]
            elif r is None or 'semantic'not in r:tests=[dict(check='completed',passed=False)]
            elif kind=='compact-values':
                if case['kind']=='encoding-probe':tests=[dict(check='wire-encoding-probe',passed=r['steps'][0]['checked']==252 and r['steps'][0]['wire_bytes_equal_json'])]
                else:
                    remaining=10000000-r['budget']['used']
                    for s in r['steps']:
                        if s.get('metadata',{}).get('observed_sources'):
                            v,p,_=c.proof(s['metadata'],s['draws'],out/'verification-request.json',remaining);proofs.append(v);remaining-=p['analysis_work']+v['used_work']
                    tests=b.checks(case,r,proofs);tests.append(dict(check='combined-budget',passed=remaining>=0))
                a,prior=c.invoke(path,case);tests.append(dict(check='prior-observations-unchanged',passed=prior is not None and r['steps']==prior['steps']and r['semantic']==prior['semantic']))
            elif kind=='draw-plans':
                if case['check']=='rejected':tests=[dict(check='site-capacity-rejection',passed=case['error']in r['steps'][0].get('error',''))]
                elif case['check']=='analysis-rejected':
                    try:b.recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']);tests=[dict(check='analysis-capacity-rejection',passed=False)]
                    except RuntimeError as e:tests=[dict(check='analysis-capacity-rejection',passed=case['reason']in str(e))]
                else:tests=b.draws.check_plan(case,r,b.recipes.inspect(r['steps'][0]['metadata'],10000000-r['budget']['used']))
            else:tests=b.reads.checks(case,r)if kind=='reads'else b.writes.checks(case,r)if kind=='writes'else b.old.assertions(case,r)if kind=='handoff'else b.compact.checks(case,r)
            if r is not None:tests.append(dict(check='formal-limits-no-trace',passed=r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())and not r['full_trace_enabled']and not r['game_started']))
            row=dict(id=case['id'],suite=kind,passed=all(t['passed']for t in tests),checks=tests,artifact=artifact,proofs=proofs);rows.append(row)
            if not row['passed']:print(json.dumps(row),flush=True);break
        if not rows[-1]['passed']:break
    result=dict(schema='module-runtime-previous-regressions-1',passed=len(rows)==153 and all(r['passed']for r in rows)and before==m.protected(),cases=rows,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,game_started=False,full_trace_enabled=False,binary_sha256=m.old.digest(m.EXE),driver_sha256=m.old.digest(Path(__file__)))
    m.old.save(out/'result.json',result);print(json.dumps(dict(passed=result['passed'],cases=len(rows),seconds=result['seconds'])));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(0 if run(a.output.resolve())['passed']else 1)
