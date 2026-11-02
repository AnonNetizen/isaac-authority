"""Bounded actual-API sparse provenance probes and unchanged World View regressions."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as world
import bounded_font_process
ROOT=world.ROOT;DIR=ROOT/'research/sparse_value';MANIFEST=DIR/'suite-v2.json'
EXE=ROOT/'build-sparse-value/Release/authority-sparse-value.exe';REF=EXE.with_name('authority-sparse-value-reference.exe')

CODE="""SparseMod=RegisterMod('Sparse Value Fixture',1)
local cfg=require('json').decode(SparseMod:LoadData())
local alias=cfg
local cached=tostring
local function tail(v)return v end
local function helper(v)return cached(v)..'\\0' end
local function closure()return alias.amount end
local captured=closure()
local P=Isaac.GetPlayer(0)
SparseMod:AddCallback(1,function()P:AddCoins(alias.amount)end)
SparseMod:AddCallback(2,function()Isaac.RenderText(cfg.language..'|'..helper(tail(closure()+cfg.x*2)),cfg.x,0)end)
SparseMod:AddCallback(3,function()Isaac.RenderText(string.upper(cfg.language)..':'..cfg.amount,0,0)end)
SparseMod:AddCallback(4,function()cfg.amount=cfg.amount+1;Isaac.RenderText(cached(cfg.amount),0,0)end)
SparseMod:AddCallback(5,function()local t={a=alias.amount};rawset(t,'a',tail(t.a));Isaac.RenderText(cached(t.a),0,0)end)
SparseMod:AddCallback(6,function()local t={};table.insert(t,cfg.amount);Isaac.RenderText(cached(t[1]),0,0)end)
SparseMod:AddCallback(7,function()if cfg.amount>1 then Isaac.RenderText('high',0,0)else Isaac.RenderText('low',0,0)end end)
SparseMod:AddCallback(8,function()local n=0;for i=1,4200 do n=n+cfg.amount end;Isaac.RenderText(cached(n),0,0)end)
SparseMod:AddCallback(9,function()local n=0;for i=1,10000 do n=n+i end;Isaac.RenderText(cached(n),0,0)end)
SparseMod:AddCallback(10,function()Isaac.RenderText(cached(captured),0,0)end)
SparseMod:AddCallback(11,function()cfg.amount=cfg.amount+1;error('sparse-injected')end)
SparseMod:AddCallback(12,function()Isaac.RenderText(cfg.language..':'..cfg.amount,0,0)end)
"""

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
    DIR.mkdir(exist_ok=True);source=DIR/'main.lua'
    world.parent.f.parent.frozen(source,CODE.encode())
    base=copy.deepcopy(world.parent.f.load(world.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k not in ['id','steps','kind','values']}
    display='mods/sparse-value-fixture'
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=sha(source),modules=dict(entry=0,roots=[dict(root=DIR.relative_to(ROOT).as_posix(),display=display,sha256={'main.lua':sha(source)})]))
    base['mod_sdk']['stores']=[{display:'{"amount":1,"language":"en","x":17}'},{display:'{"amount":2,"language":"zh","x":137}'}]
    cases=[]
    def c(name,event,**kw):
        x=copy.deepcopy(base);x.update(id=name,steps=kw.pop('steps',[world.dispatch(event=event)]),**kw);cases.append(x)
    c('aliases-closures-tail-cached-string-bytes',2,text='zh|276\0',roots=['/amount','/language','/x'])
    c('unknown-native-remains-opaque',3,text='ZH:2',opaque=True)
    c('mutated-value-gets-new-production-version',4,text='3',operation='add')
    c('rawset-copy-preserves-producer',5,text='2',roots=['/amount'])
    c('table-library-copy-preserves-producer',6,text='2',roots=['/amount'])
    c('tagged-condition-is-explicitly-unresolved',7,text='high',condition=True)
    c('fixed-capacity-refuses-and-restores',8,steps=[world.dispatch(event=8,expect_error='Sparse node capacity exceeded'),world.dispatch(2,event=12)],text='zh:2',private_only=True)
    c('unrelated-loop-does-not-create-value-graph',9,text='50005000',node_max=5)
    c('cross-callback-upvalue-keeps-producer',10,steps=[world.dispatch(event=4),world.dispatch(2,event=10)],texts=['3','2'],roots=['/amount'])
    c('injected-failure-rebuilds-private-config',11,steps=[world.dispatch(event=11,expect_error='sparse-injected'),world.dispatch(2,event=12)],text='zh:2')
    c('host-world-consumer-has-exact-config-source',1,steps=[dict(world.dispatch(event=1,role='host'),phase='authority'),world.dispatch(event=12)],text='zh:2',world_root='/amount')
    secondary=DIR/'secondary/main.lua'
    world.parent.f.parent.frozen(secondary,b"local m=RegisterMod('Secondary',1)\nlocal c=require('json').decode(m:LoadData())\nm:AddCallback(13,function()Isaac.RenderText(c.language..':'..c.amount,0,0)end)\n")
    c('identical-bytes-from-two-mods-retain-distinct-roots',13,text='zh:2',distinct_owners=True)
    other='mods/sparse-secondary';last=cases[-1]
    last['modules']['roots'].append(dict(root=secondary.parent.relative_to(ROOT).as_posix(),display=other,sha256={'main.lua':sha(secondary)}))
    last['mod_sdk']['load_order']=[0,1]
    for store in last['mod_sdk']['stores']:store[other]=store[display]
    world.parent.f.freeze_json(MANIFEST,dict(schema='sparse-value-observation-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(world.parent.f.load(world.REAL));real['schema']='sparse-value-real-initialization-1';real['cases']=real['cases'][:3]
    for c in real['cases']:
        c['id']=c['id'].replace('post-render','initialization');c['steps']=[];c.pop('requires_hud',None)
    world.parent.f.freeze_json(DIR/'real-init-v1.json',real)
    print(json.dumps(dict(frozen=True,cases=len(cases))))

def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--sparse-value-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'])
    raw=a.pop('stdout');err=a.pop('stderr');a.update(stderr_hex=err.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest())
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r

def roots(graph,tag,seen=None):
    if not tag:return set()
    seen=set()if seen is None else seen
    if tag in seen:return set()
    seen.add(tag);n=graph['nodes'][tag-1]
    if n['op']=='config-field':return {n['path']}
    out=set()
    for arg in n.get('args',[]):out |= roots(graph,arg['tag'],seen)
    return out

def anchors(graph,tag,seen=None):
    if not tag:return []
    seen=set()if seen is None else seen
    if tag in seen:return []
    seen.add(tag);n=graph['nodes'][tag-1]
    if n['op']=='config-field':
        root=graph['nodes'][n['root']-1]
        return [dict(identity=root['identity'],path=n['path'],value_version=tag,actual=n['actual'])]
    return [a for arg in n.get('args',[])for a in anchors(graph,arg['tag'],seen)]

def run(out):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(MANIFEST)['cases']:
        refs=[False,False]if c.get('private_only')else[True,False,False]
        pairs=[invoke(MANIFEST,c,ref)for ref in refs];reports=[p[1]for p in pairs];r=reports[-1];checks={}
        checks['completed-under-limits']=all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p and'semantic'in p for a,p in pairs)
        if checks['completed-under-limits']:
            checks['ordinary-stock-equivalent']=c.get('private_only')or reports[0]['semantic']==r['semantic']and reports[0]['steps']==r['steps']
            checks['repeat-value-graph-exact']=reports[-2]['sparse_provenance']==r['sparse_provenance']and reports[-2]['semantic']==r['semantic']
            frames=[s['draws']for s in r['steps']if'draws'in s];texts=[[bytes.fromhex(d['text_hex']).decode()for d in f]for f in frames]
            checks['exact-bytes']=texts==[[x]for x in c.get('texts',[c.get('text')])]
            checks['formal-limits']=r['budget']['used']<=10000000 and r['seconds']<5 and r['private_commit_bytes']<1024**3 and not r['game_started']and not r['full_trace_enabled']
            g=r['sparse_provenance'][1];sinks=[s for s in g['sinks']if s['api']=='hud.text']
            checks['no-projection-claim']=not r['automatic_projection_implemented']and not r['personal_draws_publishable']and not g['projection_implemented']
            if'roots'in c:checks['exact-field-roots']=sorted(roots(g,sinks[-1]['tag']))==c['roots']
            if c.get('opaque'):checks['unknown-native-taint-retained']=g['opaque_native_calls']>0 and any(n['op']=='opaque-native'for n in g['nodes'])and sinks[-1]['tag']>0
            if c.get('condition'):checks['condition-unresolved-evidence']=g['tagged_conditions']>0 and all(not s['semantic_correspondence_proven']for s in sinks)
            if'operation'in c:checks['explicit-operands']=any(n['op']==c['operation']and len(n.get('args',[]))==2 for n in g['nodes'])
            if'node_max'in c:checks['no-whole-loop-trace']=len(g['nodes'])<=c['node_max']
            if'world_root'in c:
                h=r['sparse_provenance'][0];sink=next(s for s in h['sinks']if s['api']=='world.coins.add');checks['world-contribution-source']=roots(h,sink['tag'])=={c['world_root']}
            if c.get('distinct_owners'):
                checks['interned-bytes-keep-owner']=len({json.dumps(n['identity'],sort_keys=True)for n in g['nodes']if n['op']=='store-root'})==2
                a=anchors(g,sinks[-1]['tag']);checks['consumer-keeps-actual-owner']=bool(a)and all(x['identity']['owner']=='mods/sparse-secondary'for x in a)
            checks['no-audit-read']=all(g['audit_files_read']==0 for g in r['sparse_provenance'])
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,artifacts=[a for a,_ in pairs],reports=reports))
        print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    protected=before==world.parent.f.parent.protection.protection();assert protected
    result=dict(schema='sparse-value-results-1',passed=all(r['passed']for r in rows),cases=rows,manifest_sha256=sha(MANIFEST),driver_sha256=sha(Path(__file__)),binaries={str(p.relative_to(ROOT)):sha(p)for p in [EXE,REF]},protected_files_unchanged=protected,world_projection_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0))
    print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows))))
    return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','regressions','real-init']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':sys.exit(0 if run(a.output)else 1)
    else:
        world.EXE=EXE;world.REF=REF;world.invoke=invoke
        manifest=DIR/'real-init-v1.json'if a.phase=='real-init'else world.MANIFEST
        sys.exit(0 if world.run(manifest,a.output)else 1)
