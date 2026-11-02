"""Frozen UI uservalue roots, reference Lua, view preservation and audit gate."""
import argparse,gc,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_incremental2 as common
from read_compact_audit import read
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'research/ui_userdata_roots_v7.json'

def semantic(report):
    return [{k:v for k,v in p.items() if k not in ['storage_checkpoint','private_commit_checkpoint','trace_checkpoint']} for p in report.get('phases',[])]

def run(output,only=None):
    output.mkdir(parents=True,exist_ok=False);common.MANIFEST=MANIFEST;common.EXE=ROOT/'build-ui-incremental2/compact/Release/authority-compact-research.exe'
    dll=common.EXE.with_name('ia_lua533_ui_compact.dll');reference=ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_reference.dll';rows=[]
    for case in json.loads(MANIFEST.read_text(encoding='utf-8'))['cases']:
        if only and case['id'] not in only:continue
        print('Root gate '+case['id'],flush=True);reports=[];artifacts=[]
        for repeat in (1,2):
            os.environ['IA_COMPACT_AUDIT_FILE']=str(output/(case['id']+'-'+str(repeat)+'.audit'))
            r,a=common.invoke(case,'candidate-'+str(repeat),dll,output,case.get('evidence',True));reports.append(r);artifacts.append(a)
        os.environ.pop('IA_COMPACT_AUDIT_FILE',None)
        ref,ref_art=common.invoke(case,'reference',reference,output,False)
        first,second=reports;phases=first.get('phases',[]);budget=first.get('budget',{})
        repeated=not any(r.get('process_failure') for r in reports) and semantic(first)==semantic(second) and first.get('value_graph')==second.get('value_graph')
        ordinary=common.ordinary(first)==common.ordinary(ref)
        bounded=budget.get('limit')==10000000 and budget.get('used',10000001)<=10000000 and budget.get('used')==sum(budget.get('categories',{}).values()) and not budget.get('failure')
        row={'id':case['id'],'kind':case['kind'],'repeat_equal':repeated,'ordinary_equal_reference':ordinary,'budget':budget,'budget_valid':bounded,'artifacts':artifacts,'reference_artifact':ref_art}
        passed=repeated and ordinary and bounded and len(phases)==len(case['chunks'])
        if case.get('expected_error'):
            if 'expected_reference' in case:
                row['reference_result_expected']=bool(ref.get('phases')) and ref['phases'][-1].get('success') and ref['phases'][-1].get('values')==case['expected_reference']
                passed=repeated and bounded and len(phases)==len(case['chunks']) and row['reference_result_expected']
            row['expected_refusal']=bool(phases) and not phases[-1]['success'] and case['expected_error'] in phases[-1].get('error','');passed=passed and row['expected_refusal']
        else:
            passed=passed and all(p['success'] for p in phases)
            expected=case.get('expected_phases',[case.get('expected') for _ in case['chunks']])
            row['expected_values']=[p['values'] for p in phases]==expected;passed=passed and row['expected_values']
            if case['id']=='userdata-seven-classes':
                row['field_sources_preserved']=bool(phases) and phases[0]['origins']==[['personal_config:amount'],[]];passed=passed and row['field_sources_preserved']
            if case['id']=='userdata-cycle-churn':
                counts=[p['reclamation']['registered_userdata'] for p in phases];row['live_userdata']=counts;row['freed_userdata']=[p['reclamation']['userdata_freed'] for p in phases];row['private_commit']=[p['private_commit_checkpoint'] for p in phases]
                row['dead_cycles_reclaimed']=max(counts[-8:])-min(counts[-8:])<=2 and max(counts[-8:])<=3 and row['freed_userdata'][-1]>=300;passed=passed and row['dead_cycles_reclaimed']
            if case['id'].startswith('userdata-config-'):
                authority=case['authority'];row['authority_views_preserved']=all([v.get('value') for v in p.get('views',[])]==[authority,137,'en','amount='+str(authority)] and all(v.get('ok') for v in p.get('views',[])) for p in phases);passed=passed and row['authority_views_preserved']
            if case['id'].startswith('userdata-drop-'):
                view=phases[-1].get('views',[{}])[0] if phases else {}
                keep=case['pin_prior_frames'];row['view_lifetime_correct']=(view.get('ok') is True and view.get('value')==1) if keep else (view.get('ok') is False and 'live host pin' in view.get('error',''))
                row['dead_userdata_not_pinned']=len(phases)==3 and all(p.get('reclamation',{}).get('registered_userdata')==0 for p in phases[1:])
                passed=passed and row['view_lifetime_correct'] and row['dead_userdata_not_pinned']
        one=output/(case['id']+'-1.audit');two=output/(case['id']+'-2.audit');equal=common.digest(one)==common.digest(two)
        row['audit_sha256']=common.digest(one);row['audit_repeat_equal']=equal;row['audit_bytes']=one.stat().st_size
        if not first.get('process_failure'):
            decoded=read(one)
            if case.get('evidence',True):row['audit_nodes_equal']=decoded['nodes']==first['value_graph']['nodes'];passed=passed and row['audit_nodes_equal']
        if equal:two.unlink();row['duplicate_removed']=True
        row['passed']=bool(passed and equal);common.write(output/(case['id']+'-result.json'),row);rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k in ['id','passed','ordinary_equal_reference','repeat_equal','field_sources_preserved','authority_views_preserved','dead_cycles_reclaimed','expected_refusal']}),flush=True)
        del reports,first,second,ref;gc.collect()
    result={'passed':bool(rows) and all(r['passed'] for r in rows),'cases':rows,'runtime_sha256':common.digest(dll),'runner_sha256':common.digest(common.EXE),'manifest_sha256':common.digest(MANIFEST),'work_limit':10000000,'game_started':False}
    common.write(output/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');a=p.parse_args();r=run(a.output.resolve(),a.case);sys.exit(0 if r['passed'] else 1)
