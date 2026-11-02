"""Frozen storage, liveness, dual-view and fault gates; never starts the game."""
import argparse,gc,gzip,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_incremental2 as common
from read_compact_audit import read
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'research/ui_compact_storage_v3.json'

def semantic(report):
    return [{k:p.get(k) for k in ['success','values','error','origins','value_ids','view_bindings','views','reclamation']} for p in report.get('phases',[])]

def run(output,only=None):
    output.mkdir(parents=True,exist_ok=False);common.EXE=ROOT/'build-ui-incremental2/compact/Release/authority-compact-research.exe';common.MANIFEST=MANIFEST
    dll=common.EXE.with_name('ia_lua533_ui_compact.dll');rows=[]
    from audit_baseline import audit
    saved=audit(ROOT.parent/'artifacts/authority-baseline-20261009')
    common.write(output/'save-before.json',saved)
    for case in json.loads(MANIFEST.read_text(encoding='utf-8'))['cases']:
        if only and case['id'] not in only:continue
        print('Storage '+case['id'],flush=True);reports=[];artifacts=[];audits=[]
        for repeat in (1,2):
            path=output/(case['id']+'-'+str(repeat)+'.audit');os.environ['IA_COMPACT_AUDIT_FILE']=str(path)
            report,artifact=common.invoke(case,'storage-'+str(repeat),dll,output,case.get('evidence',True))
            reports.append(report);artifacts.append(artifact)
            audits.append({'file':path.name,'sha256':common.digest(path),'bytes':path.stat().st_size})
        first,second=reports;phases=first.get('phases',[])
        repeated=semantic(first)==semantic(second) and artifacts[0]['returncode']==artifacts[1]['returncode'] and artifacts[0]['stderr']==artifacts[1]['stderr']
        row={'id':case['id'],'kind':case['kind'],'repeat_equal':repeated,'artifacts':artifacts,'audits':audits,'process_failure':first.get('process_failure',False)}
        if case.get('error_contains'):
            row['safety_refusal']=all(r.get('process_failure') and case['error_contains'] in a.get('stderr','') for r,a in zip(reports,artifacts));row['passed']=repeated and row['safety_refusal']
            if case['id']=='fault-corruption':
                try:read(output/audits[0]['file']);row['offline_corruption_rejected']=False
                except ValueError:row['offline_corruption_rejected']=True
                row['passed']=row['passed'] and row['offline_corruption_rejected']
        else:
            os.environ.pop('IA_COMPACT_AUDIT_FILE',None)
            reference,ref_art=common.invoke(case,'reference',ROOT/'build-ui-incremental-encoded-v3-release/Release/ia_lua533_reference.dll',output,False)
            row['reference_artifact']=ref_art
            row['ordinary_equal_reference']=common.ordinary(first)==common.ordinary(reference)
            budget=first.get('budget',{});row['budget']=budget;row['budget_valid']=budget.get('limit')==10000000 and not budget.get('failure') and budget.get('used',10000001)<=10000000 and budget.get('used')==sum(budget.get('categories',{}).values())
            row['passed']=repeated and not first.get('process_failure') and row['ordinary_equal_reference'] and row['budget_valid'] and len(phases)==len(case['chunks'])
            decoded=read(output/audits[0]['file']);row['decoded_nodes']=len(decoded['nodes'])
            if case.get('evidence',True):
                graph=first.get('value_graph',{});row['audit_nodes_equal_export']=decoded['nodes']==graph.get('nodes');row['passed']=row['passed'] and row['audit_nodes_equal_export']
            if case['id'].startswith('churn-'):
                row['observed']=[p['values'] for p in phases]
                row['private_commit_checkpoints']=[p['private_commit_checkpoint'] for p in phases]
                row['live_object_checkpoints']=[p['trace_checkpoint']['objects'] for p in phases]
                row['passed']=row['passed'] and all(v==case['expected_repeated'] for v in row['observed'])
                if case['reclaim']:
                    tail=row['private_commit_checkpoints'][-8:];objects=row['live_object_checkpoints'][-8:]
                    row['steady_tail_gate']=max(tail)-min(tail)<=4*1024*1024 and max(objects)-min(objects)<=2
                    row['passed']=row['passed'] and row['steady_tail_gate']
            if case['id'].startswith('dual-config-'):
                personal=case['personal'];authority=case['authority'];text=lambda x:{'text_hex':x.encode().hex()}
                row['personal_values_preserved']=all(p['values']==[personal,137,text('en'),text('amount='+str(personal))] for p in phases)
                row['authority_hud_values_preserved']=all([v.get('value') for v in p.get('views',[])]==[authority,137,'en','amount='+str(authority)] and all(v.get('ok') for v in p['views']) for p in phases)
                row['passed']=row['passed'] and row['personal_values_preserved'] and row['authority_hud_values_preserved']
            if case['id']=='host-pin-keep':
                row['host_pin_keeps_authority']=bool(phases) and phases[-1].get('views',[{}])[0].get('value')==1 and phases[-1]['views'][0].get('ok',False)
                row['passed']=row['passed'] and row['host_pin_keeps_authority']
            if case['id']=='host-pin-missing':
                result=phases[-1].get('views',[{}])[0] if phases else {};row['safety_refusal']=result.get('ok') is False and 'live host pin' in result.get('error','');row['passed']=row['passed'] and row['safety_refusal']
            if case['id']=='ambiguous-world-reference':
                bindings=phases[0].get('view_bindings',[]) if phases else [];row['safety_refusal']=len(bindings)==2 and bindings[0].get('ok') and bindings[1].get('ok') is False and 'Ambiguous' in bindings[1].get('error','')
                row['passed']=row['passed'] and row['safety_refusal'] and phases[0].get('views',[{}])[0].get('value')==1
            row['compact_storage']=first.get('compact_storage')
            del reference
        if audits[0]['sha256']==audits[1]['sha256']:
            duplicate=output/audits[1]['file']
            if not duplicate.resolve().is_relative_to(output.resolve()):raise ValueError('Duplicate escapes output')
            duplicate.unlink();row['duplicate_audit_removed']=True
        common.write(output/(case['id']+'-result.json'),row);rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k in ['id','passed','process_failure','steady_tail_gate','personal_values_preserved','authority_hud_values_preserved','safety_refusal']}),flush=True)
        del reports,first,second;gc.collect()
    after=audit(ROOT.parent/'artifacts/authority-baseline-20261009');common.write(output/'save-after.json',after)
    result={'cases':rows,'passed':bool(rows) and all(r['passed'] for r in rows) and saved['files']==after['files'],'saves_unchanged':saved['files']==after['files'],'complete_13_case_gate':len(rows)==13,'manifest_sha256':common.digest(MANIFEST),'runtime_sha256':common.digest(dll),'runner_sha256':common.digest(common.EXE),'work_limit':10000000,'game_started':False}
    common.write(output/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');a=p.parse_args();result=run(a.output.resolve(),a.case);sys.exit(0 if result['passed'] else 1)
