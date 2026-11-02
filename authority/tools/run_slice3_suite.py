"""Run a frozen standalone suite and retain complete evidence without UI access."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from freeze_suite import digest

def run(binary,game,root,manifest,output,mode='slice3'):
    dll=binary/('ia_lua533_'+mode+'.dll');runner=binary/('authority-'+mode+'-research.exe')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:
        result=subprocess.run([str(runner),'--suite',str(dll),digest(dll),str(game),str(root),str(manifest)],stdout=stream,stderr=subprocess.PIPE,timeout=1200)
    if result.stderr:output.with_suffix('.stderr').write_bytes(result.stderr)
    report=json.loads(output.read_text())
    summary={'report':str(output),'sha256':digest(output),'returncode':result.returncode,'diagnostic_passed':report['diagnostic_passed'],'cases':len(report['cases']),
             'failed':[{'id':c['id'],'error':c.get('error'), 'frames':[{'error':f.get('error'),'outcome':f['outcome'],'passed':f['passed']} for f in c['frames']]} for c in report['cases'] if not c['passed']]}
    print(json.dumps(summary));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','game','root','manifest','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--mode',default='slice3');a=p.parse_args()
    s=run(*[getattr(a,n).resolve() for n in ('binary','game','root','manifest','output')],a.mode)
    raise SystemExit(0 if s['diagnostic_passed'] else 2)
