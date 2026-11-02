"""Bounded logs and evidence-backed partial ItemConfig; no game process."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_value_objects as v
ROOT=v.ROOT;old=v.old;FOLDER=ROOT/'research/engine_services';MANIFEST=ROOT/'research/engine_services_v1.json';CORRECTED=ROOT/'research/engine_services_v2.json';CURRENT=ROOT/'research/engine_services_v3.json';REAL=ROOT/'research/engine_services_real_v1.json'
EXE=ROOT/'build-engine-services/Release/authority-services.exe';REF=EXE.with_name('authority-services-reference.exe')
CATALOG=FOLDER/'item_config.json'
def freeze():
    evidence=ROOT/'runs/engine-api-j460-20261010-03/engine-api.json';report=v.s.o.load(evidence)
    source=ROOT/'native/engine_api.cpp';code=source.read_text(encoding='utf-8')
    assert report['probe_passed']and report['checks']['two_private_contexts_cached_readonly_metadata']and report['checks']['metadata_readonly_and_progress_query_refused']
    assert "assert(config:GetTrinket(1).ID==1 and config:GetCard(1).ID==1 and config:GetPillEffect(0).ID==0)"in code
    assert report['metadata_contexts'][0]==report['metadata_contexts'][1]
    row=report['metadata_contexts'][0];assert row[0]=={'t':'integer','v':1}and row[1]['t']=='string'and row[2]=={'t':'integer','v':3}
    name=bytes.fromhex(row[1]['hex']).decode('utf-8');assert name=='#THE_SAD_ONION_NAME'
    snapshot=dict(schema='partial-native-item-config-1',coverage='partial',captured_game='J460 historical native probe; not current live state',
        evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=old.digest(p))for p in [evidence,source]],
        items=[dict(kind=0,id=1,fields=dict(ID=1,Name=name,Quality=3))]+[dict(kind=k,id=i,fields=dict(ID=i))for k,i in [(1,1),(2,1),(3,0)]])
    v.s.o.freeze_json(CATALOG,snapshot)
    main="""ServiceMod=RegisterMod('Engine Services Fixture',1)
local cfg=require('json').decode(ServiceMod:LoadData())
Config=Isaac.GetItemConfig();Item=Config:GetCollectible(1)
local cached=Config.GetCollectible
Isaac.DebugString('init:'..cfg.language)
ServiceMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
ServiceMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;ServiceMod:SaveData(require('json').encode(cfg))end
 Isaac.DebugString(cfg.language..'|'..Item.Name)
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins(),cfg.x,0)
 if Input.IsButtonTriggered('fail')then cfg.x=999;ServiceMod:SaveData('uncommitted');Isaac.DebugString('uncommitted');Isaac.RenderText('unpublished',0,0);error('service-injected')end
end)
ServiceMod:AddCallback(3,function()Isaac.RenderText(cached(Config,1).Name..'|q='..Item.Quality,0,0)end)
"""
    p=FOLDER/'main.lua';v.s.o.freeze_file(p,main.encode('utf-8'))
    rr=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/engine-services-fixture',sha256={'main.lua':old.digest(p)})
    common=dict(source=p.relative_to(ROOT).as_posix(),source_sha256=old.digest(p),modules=dict(entry=0,roots=[rr]),objects=v.s.o.load(v.s.o.MANIFEST)['cases'][0]['objects'],
      value_objects=v.profile(),mod_sdk=v.s.profile([rr],[{rr['display']:old.store(1,17,'en')},{rr['display']:old.store(2,137,'zh')}],[0]),
      engine_services=dict(catalog=dict(path=CATALOG.relative_to(ROOT).as_posix(),sha256=old.digest(CATALOG))),stores=['{}','{}'])
    cases=[]
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(event=2,**kw):return dict(op='dispatch',event=event,phase='presentation',**kw)
    def status():return dict(op='service_status')
    def cap():return dict(op='capture_reads',event=3,phase='presentation')
    def case(id,steps,expected=None,kind='functional',**kw):
        c=copy.deepcopy(common);c.update(id=id,steps=steps,kind=kind,**kw)
        if expected is not None:c['expected_values']=v.values(*expected)
        cases.append(c);return c
    case('actual-native-snapshot-fields',[ev("return type(Config),Item.ID,Item.Name,Item.Quality,Config:GetTrinket(1).ID,Config:GetCard(1).ID,Config:GetPillEffect(0).ID")],['userdata',1,name,3,1,1,0])
    case('cached-lookup-and-alias',[ev("local alias=Config;local get=alias.GetCollectible;return get(alias,1).Name,get(Isaac.GetItemConfig(),1).Quality")],[name,3])
    case('raw-log-bytes-and-void',[ev("return select('#',Isaac.DebugString(string.char(255)..'中文'))"),status()],[0],last_log_hex=(b'\xff'+'中文'.encode()).hex())
    case('log-max-supported-length',[ev("Isaac.DebugString(string.rep('x',10219))"),status()],last_log_hex=('x'*10219).encode().hex())
    case('independent-private-logs',[dict(dispatch(),role='host'),dispatch(input={'move':True}),dict(dispatch(),role='host'),status()],frames=[['en|x=17|coins=0'],['zh|x=147|coins=0'],['en|x=17|coins=0']],expected_log_counts=[3,2])
    case('authority-coins-personal-settings',[dict(dispatch(1),role='host',phase='authority'),dispatch(input={'move':True}),status()],frames=[['zh|x=147|coins=1']],expected_coins=1)
    case('save-reload',[dispatch(input={'move':True}),dict(op='reload_saved'),dispatch(),status()],frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']],expected_log_counts=[1,2])
    case('rollback-after-log-save-and-draw',[dispatch(input={'move':True}),dict(dispatch(input={'fail':True}),expect_error='service-injected'),dispatch(),status()],frames=[['zh|x=147|coins=0'],['zh|x=147|coins=0']],expected_log_counts=[1,3],forbidden_log='uncommitted')
    case('metadata-consumer-unrelated-write',[cap(),ev('UnrelatedServiceField=42'),dict(op='consumer_status',consumer=3),status()],valid_status=[True],frames=[[name+'|q=3']])
    case('metadata-cache-survives-gc',[cap(),dict(op='gc'),dict(op='consumer_status',consumer=3),status()],valid_status=[True],frames=[[name+'|q=3']])
    case('rebuild-does-not-duplicate-logs',[dispatch(),dict(op='rebuild'),status()],expected_log_counts=[1,2],frames=[['zh|x=137|coins=0']])
    case('read-only-refusal-restores-reader',[cap(),ev('Item.Quality=99',expect_error='ItemConfig is read-only'),dict(op='consumer_status',consumer=3),dispatch(3),status()],valid_status=[True],frames=[[name+'|q=3'],[name+'|q=3']])
    for id,code,error in [
      ('unknown-id','Config:GetCollectible(2)','Uncaptured ItemConfig lookup'),
      ('negative-id','Config:GetCollectible(-1)','Uncaptured ItemConfig lookup'),
      ('unknown-field','return Item.Hidden','Uncaptured ItemConfig field'),
      ('unknown-progress','return Item:IsAvailable()','Uncaptured ItemConfig field'),
      ('unknown-list','return Config:GetCollectibles()','ItemConfig method not implemented'),
      ('forged-receiver','Config.GetCollectible({},1)','Foreign ItemConfig receiver'),
      ('item-as-service','Config.GetCollectible(Item,1)','Foreign ItemConfig receiver'),
      ('wrong-id-type',"Config:GetCollectible('1')",'Expected integer'),
      ('wrong-getter-args','Isaac.GetItemConfig(1)','GetItemConfig takes no arguments'),
      ('root-write','Config.Name=1','ItemConfig is read-only'),
      ('wrong-log-args','Isaac.DebugString()','DebugString requires one string'),
      ('wrong-log-type','Isaac.DebugString(7)','Expected string'),
      ('log-nul',"Isaac.DebugString('a'..string.char(0)..'b')",'Embedded NUL log contract unverified'),
      ('log-truncation',"Isaac.DebugString(string.rep('a',10220))",'DebugString truncation contract unverified')]:
        case('reject-'+id,[ev(code,expect_error=error),dispatch(3),status()],frames=[[name+'|q=3']],expected_log_counts=[1,1])
    case('reject-log-record-cap',[ev("for i=1,257 do Isaac.DebugString('x')end")],kind='process-rejection',error='Private log capacity exceeded')
    case('reject-log-byte-cap',[ev("for i=1,7 do Isaac.DebugString(string.rep('x',10000))end")],kind='process-rejection',error='Private log capacity exceeded')
    c=case('reject-catalog-hash',[],kind='process-rejection',error='Service evidence hash mismatch');c['engine_services']['catalog']['sha256']='0'*64
    v.s.o.freeze_json(MANIFEST,dict(schema='engine-services-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    corrected=copy.deepcopy(cases)
    c=next(c for c in corrected if c['id']=='raw-log-bytes-and-void')
    c['expected_values_at']=dict(step=0,values=c.pop('expected_values'))
    v.s.o.freeze_json(CORRECTED,dict(schema='engine-services-contracts-2',work_limit=10000000,timeout_seconds=5,contract_correction='Void-return expectation remains integer zero at evaluate step 0; the trailing status step has no values. Frozen Lua source and expected value unchanged.',cases=corrected))
    bounded=copy.deepcopy(corrected)
    for id,code,error in [('oversize-field-key',"return Item[string.rep('x',65)]",'ItemConfig field key capacity exceeded'),('oversize-log-before-admission',"Isaac.DebugString(string.rep('x',65536))",'DebugString truncation contract unverified')]:
        c=copy.deepcopy(common);c.update(id=id,kind='functional',steps=[ev(code,expect_error=error),dispatch(3),status()],frames=[[name+'|q=3']],expected_log_counts=[1,1]);bounded.append(c)
    c=copy.deepcopy(v.s.o.load(v.CURRENT)['cases'][0]);c.update(id='profile-absent-status-refused',kind='process-rejection',steps=[dict(op='service_status')],error='Engine services profile not installed');c.pop('expected_values',None);bounded.append(c)
    v.s.o.freeze_json(CURRENT,dict(schema='engine-services-contracts-3',work_limit=10000000,timeout_seconds=5,cases=bounded))
    real=copy.deepcopy(v.s.o.load(v.REAL))
    for c in real['cases']:c['engine_services']=copy.deepcopy(common['engine_services'])
    real['schema']='engine-services-real-entry-1';v.s.o.freeze_json(REAL,real)
    print(json.dumps(dict(frozen=True,cases=len(bounded),real_entries=3,known_item_identities=4,coverage='partial',game_started=False)))

def invoke(path,c,reference=False):
    start=time.perf_counter()
    try:p=subprocess.run([str(REF if reference else EXE),'--services-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:return dict(returncode=-9,seconds=time.perf_counter()-start,stderr='5-second timeout; killed and reaped'),None
    if len(p.stdout)>2*1024**2:raise RuntimeError('Service output capacity exceeded')
    try:r=json.loads(p.stdout)
    except ValueError:r=None
    return dict(returncode=p.returncode,seconds=time.perf_counter()-start,stderr=p.stderr.decode('utf-8',errors='replace'),invalid_stdout=p.stdout[-4096:].decode('utf-8',errors='replace')if r is None else None),r

def setup():v.EXE=EXE;v.REF=REF;v.invoke=invoke;v.s.EXE=EXE;v.s.REF=REF;v.s.invoke=invoke

def run(path,out,real=False):
    setup();r=v.s.run(path,out,real);cases={c['id']:c for c in v.s.o.load(path)['cases']}
    for row in r['cases']:
        c=cases[row['id']];p=row['reports'][1];checks=row['checks']
        if p and c['id']in ['reject-log-record-cap','reject-log-byte-cap']:
            reason='(records)'if c['id']=='reject-log-record-cap'else'(bytes)'
            checks.append(dict(check='specific-resource-limit-reached',passed=reason in p.get('first_unsupported_entry','')))
        if p and 'semantic'in p:
            logs=p['semantic']['private_logs']
            if c.get('expected_values_at')is not None:
                expected=c['expected_values_at'];checks.append(dict(check='expected-values-at-recorded-step',passed=p['steps'][expected['step']].get('values')==expected['values']))
            checks.append(dict(check='all-private-logs-match-stock-and-repeat',passed=all(x['semantic']['private_logs']==logs for x in row['reports'])))
            if c.get('expected_log_counts')is not None:checks.append(dict(check='private-transaction-log-counts',passed=[len(x)for x in logs]==c['expected_log_counts']))
            if c.get('last_log_hex')is not None:checks.append(dict(check='raw-log-bytes',passed=logs[1][-1]['text_hex']==c['last_log_hex']))
            if c.get('forbidden_log'):checks.append(dict(check='rejected-log-not-committed',passed=all(c['forbidden_log'].encode().hex()!=x['text_hex']for role in logs for x in role)))
            checks.append(dict(check='bounded-config-root-and-cache',passed=all(x['engine_services']['live_config_handles']<=5 and x['engine_services']['cached_items']<=4 for x in p['metadata'])))
        row['passed']=all(x['passed']for x in checks)
    r['passed']=len(r['cases'])==len(cases)and all(c['passed']for c in r['cases']);r['schema']='engine-services-results-1';r['services_driver_sha256']=old.digest(Path(__file__))
    data=(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode();p=out/'result.json.gz';p.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(p.read_bytes())==data
    print(json.dumps(dict(services_finished=True,passed=r['passed'],cases=len(r['cases']),failures=[dict(id=c['id'],checks=[x['check']for x in c['checks']if not x['passed']])for c in r['cases']if not c['passed']])),flush=True);return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(REAL if a.phase=='real'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
