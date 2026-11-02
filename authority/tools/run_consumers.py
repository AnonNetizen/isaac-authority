"""Bounded consumer read-set gate, with oracle and independent audit replay."""
import argparse,copy,gzip,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_semantic_versions as previous
gate=previous.gate;ROOT=gate.ROOT
gate.MANIFEST=ROOT/'research/ui_consumers_v1.json'
gate.BINARY=ROOT/'build-consumers/Release';gate.DLL=gate.BINARY/'ia_lua533_consumers.dll';gate.EXE=gate.BINARY/'authority-consumers.exe'
gate.OLD=ROOT/'build-semantic-versions/Release/ia_lua533_semantic_versions.dll'
old_protected=gate.protected
def protected():
    result=old_protected()
    for folder in ['semantic_versions_runtime','build-semantic-versions/Release']:
        for p in (ROOT/folder).iterdir():
            if p.is_file() and (folder=='semantic_versions_runtime' or p.suffix in ['.dll','.exe','.lib']):result[p.relative_to(ROOT).as_posix()]=gate.digest(p)
    result['research/ui_scoped_versions_v2.json']=gate.digest(ROOT/'research/ui_scoped_versions_v2.json')
    return result
gate.protected=protected
old_canonical=gate.canonical
def canonical(report):
    result=old_canonical(report)
    for phase in result.get('phases',[]):
        phase.pop('consumer_checkpoints',None);phase.pop('consumer_initial_checkpoint',None)
    return result
gate.canonical=canonical
def baseline_equal(first,old):
    if first['id']=='consumer-poison':return gate.ordinary(first)==gate.ordinary(old)
    return canonical(copy.deepcopy(first))==canonical(copy.deepcopy(old))
gate.baseline_equal=baseline_equal
old_metrics=gate.compact_metrics
def metrics(report):
    result=old_metrics(report);result['consumers']=report.get('execution_before_diagnostics',{}).get('consumers');return result
gate.compact_metrics=metrics
CAPTURED={}
old_invoke=gate.invoke
def invoke(case,label,dll,out,timeout):
    old=os.environ.get('IA_CONSUMER_VERIFY');os.environ['IA_CONSUMER_VERIFY']='1'
    try:r,a,j=old_invoke(case,label,dll,out,timeout)
    finally:
        if old is None:os.environ.pop('IA_CONSUMER_VERIFY',None)
        else:os.environ['IA_CONSUMER_VERIFY']=old
    CAPTURED[(case['id'],label)]={'consumer':r.get('consumer_readsets'),'phases':r.get('phases',[]),'budget':r.get('budget')}
    return r,a,j
gate.invoke=invoke
old_decode=gate.decode
def decode(path):
    result=old_decode(path)
    name=path.name.removesuffix('-candidate-1.audit')
    expected=CAPTURED.get((name,'candidate-1'),{}).get('consumer')
    if expected is not None and result['consumer_records']!=expected['records']:raise RuntimeError('Consumer independent audit reconstruction mismatch')
    return result
gate.decode=decode

def resolve(index=0,phase=None,expected=None,error=None,hit=False,stable=False):
    s={'action':'resolve','index':index}
    if phase is not None:s['phase']=phase
    if expected is not None:s['expected_view']=expected
    if error:s['error_contains']=error
    if hit:s['require_hit']=True
    if stable:s['require_no_invalidation']=True
    return s
def bind(index,value,phase=None,authority=701):
    s={'action':'bind','index':index,'evidence':{'value':value,'authority_value_id':authority,'authority_owner_version':1}}
    if phase is not None:s['phase']=phase
    return s
def chunk(name,steps=None,epoch=None):
    p=ROOT/'research/consumer_fixtures'/name
    s={'file':p.relative_to(ROOT).as_posix(),'sha256':gate.digest(p)}
    if steps is not None:s['consumer_steps']=steps
    if epoch is not None:s['trace_epoch']=epoch
    return s
def freeze():
    spec=json.loads((ROOT/'research/ui_scoped_versions_v2.json').read_text(encoding='utf-8'));spec['schema']='consumer-readsets-short-1'
    text=lambda value:{'text_hex':value.encode().hex()}
    first=[resolve(0,expected=2),resolve(3,expected='amount=2'),bind(0,1),resolve(0,expected=1),resolve(3,expected='amount=1'),resolve(2,expected=1),resolve(4,expected=1),resolve(0,expected=1,hit=True),bind(1,500,authority=702),resolve(0,expected=1,hit=True,stable=True),resolve(3,expected='amount=1',hit=True,stable=True)]
    second=[resolve(0,0,1,hit=True,stable=True),resolve(3,0,'amount=1',hit=True,stable=True),resolve(0,expected=1),resolve(2,expected=1),resolve(4,expected=1)]
    third=[bind(0,5,authority=703),resolve(0,expected=5),resolve(2,expected=5),resolve(4,expected=5),resolve(3,expected='amount=1'),resolve(0,0,1,hit=True,stable=True)]
    spec['cases'].append({'id':'consumer-field-upvalue-scope','kind':'functional','configuration':{'amount':2,'x':2},'pin_prior_frames':True,'reclaim':True,'verify_full_origins':True,'chunks':[chunk('setup.lua',first),chunk('unrelated.lua',second),chunk('related.lua',third)],'expected':[[2,2,2,text('amount=2'),2],[2,193,2,text('amount=2'),2],[3,193,3,text('amount=2'),3]]})
    spec['cases'].append({'id':'consumer-history-timepoint','kind':'functional','configuration':{'amount':2,'x':137},'pin_prior_frames':True,'reclaim':True,'verify_full_origins':True,'chunks':[chunk('setup.lua',[bind(0,1),resolve(0,expected=1),resolve(3,expected='amount=1')],1),chunk('refresh.lua',[bind(0,3,phase=0,authority=704),resolve(0,expected=3),resolve(1,expected='amount=1'),resolve(2,expected=1),resolve(0,expected=3,hit=True)],2)],'expected':[[2,137,2,text('amount=2'),2],[2,text('amount=2'),2]]})
    spec['cases'].append({'id':'consumer-unsupported-projection','kind':'consumer-safety','configuration':{'amount':2,'x':137},'reclaim':True,'chunks':[chunk('unsupported.lua',[bind(1,1),resolve(0,error='Unsupported slice3 projected native contract: math.floor'),resolve(1,expected=1)])],'expected':[[2,2]]})
    spec['cases'].append({'id':'consumer-poison','kind':'consumer-safety','configuration':{'amount':2,'x':137},'chunks':[chunk('setup.lua',[bind(0,1),resolve(0,expected=1),{'action':'fault'},resolve(0,error='Consumer read-set oracle mismatch')])],'expected':[[2,137,2,text('amount=2'),2]]})
    for c in spec['cases']:c['audit_disk_limit']=16*1024*1024
    spec['acceptance']['consumer_validation']='per-hit uncached value and actual-read-set oracle; independent revision/certificate replay'
    spec['acceptance']['baseline']='previous semantic-version candidate; full semantic graph/certificate proof retained except injected poison test'
    if gate.MANIFEST.exists():
        if json.loads(gate.MANIFEST.read_text(encoding='utf-8'))!=spec:raise RuntimeError('Frozen consumer manifest differs')
    else:gate.save(gate.MANIFEST,spec)
    print(json.dumps({'cases':len(spec['cases']),'manifest_sha256':gate.digest(gate.MANIFEST)}))

def verify_records(records):
    revisions={};certificates={};hits=0;invalidations=0
    def valid(c):return all(revisions.get(a['id'],(0,False))==(a['revision'],a['retired']) for a in c['reads'])
    for event in records:
        action=event['action']
        if action=='revision':
            if event['revision']<=max((r[0] for r in revisions.values()),default=0):raise RuntimeError('Non-monotonic consumer revision')
            revisions[event['id']]=(event['revision'],event['retired'])
        elif action=='complete':
            if event['certificate'] in certificates or not valid(event):raise RuntimeError('Consumer completed against stale read set')
            if len({a['id'] for a in event['reads']})!=len(event['reads']):raise RuntimeError('Duplicate consumer atom')
            certificates[event['certificate']]=event
        elif action in ['hit','invalidate']:
            c=certificates[event['certificate']]
            if any(event[k]!=c[k] for k in ['kind','root','epoch']):raise RuntimeError('Consumer use identity mismatch')
            if action=='hit':
                if not valid(c):raise RuntimeError('Consumer reused stale certificate')
                hits+=1
            else:
                if valid(c):raise RuntimeError('Consumer invalidated an unchanged read set')
                invalidations+=1
        else:raise RuntimeError('Unknown consumer audit event')
    return {'records':len(records),'certificates':len(certificates),'hits':hits,'invalidations':invalidations}

def run(out,only):
    result=previous.run(out,only);spec=json.loads(gate.MANIFEST.read_text(encoding='utf-8'));checks=[]
    for row in result['cases']:
        data=CAPTURED[(row['id'],'candidate-1')];other=CAPTURED.get((row['id'],'candidate-2'),{})
        if data['consumer'] is None:continue
        record_check=verify_records(data['consumer']['records']);stats=data['consumer']['stats']
        repeat=data['consumer']==other.get('consumer') if row['kind'] not in ['process-safety','certificate-safety'] else True
        ok=repeat and stats['active_captures']==0 and stats['bytes']<=stats['byte_limit'] and stats['entries']<=stats['entry_limit']
        assertions=[];case=next(c for c in spec['cases'] if c['id']==row['id'])
        for phase,actual in zip(case['chunks'],data['phases']):
            for index,(step,observed) in enumerate(zip(phase.get('consumer_steps',[]),actual.get('consumer_steps',[]))):
                v=observed['result'];passed=True
                if 'expected_view' in step:passed=v.get('ok') is True and v.get('value')==step['expected_view']
                if 'error_contains' in step:passed=v.get('ok') is False and step['error_contains'] in v.get('error','')
                cp=actual['consumer_checkpoints'];prior=cp[index-1] if index else actual.get('consumer_initial_checkpoint')
                if step.get('require_hit'):passed=passed and prior is not None and cp[index]['hits']>prior['hits']
                if step.get('require_no_invalidation'):passed=passed and prior is not None and cp[index]['invalidations']==prior['invalidations']
                assertions.append({'action':step['action'],'passed':passed,'result':v});ok=ok and passed
        if stats['hits'] and row['id']!='consumer-poison':ok=ok and stats['oracle_enabled'] and stats['oracle_checks']==stats['hits']
        row['consumer_gate']=ok;checks.append({'id':row['id'],'passed':ok,'repeat_equal':repeat,'audit_replay':record_check,'stats':stats,'assertions':assertions})
    result['schema']='consumer-readsets-gate';result['consumer_checks']=checks;result['passed']=result['passed'] and all(c['passed'] for c in checks)
    result['scope']='authority-reference predicate and top-level HUD projection; whole-object tracing unchanged'
    gate.save(out/'result.json',result);print(json.dumps({'passed':result['passed'],'cases':len(result['cases']),'complete_manifest':result['complete_manifest'],'consumer_failures':[c['id'] for c in checks if not c['passed']],'seconds':result['seconds']}));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--case',action='append');a=p.parse_args()
    if a.freeze:freeze()
    if a.output:sys.exit(0 if run(a.output.resolve(),a.case)['passed'] else 1)
