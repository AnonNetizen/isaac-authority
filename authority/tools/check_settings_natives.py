"""Stock-Lua conformance and authority use of registered scalar C functions."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_settings_value as core
ROOT=core.ROOT;DIR=core.DIR;MANIFEST=DIR/'native-v1.json'
def freeze():
    base=copy.deepcopy(core.parent.parent.world.parent.f.load(core.MANIFEST)['cases'][0])
    # Keep the original frozen test mod; the extra module only adds a HUD callback.
    base.pop('authority_timeline');base.pop('fork',None);base.pop('change',None);base['steps']=[]
    c=copy.deepcopy(base);c.update(id='registered-scalars-match-stock-bytes-arity-nil-and-errors',native_contract=True,compact_audit=False)
    code="local x=ValuesConfig.amount;local s='a'..x..x;local a,b=string.find(s,'%d+');local absent=string.find(s,'none',1,true);local repl,n=string.gsub(s,'%d','Z');local ok,err=pcall(string.find,s,'[');return a,b,string.sub(s,a,b),tonumber(string.sub(s,a,b)),math.floor(x+0.75),math.min(x+0.5,3),absent,repl,n,ok,type(err),string.sub('中\\0'..x,1,4)"
    c['steps']=[core.parent.parent.world.ev(code)]
    c['expected_values']=core.parent.parent.world.values(2,3,'22',22,2,2.5,None,'aZZ',2,False,'string','中\0')
    cases=[c]
    mod=DIR/'native-mod/main.lua';mod.parent.mkdir(parents=True,exist_ok=True)
    core.parent.parent.world.parent.f.parent.frozen(mod,(ROOT/'settings_value_runtime/native_fixture.lua').read_bytes())
    c=copy.deepcopy(base);c['id']='native-format-find-follow-host-and-distinguish-result-slots';c['compact_audit']=True
    c['modules']['roots'].append(dict(root=mod.parent.relative_to(ROOT).as_posix(),display='mods/settings-native-fixture',sha256={'main.lua':core.sha(mod)}));c['mod_sdk']['load_order']=[0,1,2]
    for store,amount in zip(c['mod_sdk']['stores'],[12,3]):
        data=json.loads(store[core.OWNER]);data['amount']=amount;store[core.OWNER]=json.dumps(data,separators=(',',':'))
    c['steps']=[dict(core.parent.parent.world.dispatch(1,451,'host'),phase='authority'),core.parent.parent.world.dispatch(1,458)]
    c['authority_timeline']=dict(schema='authority-state-timeline-1',branch_views=True,links={'personal:presentation:458:1':dict(authority='host:authority:451:1',view='end',project_hud=True)})
    c['expected_hud']='value:12|7:8';cases.append(c)
    core.parent.parent.world.parent.f.freeze_json(MANIFEST,dict(schema='settings-native-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    print(json.dumps(dict(frozen=True,cases=len(cases))))
def run(out):
    protected=core.parent.parent.world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in core.parent.parent.world.parent.f.load(MANIFEST)['cases']:
        pairs=[core.invoke(MANIFEST,c)for _ in range(2)];r=pairs[0][1]
        checks={'bounded-completed':all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p is not None and'semantic'in p for a,p in pairs)}
        stock=None;stock_a=None
        if checks['bounded-completed']:
            checks['repeat-semantics-and-evidence']=r['semantic']==pairs[1][1]['semantic']and r['steps']==pairs[1][1]['steps']and r['branch_views']==pairs[1][1]['branch_views']
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['full_trace_enabled']and not p['game_started']for _,p in pairs)
            if c.get('native_contract'):
                stock_a,stock=core.invoke(MANIFEST,c,True)
                checks['stock-completed']=stock_a['returncode']==0 and stock is not None and'semantic'in stock
                if checks['stock-completed']:
                    aliases=core.parent.source_aliases(c);checks['exact-stock-values-errors-and-state']=r['steps']==stock['steps']and core.parent.strip_audit(r['semantic'],aliases)==core.parent.strip_audit(stock['semantic'],aliases)
                checks['frozen-exact-values']=r['steps'][0]['values']==c['expected_values']
                nodes=r['sparse_provenance'][1]['nodes'];find=[n for n in nodes if n['op']=='native-scalar-result'and n['function']=='string.find']
                checks['distinct-native-result-slots']=any(n['result_index']==1 and n['actual']==core.parent.parent.world.values(2)[0]for n in find)and any(n['result_index']==2 and n['actual']==core.parent.parent.world.values(3)[0]for n in find)
                checks['nil-preserved-as-an-actual-result']=any(n['actual']==dict(type='nil')for n in find)
                checks['caught-error-remains-observable']=any(n['op']=='registered-native-call'and not n['completed']for n in nodes)
            else:
                frame=r['steps'][1];checks['actual-game-hud']=[bytes.fromhex(d['text_hex']).decode('utf-8')for d in frame['draws']]==[c['expected_hud']]
                checks['ordinary-personal-value-still-independent']=[bytes.fromhex(d['text_hex']).decode('utf-8')for d in frame['branch_views']['ordinary_draws']]==['value:3|7:7']
                checks['native-arguments-projected-without-world-reexecution']=r['branch_views']['presentation_settings_values']['native_scalar_projected_arguments']>0 and r['semantic']['world']['coins']==12 and len(r['semantic']['world']['effects'])==1
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,reports=[p for _,p in pairs],artifacts=[a for a,_ in pairs],stock_control=stock,stock_artifact=stock_a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==core.parent.parent.world.parent.f.parent.protection.protection()
    result=dict(schema='settings-native-results-1',passed=all(r['passed']for r in rows),cases=rows,manifest_sha256=core.sha(MANIFEST),binaries={p.relative_to(ROOT).as_posix():core.sha(p)for p in [core.EXE,core.REF]},protected_files_unchanged=True,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output)else 1)
