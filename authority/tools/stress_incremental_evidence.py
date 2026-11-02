"""Repeat a frozen fixture without changing graph IDs or removing evidence."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,invoke,cache_witnesses,write

def run(binary,output,case_id,runs,work_limit=5000000):
    if not 2<=runs<=100:raise ValueError('Use between 2 and 100 independent processes')
    spec=json.loads((ROOT/'research/ui_incremental_oracle_v3.json').read_bytes())
    case=next(c for c in spec['cases'] if c['id']==case_id)
    fixture=ROOT/case['file'];dll=binary/'ia_lua533_ui_incremental.dll'
    if digest(fixture)!=case['sha256']:raise ValueError('Frozen fixture changed')
    output.mkdir(parents=True,exist_ok=False);rows=[];first=None
    for n in range(runs):
        report=invoke([binary/'authority-trace-research.exe','--evaluate',dll,digest(dll),fixture,'trace'],output/f'{n}.json',True)
        if first is None:first=report
        cost=report['trace']['bounded_work']
        row={'run':n,'whole_graph_equal':report['value_graph']==first['value_graph'],'whole_cache_evidence_equal':report['trace']['incremental']==first['trace']['incremental'],'origins_equal':report['origins']==first['origins'],'ordinary_result_equal':all(report.get(k)==first.get(k) for k in ['success','values','error']),'used':cost['used'],'cache_witness_checks':cache_witnesses(report['trace'])}
        rows.append(row)
        if not all(row[k] for k in ['whole_graph_equal','whole_cache_evidence_equal','origins_equal','ordinary_result_equal']) or cost['limit']!=work_limit or cost['used']>work_limit or cost['used']!=sum(cost['categories'].values()) or cost['failure']:
            write(output/'failure.json',{'case':case_id,'runtime_sha256':digest(dll),'runs':rows})
            raise ValueError('Stable evidence or unchanged budget check failed')
    result={'passed':True,'case':case_id,'source_sha256':case['sha256'],'runs':rows,'runtime_sha256':digest(dll),'work_limit':work_limit,'normalization_used':False,'game_process_used':False}
    write(output/'stress.json',result);print(json.dumps({'passed':True,'runs':runs,'case':case_id,'runtime_sha256':digest(dll)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',default='structure-resize');p.add_argument('--runs',type=int,default=20);p.add_argument('--work-limit',type=int,choices=[2000000,5000000],default=5000000);a=p.parse_args();run(a.binary.resolve(),a.output.resolve(),a.case,a.runs,a.work_limit)
