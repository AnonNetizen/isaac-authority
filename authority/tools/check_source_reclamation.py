"""Rooted values across collection, real MCM saves and strict stale references."""
import argparse,copy,gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_settings_value as core
import check_settings_serialization as saving
ROOT=core.ROOT;DIR=core.DIR;world=core.parent.parent.world
MANIFEST=DIR/'reclamation-roots-v1.json';SAVES=DIR/'reclamation-serialization-v2.json';VALUES=DIR/'reclamation-values-v1.json'

def freeze():
    m=copy.deepcopy(world.parent.f.load(saving.MANIFEST));m['schema']='settings-source-reclamation-1'
    for c in m['cases']:c['source_reclamation']=True
    extra=copy.deepcopy(next(c for c in m['cases']if c['save_mode']=='second-frame'));extra['id']='serialization-six-frame-changes';extra['expected_changes']=6
    at=next(i for i,s in enumerate(extra['steps'])if s.get('event')==453);frame=extra['steps'][at]['frame_id'];more=[]
    for i in range(4):more.extend([world.dispatch(frame+2*i),world.dispatch(frame+2*i+1,input=world.device(action=1))])
    extra['steps'][at:at]=more;extra['steps'][at+len(more)]['frame_id']=frame+len(more)
    extra['authority_timeline']['links']={f"{s['role']}:{s['phase']}:{s['event']}:{s['frame_id']}":dict(authority='host:authority:451:1',view='end',project_hud=True)for s in extra['steps']if s.get('op')=='dispatch'and s.get('role')=='personal'};m['cases'].append(extra)
    world.parent.f.freeze_json(SAVES,m)
    v=copy.deepcopy(world.parent.f.load(core.MANIFEST));v['schema']='settings-source-reclamation-values-1'
    for c in v['cases']:c['source_reclamation']=True
    world.parent.f.freeze_json(VALUES,v)
    source=DIR/'roots-mod/main.lua';source.parent.mkdir(parents=True,exist_ok=True)
    world.parent.f.parent.frozen(source,(ROOT/'settings_value_runtime/roots_fixture.lua').read_bytes())
    base=copy.deepcopy(world.parent.f.load(core.MANIFEST)['cases'][0]);base['source_reclamation']=True
    base['modules']['roots'].append(dict(root=source.parent.relative_to(ROOT).as_posix(),display='mods/source-root-fixture',sha256={'main.lua':core.sha(source)}));base['mod_sdk']['load_order']=[0,1,2]
    cases=[]
    for mode in ['retained-values','lua-gc','rebuild','duplicate','stale-native-version','pool-invariants']:
        c=copy.deepcopy(base);c['id']='source-roots-'+mode;c['root_mode']=mode
        steps=[copy.deepcopy(base['steps'][0]),dict(op='source_collect_all')]+copy.deepcopy(base['steps'][1:-2])+[dict(op='source_collect_all'),world.dispatch(50,461),dict(op='source_collect_all')]
        if mode=='lua-gc':steps.extend([dict(op='gc'),dict(op='source_collect_all')])
        if mode=='rebuild':steps.append(dict(op='rebuild'))
        if mode=='stale-native-version':steps.extend([world.dispatch(51,463),dict(op='source_collect_all')])
        last=world.dispatch(52,461)
        if mode=='stale-native-version':last['expect_error']='UI vector boundary origin unavailable'
        steps.append(last)
        if mode=='duplicate':steps.extend([dict(op='source_gc_state'),copy.deepcopy(last),dict(op='source_gc_state')])
        if mode=='pool-invariants':steps.append(dict(op='source_pool_probe'))
        steps.append(world.ev('return ValuesConfig.amount,ValuesConfig.x'))
        c['steps']=steps
        c['authority_timeline']['links']={f"{s['role']}:{s['phase']}:{s['event']}:{s['frame_id']}":dict(authority='host:authority:451:1',view='end',project_hud=True)for s in steps if s.get('op')=='dispatch'and s.get('role')=='personal'}
        cases.append(c)
    world.parent.f.freeze_json(MANIFEST,dict(schema='source-root-functional-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    print(json.dumps(dict(frozen=True,root_cases=len(cases),save_cases=len(m['cases']))))

def run(out,path=MANIFEST):
    protected=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(path)['cases']:
        pairs=[core.invoke(path,c)for _ in range(2)];r=pairs[0][1]
        checks={'bounded-completed':all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p is not None and'semantic'in p for a,p in pairs)}
        if checks['bounded-completed']:
            other=pairs[1][1]
            def evidence_steps(report):
                result=copy.deepcopy(report['steps'])
                for step in result:
                    if'collections'in step and'scanned_slots'in step:
                        # Lua hash layout may change allocated table capacity.
                        # Preserve all source IDs, roots, proofs and within-run
                        # duplicate checks; only this scan cost is diagnostic.
                        step.pop('scanned_slots')
                        if step.get('last')is not None:step['last']['scan'].pop('slots')
                return result
            checks['repeat-config-draw-and-authority-proofs']=all(r[k]==other[k]for k in ['semantic','branch_views','settings_values'])and evidence_steps(r)==evidence_steps(other)
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for _,p in pairs)
            checks['host-commits-once-personal-config-independent']=r['semantic']['world']['coins']==1 and len(r['semantic']['world']['effects'])==1 and r['steps'][-1]['values']==world.values(2,137)
            frames=[t for s,t in zip(c['steps'],r['steps'])if s.get('event')==461 and'draws'in t]
            checks['actual-retained-world-and-personal-values']=bool(frames)and all([bytes.fromhex(d['text_hex']).decode('utf-8')for d in t['draws']]==['zh|a=6|b=8|v=137:1']and all(d['x']==137 for d in t['draws'])and [bytes.fromhex(d['text_hex']).decode('utf-8')for d in t['branch_views']['ordinary_draws']]==['zh|a=7|b=9|v=137:2']for t in frames)
            states=r['source_collection'];checks['native-and-lua-root-scan-used']=all(s['enabled']and s['collections']>0 and s['active_nodes']<=4096 for s in states.values())and all(s['retired_nodes']>0 and s['last']['scan']['native_vector_roots']>0 and s['last']['scan']['lua_closures']>0 for key,s in states.items()if key!='host')
            checks['no-forced-gc-no-extra-mod-callbacks']=all(not s['last']['scan']['lua_gc_forced']and not s['last']['scan']['lua_callbacks_executed']for s in states.values())
            if c['root_mode']=='duplicate':
                q=[s for s in r['steps']if'collections'in s];checks['duplicate-does-not-collect-or-execute']=len(q)==2 and q[0]==q[1]
            if c['root_mode']=='stale-native-version':checks['no-expired-native-producer-reuse']=any(t.get('error')=='UI vector boundary origin unavailable'for t in r['steps'])
            if c['root_mode']=='pool-invariants':
                p=next(t for t in r['steps']if'retired-reference-refuses'in t);checks['stale-identity-and-failure-atomicity']=all(p.values())
        rows.append(dict(id=c['id'],passed=all(checks.values()),checks=checks,boundary_diagnostic=c['root_mode']=='stale-native-version',reports=[p for _,p in pairs],artifacts=[a for a,_ in pairs]));print(json.dumps(dict(id=c['id'],passed=rows[-1]['passed'],failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==world.parent.f.parent.protection.protection()
    result=dict(schema='source-root-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=core.sha(path),binaries={p.relative_to(ROOT).as_posix():core.sha(p)for p in [core.EXE,core.REF]},protected_files_unchanged=True,long_session_memory_bounded=False,full_real_ui_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','roots','saves','values']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='saves':sys.exit(0 if saving.run(a.output,SAVES)else 1)
    elif a.phase=='values':sys.exit(0 if core.run(VALUES,a.output)else 1)
    else:sys.exit(0 if run(a.output)else 1)
