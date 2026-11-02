"""Run the frozen first refactoring gate with bounded, compressed full evidence."""
import argparse
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
DLL=ROOT/'build-ui-incremental2/Release/ia_lua533_ui_incremental2.dll'
EXE=DLL.with_name('authority-incremental2-research.exe')
BASE=ROOT/'build-ui-incremental-encoded-v3-release/Release'
MANIFEST=ROOT/'research/ui_incremental2_stage1_v7.json'
MAX_OUTPUT=64*1024*1024

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def write(path,value):
    with path.open('x',encoding='utf-8') as out:json.dump(value,out,ensure_ascii=False,indent=2)

def preservation():
    names=['incremental_ui_runtime','trace_runtime','bounded_ui_runtime','slice_runtime','slice2_runtime','slice3_runtime','slice3_ui_runtime','native','research/slice3_ui_inputs','third_party/lua533']
    records={}
    for name in names:
        for p in (ROOT/name).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:records[p.relative_to(ROOT).as_posix()]=digest(p)
    for folder in ['build-ui-incremental-encoded-v3-release/Release','build-ui-incremental-encoded/Release']:
        for p in (ROOT/folder).iterdir():
            if p.suffix.lower() in ('.exe','.dll','.lib'):records[p.relative_to(ROOT).as_posix()]=digest(p)
    records['CMakeLists.txt']=digest(ROOT/'CMakeLists.txt')
    return records

def invoke(case,label,dll,output,evidence):
    target=output/(case['id']+'-'+label+'.json.gz')
    command=[str(EXE),'--suite',str(dll),digest(dll),str(ROOT),str(MANIFEST),case['id'],'plain' if label=='reference' else 'trace']
    if evidence:command.append('--evidence')
    env=os.environ.copy();env.pop('IA_INCREMENTAL_VERIFY',None)
    if label!='reference' and case.get('verify_full_origins'):env['IA_INCREMENTAL_VERIFY']='1'
    if label=='origin-oracle':env.pop('IA_INCREMENTAL_VERIFY',None)
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    timed_out=[]
    def timeout():
        timed_out.append(True)
        if process.poll() is None:process.kill()
    timer=threading.Timer(90,timeout);timer.start();started=time.perf_counter();h=hashlib.sha256();size=0
    try:
        with target.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as packed:
            while block:=process.stdout.read(1024*1024):
                size+=len(block)
                if size>MAX_OUTPUT:
                    process.kill();raise RuntimeError('Diagnostic output exceeds frozen 64 MiB case limit')
                h.update(block);packed.write(block)
        stderr=process.stderr.read(65536).decode('utf-8',errors='replace');returncode=process.wait()
    finally:
        timer.cancel()
        if process.poll() is None:process.kill();process.wait()
    artifact={'file':target.name,'compressed_sha256':digest(target),'uncompressed_sha256':h.hexdigest(),'uncompressed_bytes':size,'elapsed_seconds':round(time.perf_counter()-started,6),'returncode':returncode,'stderr':stderr,'timeout':bool(timed_out)}
    # Verify the complete compressed evidence before reading observations.
    with gzip.open(target,'rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=h.hexdigest():raise RuntimeError('Compressed evidence failed verification')
    if returncode or timed_out:
        return {'process_failure':True,'error':stderr or 'process '+str(returncode)},artifact
    with gzip.open(target,'rt',encoding='utf-8') as stream:return json.load(stream),artifact

def ordinary(report):
    return [{k:p.get(k) for k in ['success','values','error']} for p in report.get('phases',[])]

def proof(report):
    # Layout, timings and fees are diagnostics, not portable producer identity.
    graph=report.get('value_graph',{})
    return {'phases':report.get('phases'),'graph':graph,'cache_evidence':report.get('trace',{}).get('incremental'),'ids_present':bool(graph.get('nodes'))}

def graph_sources(report):
    nodes=report.get('value_graph',{}).get('nodes',[])
    def sources(value):
        todo=[value];seen=set();labels=set()
        while todo:
            current=todo.pop()
            if not current or current in seen:continue
            if current<1 or current>len(nodes):raise ValueError('Dangling producer reference')
            seen.add(current);node=nodes[current-1]
            if node['id']!=current:raise ValueError('Producer identity changed')
            if node['operation']=='source':
                label=node['detail']['label']
                labels.update(json.loads(label))
            todo.extend(node['data']);todo.extend(node['control'])
        return sorted(labels)
    return [[sources(value) for value in phase.get('value_ids',[])] for phase in report.get('phases',[])]

def run(output,only=None):
    output.mkdir(parents=True,exist_ok=False);before=preservation();write(output/'preserved-before.json',before)
    from audit_baseline import audit
    saved=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-before.json',saved)
    spec=json.loads(MANIFEST.read_text(encoding='utf-8'));rows=[]
    cases=[c for c in spec['cases'] if not only or c['id'] in only]
    for case in cases:
        print('Incremental2 '+case['id'],flush=True)
        reference,ref_art=invoke(case,'reference',BASE/'ia_lua533_reference.dll',output,False)
        candidate,art=invoke(case,'candidate-1',DLL,output,True)
        second,art2=invoke(case,'candidate-2',DLL,output,True)
        observed=ordinary(candidate);expected=case.get('expected')
        same=not candidate.get('process_failure') and ordinary(reference)==observed
        if case.get('kind')=='safety':
            functional=None
            safety=not candidate.get('process_failure') and any(case['error_contains'] in p.get('error','') for p in candidate.get('phases',[]))
        elif case.get('kind')=='error':
            safety=None;functional=same and bool(observed) and not observed[-1]['success']
        else:
            safety=None;functional=same and all(p['success'] for p in observed)
            if expected is not None:functional=functional and [p['values'] for p in observed]==expected
            if 'origins' in case:functional=functional and [p['origins'] for p in candidate['phases']]==case['origins']
        budget=candidate.get('budget',{});budget_ok=budget.get('limit')==10000000 and budget.get('used',10000001)<=10000000 and budget.get('used')==sum(budget.get('categories',{}).values())
        if case.get('kind')!='safety':budget_ok=budget_ok and not budget.get('failure') and candidate.get('diagnostic_export_budget_ok',False)
        repeated=proof(candidate)==proof(second) and not second.get('process_failure')
        producer_sources=graph_sources(candidate) if not candidate.get('process_failure') else []
        graph_trace_equal=producer_sources==[p.get('origins',[]) for p in candidate.get('phases',[])]
        if functional is not None:functional=bool(functional and graph_trace_equal and not candidate.get('value_graph',{}).get('failure') and not candidate.get('trace',{}).get('failure'))
        if 'origins' in case:functional=bool(functional and producer_sources==case['origins'])
        row={'id':case['id'],'functional':functional,'safety':safety,'ordinary_equal_reference':same,'budget_valid':budget_ok,'producer_and_field_proofs_repeat_equal':repeated,'producer_sources':producer_sources,'artifacts':[ref_art,art,art2],'budget':budget,'graph_nodes':candidate.get('graph_nodes'),'private_commit_bytes':candidate.get('private_commit_bytes'),'origins':[p.get('origins') for p in candidate.get('phases',[])]}
        if case.get('require_all_field_writes_actual'):
            writes=[n for n in candidate.get('value_graph',{}).get('nodes',[]) if n['operation']=='field_write' and 'actual_write' in n['detail']]
            row['all_field_writes_actual']=bool(writes) and all(n['detail']['actual_write'] for n in writes)
            row['functional']=bool(row['functional'] and row['all_field_writes_actual'])
        if case['id']=='reparent':
            snapshots=[p['snapshots']['observed'] for p in candidate.get('phases',[]) if 'observed' in p.get('snapshots',{})]
            row['detached_child_does_not_invalidate_parent']=len(snapshots)==4 and snapshots[3]['version']==snapshots[2]['version']
            row['remaining_alias_still_invalidates_parent']=len(snapshots)==4 and snapshots[1]['version']>snapshots[0]['version']
            row['functional']=bool(row['functional'] and row['detached_child_does_not_invalidate_parent'] and row['remaining_alias_still_invalidates_parent'])
        if case['id'].startswith('read-') and candidate.get('phases'):
            ps=candidate['phases'];row['read_preserves_version']=len(ps)==2 and ps[0]['snapshots']['observed']['version']==ps[1]['snapshots']['observed']['version'];row['functional']=bool(row['functional'] and row['read_preserves_version'])
        if case['id']=='layout-migration':
            ps=candidate.get('phases',[]);snap=[p['snapshots']['observed'] for p in ps if 'observed' in p.get('snapshots',{})]
            row['layout_changed_without_rewriting_retained_field']=len(snap)==2 and snap[1]['layout_version']>snap[0]['layout_version'] and snap[1]['fields']['integer:8']==snap[0]['fields']['integer:8'] and snap[1]['structure_version']==snap[0]['structure_version']+1
            row['functional']=bool(row['functional'] and row['layout_changed_without_rewriting_retained_field'])
        if case.get('baseline'):
            old,old_art=invoke(case,'baseline',BASE/'ia_lua533_ui_incremental.dll',output,False)
            row['baseline']={'ordinary_equal_reference':ordinary(old)==ordinary(reference),'budget':old.get('budget'),'artifacts':old_art,'private_commit_bytes':old.get('private_commit_bytes'),'process_failure':old.get('process_failure',False),'error':old.get('error')}
            if case.get('compare_baseline_origins'):
                row['origins_equal_historical_runtime']=[p.get('origins') for p in old.get('phases',[])]==row['origins']
                row['functional']=bool(row['functional'] and row['origins_equal_historical_runtime'])
        if case.get('origin_oracle'):
            full,full_art=invoke(case,'origin-oracle',DLL.with_name('ia_lua533_ui_incremental2_oracle.dll'),output,False)
            equal=bool(full.get('full_traversal_oracle')) and ordinary(full)==ordinary(candidate) and [p.get('origins') for p in full.get('phases',[])]==row['origins']
            row['uncached_origin_oracle_equal']=equal;row['origin_oracle_artifact']=full_art
            if row['functional'] is not None:row['functional']=bool(row['functional'] and equal)
        rows.append(row);write(output/(case['id']+'-result.json'),row)
        print(json.dumps({k:row[k] for k in ['id','functional','safety','budget_valid','producer_and_field_proofs_repeat_equal','graph_nodes','private_commit_bytes']}),flush=True)
        del reference,candidate,second;gc.collect()
    growth=[]
    for name in ['append','overwrite','read']:
        selected=[next((r for r in rows if r['id']==name+'-'+str(n)),None) for n in [256,512,1024]]
        if not all(selected):continue
        units=[r['budget']['used'] for r in selected];memory=[r['private_commit_bytes'] for r in selected]
        ratios=[round(units[i+1]/units[i],6) for i in [0,1]]
        work_delta_ratio=(units[2]-units[1])/(units[1]-units[0]);memory_delta_ratio=(memory[2]-memory[1])/max(1,memory[1]-memory[0])
        growth.append({'case':name,'n':[256,512,1024],'charged_work':units,'private_commit_bytes':memory,'work_ratios':ratios,'work_increment_ratio':work_delta_ratio,'memory_increment_ratio':memory_delta_ratio,'linear_work_gate':all(v<=2.5 for v in ratios) and work_delta_ratio<=2.5 and memory_delta_ratio<=2.5})
    after=preservation();unchanged=before==after;write(output/'preserved-after.json',after)
    saves_after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');write(output/'save-after.json',saves_after)
    saves_unchanged=saved['files']==saves_after['files']
    result={'stage':'native-field-effects','cases':rows,'growth':growth,'preserved_sources_and_binaries_unchanged':unchanged,'save_files_unchanged':saves_unchanged,'manifest_sha256':digest(MANIFEST),'runtime_sha256':digest(DLL),'runner_sha256':digest(EXE),'game_started':False,'real_mcm_eid_initialization_run':False,'compact_graph_complete':False,'runtime_audit_stream_complete':False,'graph_gc_complete':False,'entire_refactor_passed':False}
    result['preflight_passed']=all((r['functional'] if r['functional'] is not None else r['safety']) and r['budget_valid'] and r['producer_and_field_proofs_repeat_equal'] for r in rows) and all(g['linear_work_gate'] for g in growth) and unchanged and saves_unchanged
    result['complete_manifest_run']=len(rows)==len(spec['cases'])
    result['stage_gate_passed']=result['preflight_passed'] and result['complete_manifest_run'] and len(growth)==3
    write(output/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['cases','growth']},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--case',action='append');parser.add_argument('--manifest',type=Path);args=parser.parse_args()
    if args.manifest:MANIFEST=args.manifest.resolve()
    run(args.output.resolve(),args.case)
