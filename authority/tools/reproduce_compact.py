"""Verify two pinned archives, replay all cases, retain results outside extraction."""
import argparse,gc,gzip,hashlib,json,os,sys,zipfile
from pathlib import Path
sys.dont_write_bytecode=True
import run_incremental2 as common
from run_compact_storage import semantic
from read_compact_audit import read

def normalized(report):
    phases=[{k:v for k,v in phase.items() if k not in ['storage_checkpoint','trace_checkpoint','private_commit_checkpoint']} for phase in report.get('phases',[])]
    return {'phases':phases,'graph':report.get('value_graph'),
            'incremental':report.get('trace',{}).get('incremental')}

def unpack(base,delta,workspace,output):
    with zipfile.ZipFile(delta) as archive:manifest=json.loads(archive.read('compact-bundle-manifest.json'))
    if common.digest(base)!=manifest['base_sha256']:raise ValueError('Base archive hash mismatch')
    expected_delta=delta.with_suffix('.zip.sha256').read_text(encoding='ascii').split()[0]
    if common.digest(delta)!=expected_delta:raise ValueError('Delta archive hash mismatch')
    workspace=workspace.resolve();output=output.resolve()
    if workspace.exists() or output.is_relative_to(workspace):raise ValueError('Fresh extraction and external results required')
    output.mkdir(parents=True,exist_ok=False);workspace.mkdir(parents=True,exist_ok=False);extracted={}
    for path,manifest_name in [(base,'bundle-manifest.json'),(delta,'compact-bundle-manifest.json')]:
        with zipfile.ZipFile(path) as archive:
            inventory=json.loads(archive.read(manifest_name));allowed={e['path']:e for e in inventory['files']}
            if set(archive.namelist())!=set(allowed)|{manifest_name}:raise ValueError('Archive inventory mismatch')
            for name in archive.namelist():
                destination=(workspace/name).resolve()
                if not destination.is_relative_to(workspace):raise ValueError('Archive member escapes extraction')
                destination.parent.mkdir(parents=True,exist_ok=True)
                data=archive.read(name);sha=hashlib.sha256(data).hexdigest()
                if name in allowed and (len(data)!=allowed[name]['bytes'] or sha!=allowed[name]['sha256']):raise ValueError('Archive member changed')
                destination.write_bytes(data);extracted[name]={'path':name,'sha256':sha,'bytes':len(data)}
    common.write(output/'extraction-cleanup-plan.json',{'root':str(workspace),'files':list(extracted.values()),'base_sha256':common.digest(base),'delta_sha256':common.digest(delta)})
    return manifest

def reproduce(base,delta,workspace,output):
    manifest=unpack(base,delta,workspace,output);root=workspace/'authority';common.ROOT=root
    common.EXE=root/'build-ui-incremental2/compact/Release/authority-compact-research.exe';dll=common.EXE.with_name('ia_lua533_ui_compact.dll');rows=[]
    for group in manifest['groups']:
        common.MANIFEST=root/group['manifest'];suite=json.loads(common.MANIFEST.read_text(encoding='utf-8'))
        for case in suite['cases']:
            folder=output/case['id'];folder.mkdir();reports=[];artifacts=[]
            for repeat in (1,2):
                os.environ['IA_COMPACT_AUDIT_FILE']=str(folder/('replay-'+str(repeat)+'.audit'))
                report,artifact=common.invoke(case,'replay-'+str(repeat),dll,folder,case.get('evidence',True));reports.append(report);artifacts.append(artifact)
            if group['kind']=='regression':expected_path=workspace/group['expected']/(case['id']+'-candidate-1.json.gz')
            else:expected_path=workspace/group['expected']/(case['id']+'-storage-1.json.gz')
            injected=group['kind']=='storage' and bool(case.get('error_contains'))
            expected=None
            if not injected:
                with gzip.open(expected_path,'rt',encoding='utf-8') as stream:expected=json.load(stream)
            if injected:
                passed=all(r.get('process_failure') and case['error_contains'] in a.get('stderr','') for r,a in zip(reports,artifacts))
            else:
                def bounded(r):
                    b=r.get('budget',{})
                    return b.get('limit')==10000000 and b.get('used',10000001)<=10000000 and b.get('used')==sum(b.get('categories',{}).values()) and (case['kind']=='safety' or not b.get('failure'))
                passed=all(not r.get('process_failure') and normalized(r)==normalized(expected) and bounded(r) for r in reports)
                if passed:
                    decoded=read(folder/'replay-1.audit')
                    if case.get('evidence',True):
                        graph=reports[0]['value_graph'];incremental=reports[0].get('trace',{}).get('incremental',{})
                        passed=all(decoded[k]==graph[k] for k in ['nodes','consumption_records','storage_versions','static_regions','code','purpose_records']) and decoded['root']=={k:v for k,v in graph.items() if k not in ['nodes','consumption_records','storage_versions','static_regions','code','purpose_records']}
                        if group['kind']=='regression':passed=passed and all(decoded[k]==incremental[k] for k in ['cache_descriptors','cache_sites','cache_uses'])
            one=folder/'replay-1.audit';two=folder/'replay-2.audit';same=common.digest(one)==common.digest(two)
            if same:two.unlink()
            row={'id':case['id'],'passed':bool(passed and same),'audit_repeat_equal':same,'duplicate_removed':same,'artifacts':artifacts}
            common.write(folder/'result.json',row);rows.append(row);print(json.dumps({k:row[k] for k in ['id','passed','audit_repeat_equal']}),flush=True)
            del reports,expected;gc.collect()
    result={'cases':rows,'passed':len(rows)==manifest['cases'] and all(r['passed'] for r in rows),'case_count':len(rows),
            'base_sha256':common.digest(base),'delta_sha256':common.digest(delta),'game_started':False,'save_accessed':False,'work_limit':10000000}
    common.write(output/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['base','delta','workspace','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=reproduce(*[getattr(a,n).resolve() for n in ['base','delta','workspace','output']]);sys.exit(0 if result['passed'] else 1)
