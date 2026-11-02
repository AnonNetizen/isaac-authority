"""Package or safely extract/reproduce bounded tracking research, without game assets."""
import sys
sys.dont_write_bytecode=True
import argparse, json, subprocess, zipfile
from pathlib import Path, PurePosixPath
from run_bounded_ui import ROOT,digest,write,sources,outcome
from run_slice3_ui_research import verify_inputs
from run_trace_research import verify_pristine
from validate import source_files
PREFIX='isaac-authority-ui-bounded-0.1.0'
def package(binary,evidence,output):
    validation=json.loads((evidence/'validation.json').read_text());baseline=json.loads((evidence/'before.json').read_text())
    if sources()!=baseline['sources']:raise ValueError('Research source changed since verification')
    for n,sha in validation['binaries'].items():
        if digest(binary/n)!=sha:raise ValueError('Binary changed: '+n)
    verify_pristine();verify_inputs(ROOT);files={}
    for p in source_files():files['source/'+p.relative_to(ROOT).as_posix()]=p
    for name in ['bounded_ui_runtime','slice3_ui_runtime']:
        for p in (ROOT/name).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files['source/'+p.relative_to(ROOT).as_posix()]=p
    for n in baseline['sources']:files['source/'+n]=ROOT/n
    for n in validation['binaries']:files['bin/'+n]=binary/n
    for p in evidence.iterdir():
        if p.is_file():files['reports/current/'+p.name]=p
    # Preserve the prior validation and exact hashes, not another giant archive.
    for n in ['reports/ui-bounded-final/validation.json','reports/ui-bounded-final/before.json','reports/ui-bounded-final/after.json','reports/ui-bounded-final/regression.json','reports/slice3-ui-delivery.json']:
        files['history/'+Path(n).name if not n.endswith('slice3-ui-delivery.json') else 'history/slice3-ui-delivery.json']=ROOT/n
    files['README.md']=ROOT/'docs/BOUNDED_UI.md'
    for n in files:
        if Path(n).suffix.lower() in ('.png','.fnt','.anm2','.jpg','.dds','.ttf') and n!='source/third_party/lua533/doc/osi-certified-72x60.png':raise ValueError('Game resource bytes refused')
    entries=[{'path':n,'bytes':p.stat().st_size,'sha256':digest(p)} for n,p in sorted(files.items())]
    index={'schema':'isaac-ui-bounded-bundle-1','abi':validation['abi'],'files':entries,'ordinary_outcomes_repeated':True,'full_evidence_repeat_identically':validation['full_evidence_repeat_identically'],'initialization_contract_gate_passed':validation['initialization_contract_gate_passed'],'game_resources_distributed':False,'playable':False,'game_process_used':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):z.write(p,PREFIX+'/'+name)
        z.writestr(PREFIX+'/bundle-manifest.json',json.dumps(index,indent=2))
    with output.with_suffix('.zip.sha256').open('x',encoding='ascii') as f:f.write(digest(output)+'  '+output.name+'\n')
    return {'archive':str(output),'sha256':digest(output),'files':len(entries),'bytes':output.stat().st_size}
def verify(bundle):
    index=json.loads((bundle/'bundle-manifest.json').read_text());names={'bundle-manifest.json'}
    for record in index['files']:
        p=(bundle/record['path']).resolve();names.add(record['path'])
        if not p.is_relative_to(bundle) or p.stat().st_size!=record['bytes'] or digest(p)!=record['sha256']:raise ValueError('Bundle file mismatch: '+record['path'])
    if {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}!=names:raise ValueError('Bundle has extra/missing files')
    return len(names)-1
def reproduce(archive,extracted,output,game=None):
    if digest(archive)!=archive.with_suffix('.zip.sha256').read_text().split()[0]:raise ValueError('ZIP digest mismatch')
    extracted.mkdir(parents=True,exist_ok=False);output.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            p=PurePosixPath(entry.filename);target=(extracted/Path(*p.parts)).resolve()
            if p.is_absolute() or not target.is_relative_to(extracted) or p.parts[0]!=PREFIX or ((entry.external_attr>>16)&0xF000)==0xA000:raise ValueError('Unsafe archive path')
        z.extractall(extracted)
    bundle=extracted/PREFIX;count=verify(bundle);source=bundle/'source';binary=bundle/'bin'
    inputs=verify_inputs(source,game);reports={};definitions=json.loads((source/'research/ui_bounded_suite_v4.json').read_text())
    for label,reference in [('reference',True),('candidate',False)]:
        print('Extracted '+label,flush=True);dll=binary/('ia_lua533_reference.dll' if reference else 'ia_lua533_ui_bounded.dll')
        with (output/(label+'.json')).open('xb') as f,(output/(label+'.stderr.txt')).open('xb') as err:
            p=subprocess.run([str(binary/'authority-ui-bounded-research.exe'),'--suite-reference' if reference else '--suite',str(dll),digest(dll),str(source/'research/slice3_ui_inputs'),str(source),str(source/'research/ui_bounded_suite_v4.json')],stdout=f,stderr=err,timeout=300)
        if p.returncode:raise ValueError('Extracted process failed')
        actual=json.loads((output/(label+'.json')).read_bytes());prior=json.loads((bundle/'reports/current'/(label+'-1.json')).read_bytes())
        if outcome(actual)!=outcome(prior):raise ValueError('Relocated functional outcomes changed')
        if not reference:
            if not actual['safety_diagnostics_passed']:raise ValueError('Relocated rejection gate failed')
            for c in actual['cases']:
                w=c['execution_dependencies']['runtime']['bounded_work']
                if w['used']>2000000:raise ValueError('Relocated budget escaped')
        reports[label]={'cases':len(actual['cases']),'functional_outcomes_equal':True,'full_evidence_claimed_equal':False,'initialization_contract_gate_passed':actual['initialization_contract_gate_passed']}
        del prior,actual
    p=subprocess.run([str(binary/'authority-bounded-cfg-tests.exe')],capture_output=True,timeout=30)
    if p.returncode or not json.loads(p.stdout)['passed']:raise ValueError('Extracted CFG test failed')
    if verify(bundle)!=count:raise ValueError('Extracted bundle changed during reproduction')
    result={'schema':'isaac-ui-bounded-reproduction-1','archive_sha256':digest(archive),'files_verified_before_and_after':count,'inputs':inputs,'reports':reports,'cfg_tests':json.loads(p.stdout),'full_proof_equality_unverified':True,'game_process_used':False,'playable':False}
    write(output/'reproduction.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('package')
    for n in ('binary','evidence','output'):b.add_argument('--'+n,type=Path,required=True)
    r=sub.add_parser('reproduce')
    for n in ('archive','extracted','output'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--game',type=Path);a=p.parse_args()
    result=package(a.binary.resolve(),a.evidence.resolve(),a.output.resolve()) if a.command=='package' else reproduce(a.archive.resolve(),a.extracted.resolve(),a.output.resolve(),a.game.resolve() if a.game else None)
    print(json.dumps(result,indent=2))
