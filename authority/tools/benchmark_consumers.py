"""Small CLI performance samples; never launches real mod initialization."""
import argparse,copy,hashlib,json,os,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_consumers as bench
gate=bench.gate
def run(out):
    out.mkdir(parents=True,exist_ok=False);gate.RUN_DEADLINE=time.perf_counter()+20;gate.AUDIT_WRITTEN_BYTES=0
    initial=os.environ.pop('IA_CONSUMER_VERIFY',None);rows=[]
    try:
        for manifest,name in [('ui_consumers_v1.json','consumer-field-upvalue-scope'),('ui_consumer_performance_v1.json','consumer-repeated-expression')]:
            gate.MANIFEST=gate.ROOT/'research'/manifest;spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'));case=next(c for c in spec['cases'] if c['id']==name)
            for sample in range(2):
                reports={};row={'id':name,'sample':sample+1,'manifest_sha256':gate.digest(gate.MANIFEST)}
                for label,dll in [('baseline',gate.OLD),('candidate-1',gate.DLL)]:
                    report,artifact,journal=bench.old_invoke(case,label,dll,out,5)
                    if report.get('process_failure'):raise RuntimeError(report['error'])
                    reports[label]=report;decoded=bench.old_decode(journal);graph=report['value_graph'];incremental=report['trace']['incremental']
                    for key in ['nodes','consumption_records','storage_versions','static_regions','code','purpose_records']:
                        if decoded[key]!=graph[key]:raise RuntimeError('Benchmark graph audit differs')
                    for key in ['cache_descriptors','cache_sites','cache_uses']:
                        if decoded[key]!=incremental[key]:raise RuntimeError('Benchmark incremental audit differs')
                    if 'consumer_readsets' in report:
                        if decoded['consumer_records']!=report['consumer_readsets']['records']:raise RuntimeError('Benchmark consumer audit differs')
                        bench.verify_records(decoded['consumer_records'])
                    functional=[p['values'] for p in report['phases']]==case['expected']
                    for definition,phase in zip(case['chunks'],report['phases']):
                        for step,observed in zip(definition.get('consumer_steps',[]),phase.get('consumer_steps',[])):
                            if 'expected_view' in step:functional=functional and observed['result'].get('ok') is True and observed['result'].get('value')==step['expected_view']
                    budget=report['budget'];functional=functional and budget['limit']==10000000 and budget['used']==sum(budget['categories'].values()) and budget['used']<=10000000
                    row[label]={'seconds':artifact['seconds'],'budget':budget,'consumers':report.get('execution_before_diagnostics',{}).get('consumers'),'audit_bytes':journal.stat().st_size,'audit_sha256':gate.digest(journal),'expected_outputs':functional,'proof_sha256':hashlib.sha256(json.dumps(gate.canonical(copy.deepcopy(report)),sort_keys=True).encode()).hexdigest()}
                    if journal.parent.resolve()!=out.resolve():raise RuntimeError('Unexpected temporary audit path')
                    journal.unlink()
                row['semantic_proof_equal']=bench.baseline_equal(reports['candidate-1'],reports['baseline']);rows.append(row)
    finally:
        if initial is not None:os.environ['IA_CONSUMER_VERIFY']=initial
    result={'schema':'bounded-consumer-performance-2','samples':rows,'consumer_oracle_enabled':False,'full_origin_oracle_enabled':True,'work_limit':10000000,'case_timeout_seconds':5,'batch_timeout_seconds':20,'dll_sha256':gate.digest(gate.DLL),'passed':all(r['semantic_proof_equal'] and r['baseline']['expected_outputs'] and r['candidate-1']['expected_outputs'] for r in rows),'timings_are_small_samples':True,'real_mod_initialization':False}
    gate.save(out/'result.json',result);print(json.dumps({'passed':result['passed'],'samples':len(rows)}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();sys.exit(0 if run(a.output.resolve())['passed'] else 1)
