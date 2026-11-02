"""Actual MCM navigation and bounded per-field save receipt adversaries."""
import argparse,copy,gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_settings_value as core
ROOT=core.ROOT;DIR=core.DIR;MANIFEST=DIR/'serialization-v2.json';world=core.parent.parent.world

def freeze():
    source=DIR/'serialization-mod/main.lua';source.parent.mkdir(parents=True,exist_ok=True)
    world.parent.f.parent.frozen(source,(ROOT/'settings_value_runtime/serialization_fixture.lua').read_bytes())
    base=copy.deepcopy(world.parent.f.load(core.MANIFEST)['cases'][-1]);cases=[]
    for mode in ['copy','two-saves','second-frame','nested','rebuild','duplicate','append-space','native-rewrite','write-divergent','rawset-aba','fail-save','fail-state','fail-draw']:
        c=copy.deepcopy(base);c['id']='serialization-'+mode;c['save_mode']=mode
        c['modules']['roots'][1].update(root=source.parent.relative_to(ROOT).as_posix(),sha256={'main.lua':core.sha(source)})
        c.update(source=source.relative_to(ROOT).as_posix(),source_sha256=core.sha(source))
        for store in c['mod_sdk']['stores']:
            v=json.loads(store[core.OWNER]);v['mode']=mode
            if mode=='nested':v['details']={'flag':0,'language':'en'}
            store[core.OWNER]=json.dumps(v,separators=(',',':'))
        menu=[s for s in c['steps']if s.get('op')=='dispatch'and s.get('event')==2]
        error={'append-space':'Settings callback effect transcripts differ','native-rewrite':'Settings callback effect transcripts differ','write-divergent':'Settings callback effect transcripts differ','rawset-aba':'Settings callback effect transcripts differ','fail-save':'serialization-injected-after-save','fail-state':'serialization-injected-after-effects','fail-draw':'serialization-injected-after-effects'}.get(mode)
        if error:menu[-1]['expect_error']=error;c['expected_error']=error
        c['required_compatibility']=not bool(error)
        index=next(i for i,s in enumerate(c['steps'])if s.get('event')==453);frame=c['steps'][index]['frame_id']
        if mode=='second-frame':
            c['steps'][index:index]=[world.dispatch(frame),world.dispatch(frame+1,input=world.device(action=1))]
            c['steps'][index+2]['frame_id']=frame+2
        if mode=='rebuild':c['steps'].insert(index,dict(op='rebuild'))
        if mode=='duplicate':c['steps'][index:index]=[dict(op='purpose_state'),copy.deepcopy(menu[-1]),dict(op='purpose_state')]
        c['authority_timeline']['links']={f"{s['role']}:{s['phase']}:{s['event']}:{s['frame_id']}":dict(authority='host:authority:451:1',view='end',project_hud=True)for s in c['steps']if s.get('op')=='dispatch'and s.get('role')=='personal'}
        cases.append(c)
    world.parent.f.freeze_json(MANIFEST,dict(schema='settings-serialization-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    print(json.dumps(dict(frozen=True,cases=len(cases))))

def run(out,path=MANIFEST):
    protected=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(path)['cases']:
        pairs=[core.invoke(path,c)for _ in range(2)];r=pairs[0][1]
        checks={'bounded-completed':all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p is not None and'semantic'in p for a,p in pairs)}
        refusal='expected_error'in c
        if checks['bounded-completed']:
            other=pairs[1][1];checks['repeat-values-config-draws-proofs']=all(r[k]==other[k]for k in ['semantic','steps','branch_views','settings_values'])
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for _,p in pairs)
            checks['rewards-follow-host-once']=r['semantic']['world']['coins']==1 and len(r['semantic']['world']['effects'])==1
            if c.get('source_reclamation'):
                states=r['source_collection'];checks['collection-enabled-and-source-limits']=all(s['enabled']and s['active_nodes']<=4096 for s in states.values())and states['personal']['collections']>0 and states['presentation']['collections']>0
                checks['no-forced-lua-gc-or-callbacks']=all(not s['last']['scan']['lua_gc_forced']and not s['last']['scan']['lua_callbacks_executed']for s in states.values()if s['last']is not None)
            amount=2 if refusal else 2+c.get('expected_changes',2 if c['save_mode']=='second-frame'else 1)
            checks['ordinary-private-state']=r['steps'][-1]['values']==world.values(amount,20,137)
            saved=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][core.OWNER]['data_hex']))
            shadow=json.loads(bytes.fromhex(r['branch_views']['presentation_stores'][core.OWNER]['data_hex']))
            checks['exact-personal-save']=saved['amount']==amount and saved['private']==(0 if refusal else 20)and saved['x']==137
            checks['exact-private-game-save']=shadow['amount']==amount and shadow['private']==(0 if refusal else 10)and shadow['x']==137
            hud=next(t for s,t in zip(c['steps'],r['steps'])if s.get('event')==453)
            checks['hud-game-view-and-position']=[bytes.fromhex(d['text_hex']).decode('utf-8')for d in hud['draws']]==['amount=1','one','private=10','coins=1']and all(d['x']==137 for d in hud['draws'])
            proofs=[p for t in r['steps']for p in t.get('branch_views',{}).get('settings_values',{}).get('proofs',[])if p['kind']=='settings-save-accepted-context-pass-through']
            if refusal:
                checks['specific-rejection-and-full-recovery']=any(t.get('error')==c['expected_error']for t in r['steps'])and not proofs
            else:
                checks['field-identity-and-entry-version-proofs']=bool(proofs)and all(p['root']['owner']==core.OWNER and not p['presentation_save_published']and p['unchanged_divergent_fields']and all(f['ordinary']['identity']==f['presentation']['identity']and f['ordinary']['unchanged_since_entry']and f['presentation']['unchanged_since_entry']for f in p['unchanged_divergent_fields'])for p in proofs)
                menus=[t for s,t in zip(c['steps'],r['steps'])if s.get('event')==2]
                checks['real-menu-keeps-personal-values']=f'amount={amount}'in [bytes.fromhex(d['text_hex']).decode('utf-8')for t in menus for d in t['draws']if'text_hex'in d]
            if c['save_mode']=='two-saves':checks['two-saves-in-one-real-callback']=len(proofs)==2
            if c['save_mode']=='second-frame':checks['previous-view-receipts-match']=len(proofs)==c.get('expected_changes',2)
            if c['save_mode']=='nested':checks['nested-field-identity-retained']=saved['details']=={'flag':20,'language':'en'}and shadow['details']=={'flag':10,'language':'en'}and any(f['path']=='/details/flag'for p in proofs for f in p['unchanged_divergent_fields'])
            if c['save_mode']=='duplicate':
                states=[s for s in r['steps']if'forwarded_values'in s];checks['duplicate-no-new-calls-or-effects']=len(states)==2 and states[0]==states[1]
        rows.append(dict(id=c['id'],passed=all(checks.values()),checks=checks,boundary_diagnostic=refusal,reports=[p for _,p in pairs],artifacts=[a for a,_ in pairs]));print(json.dumps(dict(id=c['id'],passed=rows[-1]['passed'],failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==world.parent.f.parent.protection.protection()
    result=dict(schema='settings-serialization-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=core.sha(path),binaries={p.relative_to(ROOT).as_posix():core.sha(p)for p in [core.EXE,core.REF]},protected_files_unchanged=True,full_real_ui_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--output',type=Path);p.add_argument('--manifest',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(a.output,a.manifest or MANIFEST)else 1)
