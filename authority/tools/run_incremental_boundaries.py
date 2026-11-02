"""Exercise cached leaf depth/walk limits through protected C API calls."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from run_incremental_ui import ROOT,digest,invoke,write,cache_witnesses,EvidenceEvents

def run(binary,output,work_limit=5000000,manifest=None):
    output.mkdir(parents=True,exist_ok=False)
    manifest=manifest or ROOT/'research/ui_incremental_boundaries_v2.json'
    spec=json.loads(manifest.read_bytes());rows=[]
    if spec['work_limit']!=work_limit:raise ValueError('Frozen boundary profile differs from requested work limit')
    runtimes={'reference':(binary/'ia_lua533_reference.dll','plain'),'full':(binary/'ia_lua533_trace.dll','trace'),'candidate':(binary/'ia_lua533_ui_incremental.dll','trace')}
    for case in spec['cases']:
        reports={}
        for name,(dll,mode) in runtimes.items():
            r=invoke([binary/'authority-incremental-boundary-tests.exe',dll,digest(dll),mode,case['id']],output/(case['id']+'-'+name+'.json'))
            if r['source_sha256']!=case['source_sha256']:raise ValueError('Boundary program changed')
            reports[name]=r
        plain,full,candidate=[reports[n] for n in ['reference','full','candidate']]
        b=candidate['trace']['bounded_work'];inc=candidate['trace']['incremental']
        leaf_proofs=[e for e in EvidenceEvents(inc) if e['operation']=='complete_scalar_leaf_mark']
        replay=invoke([binary/'authority-incremental-boundary-tests.exe',binary/'ia_lua533_ui_incremental.dll',digest(binary/'ia_lua533_ui_incremental.dll'),'trace',case['id']],output/(case['id']+'-candidate-repeat.json'))
        same=candidate['success']==replay['success'] and candidate.get('error')==replay.get('error') and inc==replay['trace']['incremental']
        passed=plain['success'] and plain['value']==1 and not full['success'] and not candidate['success'] and case['expected_refusal'] in full.get('error','') and case['expected_refusal'] in candidate.get('error','') and bool(leaf_proofs) and same and b['limit']==work_limit and b['used']<=work_limit and b['used']==sum(b['categories'].values())
        rows.append({'case':case['id'],'passed':passed,'reference_value':plain.get('value'),'full_refusal':full.get('error'),'candidate_refusal':candidate.get('error'),'complete_leaf_proofs':len(leaf_proofs),'leaf_cache_hits_before_refusal':inc['scalar_leaf_mark_cache_hits'],'cache_witnesses':cache_witnesses(candidate['trace']),'complete_cache_evidence_repeat_equal':same,'work_used':b['used'],'source_sha256':case['source_sha256']})
    result={'passed':all(c['passed'] for c in rows),'cases':rows,'runtime_sha256':digest(binary/'ia_lua533_ui_incremental.dll'),'manifest_sha256':digest(manifest),'work_limit':work_limit,'oracle_enabled':False,'same_logical_limits_as_full_runtime':True,'game_process_used':False}
    write(output/'boundaries.json',result);print(json.dumps(result),flush=True)
    if not result['passed']:raise ValueError('Cached leaf structural budget gate failed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--work-limit',type=int,choices=[2000000,5000000,10000000],default=5000000);p.add_argument('--manifest',type=Path);a=p.parse_args();run(a.binary.resolve(),a.output.resolve(),a.work_limit,a.manifest.resolve() if a.manifest else None)
