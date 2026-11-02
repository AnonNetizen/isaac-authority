"""Exact rooted storage versions, bounded CLI tests; original mod sources unchanged."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_sparse_values as sparse
import run_world_view as world
import bounded_font_process
ROOT=world.ROOT;DIR=ROOT/'research/storage_value';MANIFEST=DIR/'suite-v5.json'
EXE=ROOT/'build-storage-value/Release/authority-storage-value.exe';REF=EXE.with_name('authority-storage-value-reference.exe')
CODE="""StorageMod=RegisterMod('Storage Value Fixture',1)
local cfg=require('json').decode(StorageMod:LoadData())
local alias=cfg
local scalar=cfg.amount
local function set(v)scalar=v end
local function show()return scalar end
local function draw(v)Isaac.RenderText(tostring(v),0,0)end
StorageMod:AddCallback(1,function()local old=cfg.amount;cfg.amount=9;cfg.amount=old;draw(old..':'..cfg.amount)end)
StorageMod:AddCallback(2,function()cfg.amount=7;draw(cfg.amount)end)
StorageMod:AddCallback(3,function()rawset(alias,'amount',8);draw(cfg.amount)end)
StorageMod:AddCallback(4,function()table.insert(cfg.list,cfg.amount);local n=table.remove(cfg.list);draw(n..':'..tostring(cfg.list[1]==nil))end)
StorageMod:AddCallback(5,function()set(7);draw(show())end)
StorageMod:AddCallback(6,function()local old=show();set(9);set(old);draw(old..':'..show())end)
StorageMod:AddCallback(7,function()local n=cfg.amount;local function get()return n end;Getter=get;local old=get();n=n+1;draw(old..':'..get())end)
StorageMod:AddCallback(8,function()local n=cfg.amount;local function get()return n end;local old=get();local t={};for i=1,600 do t[i]=i end;local function arity(...)return select('#',...)end;local count=arity(table.unpack(t));draw(old..':'..get()..':'..count)end)
StorageMod:AddCallback(9,function()local t={a=cfg.amount};local old=t.a;t=nil;collectgarbage('collect');local other={a=cfg.amount};draw(old..':'..other.a)end)
StorageMod:AddCallback(10,function()draw(cfg.amount)end)
StorageMod:AddCallback(11,function()cfg.x=cfg.x+1 end)
StorageMod:AddCallback(12,function()local weak=setmetatable({},{__mode='v'});weak.a={amount=cfg.amount};collectgarbage('collect');draw(weak.a==nil)end)
StorageMod:AddCallback(13,function()cfg.amount=8;StorageMod:SaveData(require('json').encode(cfg));draw(cfg.amount);error('storage-injected')end)
StorageMod:AddCallback(14,function()cfg[{}]=1;draw(cfg.amount)end)
StorageMod:AddCallback(15,function()local n=cfg.amount;local function get()return n end;local old=get();n=7;draw(old..':'..get())end)
StorageMod:AddCallback(16,function()local n=cfg.amount;local function get()return n end;local old=get();n=n..'x';draw(old..':'..get())end)
StorageMod:AddCallback(17,function()scalar=6;draw(show())end)
StorageMod:AddCallback(18,function()local t={a=cfg.amount};local old=t.a;t.a=9;t.a=old;draw(old..':'..t.a)end)
StorageMod:AddCallback(19,function()cfg.amount=nil;draw(cfg.amount==nil)end)
StorageMod:AddCallback(20,function()draw(show())end)
StorageMod:AddCallback(21,function()pcall(function()local n=0;for i=1,4200 do n=n+cfg.amount end end);draw('continued')end)
"""
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
    DIR.mkdir(exist_ok=True);source=DIR/'main-v3.lua';world.parent.f.parent.frozen(source,CODE.encode())
    base=copy.deepcopy(world.parent.f.load(world.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k not in ['id','steps','kind','values']}
    owner='mods/storage-value-fixture';base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=sha(source),modules=dict(entry=0,roots=[dict(root=DIR.relative_to(ROOT).as_posix(),display=owner,sha256={'main.lua':sha(source)},source_paths={'main.lua':source.relative_to(ROOT).as_posix()})]))
    base['mod_sdk']['stores']=[{owner:json.dumps(dict(amount=n,x=x,language=lang,list={}),separators=(',',':'))}for n,x,lang in [(1,17,'en'),(2,137,'zh')]]
    cases=[]
    def c(name,event,text,**kw):
        x=copy.deepcopy(base);x.update(id=name,steps=kw.pop('steps',[dict(world.dispatch(event=event),phase='presentation')]),texts=kw.pop('texts',[text]),**kw);cases.append(x)
    c('field-a-b-a-keeps-distinct-versions',1,'2:2',field_version=2,ancestor_versions=[0,2])
    c('constant-field-write-keeps-new-producer',2,'7',field_version=1,constant=7)
    c('rawset-field-write',3,'8',field_version=1,constant=8)
    c('table-library-insert-remove-versions',4,'2:true',list_version=2,nil_diagnostic=True)
    c('shared-closed-upvalue-constant-write',5,'7',cell_written=True)
    c('shared-closed-upvalue-a-b-a',6,'2:2',cell_written=True,cell_aba=True)
    c('open-upvalue-arithmetic-result-finalized',7,'2:3',cell_written=True,arithmetic=True)
    c('open-upvalue-stack-relocation',8,'2:2:600',relocation=True)
    c('gc-retirement-keeps-historical-values',9,'2:2',gc_retire=True)
    c('unrelated-field-does-not-change-consumer-version',10,None,steps=[world.dispatch(event=10),world.dispatch(event=11),world.dispatch(2,event=10)],texts=['2',None,'2'],same_amount=True)
    c('weak-value-gc-write-version',12,'true',gc_write=True,nil_diagnostic=True)
    c('save-private-and-draw-failure-fully-restores',13,'2',steps=[world.dispatch(event=13,expect_error='storage-injected'),world.dispatch(2,event=10)],restored=True)
    c('unknown-field-key-refuses-and-restores',14,'2',steps=[world.dispatch(event=14,expect_error='Storage field key type unsupported'),world.dispatch(2,event=10)],restored=True,private_only=True,kind='expected-safety-rejection')
    c('open-upvalue-constant-write',15,'2:7',cell_written=True)
    c('open-upvalue-concat-result-finalized',16,'2:2x',cell_written=True,concat=True)
    c('write-before-first-private-read',17,'6',cell_written=True)
    c('derived-private-table-a-b-a',18,'2:2',derived_aba=True)
    c('nil-field-remains-explicitly-unpropagated',19,'true',field_version=1,nil_diagnostic=True)
    c('duplicate-frame-does-not-write-twice',2,None,steps=[world.dispatch(event=2),world.dispatch(event=2)],texts=['7','7'],field_version=1,sink_count=1)
    c('changed-duplicate-payload-refuses-without-extra-write',2,None,steps=[world.dispatch(event=2),world.dispatch(event=2,input=world.device(76),expect_error='Menu frame identity reused with different payload'),world.dispatch(2,event=10)],texts=['7','7'],field_version=1)
    def status(event):return dict(op='storage_reads',frame_key=f'personal:presentation:{event}:1')
    c('read-set-unrelated-field-stays-valid',10,None,steps=[world.dispatch(event=10),world.dispatch(event=11),status(10)],texts=['2',None],private_only=True,status_valid=True)
    c('read-set-original-field-write-invalidates',10,None,steps=[world.dispatch(event=10),world.dispatch(event=2),status(10)],texts=['2','7'],private_only=True,status_valid=False)
    c('saved-scalar-does-not-read-original-field-again',20,None,steps=[world.dispatch(event=20),world.dispatch(event=2),status(20)],texts=['2','7'],private_only=True,status_valid=True,no_amount_dependency=True)
    c('read-set-shared-upvalue-write-invalidates',20,None,steps=[world.dispatch(event=20),world.dispatch(event=5),status(20)],texts=['2','7'],private_only=True,status_valid=False)
    c('read-set-a-b-a-is-not-a-cache-hit',10,None,steps=[world.dispatch(event=10),dict(world.dispatch(event=1),phase='presentation'),status(10)],texts=['2','2:2'],private_only=True,status_valid=False)
    c('read-set-mixed-state-remains-explicit',1,None,steps=[dict(world.dispatch(event=1),phase='presentation'),status(1)],texts=['2:2'],private_only=True,status_valid=False,mixed_read=True)
    c('expired-storage-receipt-is-not-reused',10,None,steps=[world.dispatch(i,event=10)for i in range(1,130)]+[dict(status(10),expect_error='Storage read receipt unavailable or expired'),world.dispatch(130,event=10)],texts=['2']*130,private_only=True,receipt_cap=True)
    c('lua-pcall-cannot-hide-evidence-exhaustion',21,'2',steps=[world.dispatch(event=21,expect_error='Sparse node capacity exceeded'),world.dispatch(2,event=10)],private_only=True,restored=True,kind='expected-safety-rejection')
    world.parent.f.freeze_json(MANIFEST,dict(schema='rooted-storage-value-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    print(json.dumps(dict(frozen=True,cases=len(cases))))
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--storage-value-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'])
    raw=a.pop('stdout');err=a.pop('stderr');a.update(stderr_hex=err.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest())
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def ancestors(g,tag):
    seen=set();pending=[tag]
    while pending:
        tag=pending.pop()
        if not tag or tag in seen:continue
        if not 0<tag<=len(g['nodes']):raise RuntimeError('Invalid version graph')
        seen.add(tag);pending.extend(a['tag']for a in g['nodes'][tag-1].get('args',[]))
    return [g['nodes'][i-1]for i in sorted(seen)]
def run(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(MANIFEST)['cases']:
        pairs=[invoke(MANIFEST,c,ref)for ref in ([False,False]if c.get('private_only')else[True,False,False])];reports=[r for _,r in pairs];r=reports[1];checks={}
        checks['bounded-completion']=all(p and'semantic'in p and a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']for a,p in pairs)
        if checks['bounded-completion']:
            if not c.get('private_only'):checks['stock-equivalence']=reports[0]['semantic']==r['semantic']and reports[0]['steps']==r['steps']
            checks['repeat-versions-exact']=reports[-1]['semantic']==reports[-2]['semantic']and reports[-1]['sparse_provenance']==reports[-2]['sparse_provenance']
            frames=[s['draws']for s in r['steps']if'draws'in s];checks['exact-content']=[[bytes.fromhex(d['text_hex']).decode()for d in frame]for frame in frames]==[[]if t is None else[t]for t in c['texts']]
            g=r['sparse_provenance'][1];state=g['storage_versions'];amount=[x for x in state['live']if x['kind']=='field'and x['key']=='s:amount'];sinks=[s for s in g['sinks']if s['api']=='hud.text'];nodes=ancestors(g,sinks[-1]['tag'])
            checks['limits']=r['budget']['used']<=10000000 and r['seconds']<5 and r['private_commit_bytes']<1024**3 and g['audit_files_read']==0
            checks['no-projection-claim']=not r['automatic_projection_implemented']and not r['personal_draws_publishable']and not g['field_write_identity_complete']
            initial=[n for n in g['nodes']if n['op']=='field-version'and n['key']=='s:amount'and n['write_version']==0 and n['origin'].get('kind')=='decoded']
            checks['decoded-value-record-has-actual-type']=bool(initial)and all(n['args'][0]['type']==19 and n['args'][0]['value']==2 and n['args'][0]['tag']>0 for n in initial)
            if'field_version'in c:checks['exact-field-write-version']=len(amount)==1 and amount[0]['write_version']==c['field_version']
            if'ancestor_versions'in c:checks['historical-and-current-storage-uses']=sorted({n['write_version']for n in nodes if n['op']=='field-version'and n['key']=='s:amount'})==c['ancestor_versions']
            if'constant'in c:
                n=g['nodes'][amount[0]['value_version']-1];checks['constant-write-recorded']=n['args'][0]['tag']==0 and n['args'][0]['value']==c['constant']
            if'list_version'in c:checks['table-library-write-count']=any(x['kind']=='field'and x['key']=='i:1'and x['write_version']==c['list_version']for x in state['live'])
            if c.get('cell_written'):checks['upvalue-write-reaches-consumer']=any(n['op']=='cell-version'and n['write_version']>0 for n in nodes)
            if c.get('cell_aba'):checks['closed-upvalue-a-b-a-version']=any(n['op']=='cell-version'and n['write_version']==2 for n in nodes)
            if c.get('arithmetic'):checks['arithmetic-producer-retained']=any(n['op']=='add'for n in nodes)and any(n['op']=='cell-version'and'refines_store'in n for n in nodes)
            if c.get('concat'):checks['concat-producer-retained']=any(n['op']=='concat'for n in nodes)
            if c.get('relocation'):checks['actual-relocation-observed']=state['relocations']>0
            if c.get('gc_retire'):checks['actual-table-retired']=state['retired_tables']>0 and any(n['op']=='field-version'and n['lifetime']not in {x['lifetime']for x in state['live']if x['kind']=='field'}for n in nodes)
            if c.get('gc_write'):checks['actual-gc-write-observed']=any(n.get('gc_write')for n in g['nodes'])
            if c.get('nil_diagnostic'):checks['nil-gap-stays-explicit']=state['nil_reads_without_value_propagation']>0
            if c.get('restored'):checks['restored-original-config']=len(amount)==1 and amount[0]['write_version']==0
            if c.get('same_amount'):
                sets=[{n['id']for n in ancestors(g,s['tag'])if n['op']=='field-version'and n['key']=='s:amount'}for s in sinks];checks['unrelated-write-keeps-same-version']=len(sets)==2 and bool(sets[0])and sets[0]==sets[1]
            if c.get('derived_aba'):checks['derived-field-keeps-versions']=any(n['op']=='field-version'and n['key']=='s:a'and n['write_version']>=3 for n in nodes)
            if'sink_count'in c:checks['duplicate-does-not-execute']=len(sinks)==c['sink_count']
            if'status_valid'in c:
                receipt=next(s for s in r['steps']if'storage_versions_valid'in s);checks['exact-storage-invalidation']=receipt['storage_versions_valid']==c['status_valid']and not receipt['all_inputs_captured']and not receipt['cache_reuse_allowed']
                if c.get('no_amount_dependency'):checks['snapshot-origin-is-not-a-live-read']=all(d['kind']!='field'for d in receipt['dependencies'])
                if c.get('mixed_read'):checks['mixed-read-versions-reported']=any(d['mixed']for d in receipt['dependencies'])
            if c.get('receipt_cap'):checks['bounded-receipts-with-expiration']=len(state['read_scopes'])<=128 and all(s['frame_key']!='personal:presentation:10:1'for s in state['read_scopes'])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,reports=reports,artifacts=[a for a,_ in pairs]));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection()
    result=dict(schema='storage-value-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=sha(MANIFEST),driver_sha256=sha(Path(__file__)),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,world_projection_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows))));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','regressions','real-init','required']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':sys.exit(0 if run(a.output)else 1)
    else:
        world.EXE=EXE;world.REF=REF;world.invoke=invoke
        if a.phase=='required':
            one=world.run(world.PROJECTION,a.output/'projection');two=world.run(ROOT/'research/world_view_required_mixed_v1.json',a.output/'mixed');sys.exit(0 if one and two else 1)
        path=ROOT/'research/sparse_value/real-init-v1.json'if a.phase=='real-init'else world.MANIFEST
        sys.exit(0 if world.run(path,a.output)else 1)
