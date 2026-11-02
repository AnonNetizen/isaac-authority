"""Bounded native value lifecycle and incremental provenance, no game attach."""
import argparse,copy,gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_settings_value as core
import check_settings_serialization as saving
import check_source_reclamation as roots
ROOT=core.ROOT;DIR=core.DIR;world=core.parent.parent.world
CONTRACTS=DIR/'native-pressure-contracts-v1.json';STRESS=DIR/'native-pressure-stress-v2.json'
VALUES=DIR/'native-pressure-values-v1.json';SAVES=DIR/'native-pressure-saves-v1.json'
CODEC=DIR/'native-pressure-codec-v1.json'
ROOTS=DIR/'native-pressure-roots-v1.json'
INIT=DIR/'native-pressure-init-v1.json';INIT_CONTROL=DIR/'native-pressure-init-controls-v1.json'

def freeze():
    for original,target in [(core.DIR/'reclamation-stress-v1.json',STRESS),(roots.VALUES,VALUES),(roots.SAVES,SAVES),(roots.MANIFEST,ROOTS)]:
        m=copy.deepcopy(world.parent.f.load(original));m['schema']='native-pressure-'+m['schema']
        for c in m['cases']:c['native_value_pressure']=True
        if target==STRESS:
            m['schema']='shared-audit-'+m['schema']
            for c in m['cases']:c['shared_draw_audit']=True
        world.parent.f.freeze_json(target,m)
    compare=copy.deepcopy(next(c for c in world.parent.f.load(SAVES)['cases']if c['id']=='serialization-six-frame-changes'));compare['shared_draw_audit']=True
    world.parent.f.freeze_json(CODEC,dict(schema='shared-draw-audit-conformance-1',work_limit=10000000,timeout_seconds=5,cases=[compare]))
    for old,new,tracked in [(ROOT/'research/branch_views/init-v1.json',INIT,True),(ROOT/'research/branch_views/init-controls-v1.json',INIT_CONTROL,False)]:
        m=copy.deepcopy(world.parent.f.load(old));m['schema']='native-pressure-real-init-1'
        for c in m['cases']:c['native_value_pressure']=True;c['source_reclamation']=tracked
        world.parent.f.freeze_json(new,m)
    source=DIR/'pressure-mod/main.lua';source.parent.mkdir(parents=True,exist_ok=True)
    world.parent.f.parent.frozen(source,(ROOT/'settings_value_runtime/pressure_fixture.lua').read_bytes())
    base=copy.deepcopy(world.parent.f.load(core.MANIFEST)['cases'][0]);base.pop('authority_timeline');base['native_value_pressure']=True
    owner='mods/native-pressure-fixture';base['modules']['roots'].append(dict(root=source.parent.relative_to(ROOT).as_posix(),display=owner,sha256={'main.lua':core.sha(source)}));base['mod_sdk']['load_order']=[0,1,2]
    cases=[]
    for mode in ['deferred-finalizers','gc-stop','failure-restore','native-finalizer-aba-refuses']:
        c=copy.deepcopy(base);c['id']='native-pressure-'+mode;c['pressure_mode']=mode
        for store in c['mod_sdk']['stores']:store[owner]=json.dumps(dict(stop=mode=='gc-stop'),separators=(',',':'))
        if mode=='native-finalizer-aba-refuses':
            c['steps']=[dict(world.dispatch(1,472),expect_error='Native value finalizer mutation unsupported by pressure policy'),world.ev('return PressureHeld.X,PressureHeld.Y,PressureFinalized')]
        else:
            force=dict(op='native_pressure_force')
            if mode=='failure-restore':force.update(inject_failure=True,expect_error='Native pressure injected after collection')
            c['steps']=[world.dispatch(1,471),world.ev('return PressureFinalized,PressureWeak.held~=nil,PressureWeak.dead~=nil'),force,world.ev('return PressureFinalized,PressureWeak.held~=nil,PressureWeak.dead==nil'),dict(op='gc'),world.ev('return PressureFinalized,PressureHeld.X,PressureHeld.Y'),dict(op='gc'),world.ev('return PressureFinalized')]
        cases.append(c)
    world.parent.f.freeze_json(CONTRACTS,dict(schema='native-pressure-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    print(json.dumps(dict(frozen=True,contracts=len(cases))))

def run_init(out):
    protected=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(INIT)['cases']:
        sa,stock=core.invoke(INIT_CONTROL,c,True);pairs=[core.invoke(INIT,c)for _ in range(2)];r=pairs[0][1]
        all_pairs=[(sa,stock),*pairs];checks={'bounded-completed':all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p is not None and'semantic'in p for a,p in all_pairs)}
        if checks['bounded-completed']:
            checks['ordinary-stock-initialization-equivalence']=r['semantic']==stock['semantic']
            checks['third-context-and-policies-active']=r['branch_views']['enabled']and r['branch_views']['presentation']['lane']==2 and all(s['enabled']for s in r['source_collection'].values())and all(s['enabled']for s in r['native_value_pressure'].values())
            checks['repeated-initialization-and-evidence']=r['semantic']==pairs[1][1]['semantic']and r['branch_views']==pairs[1][1]['branch_views']
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for _,p in all_pairs)
        rows.append(dict(id=c['id'],passed=all(checks.values()),checks=checks,reports=[p for _,p in pairs],artifacts=[a for a,_ in pairs],stock_control=stock,stock_artifact=sa));print(json.dumps(dict(id=c['id'],passed=rows[-1]['passed'],failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==world.parent.f.parent.protection.protection()
    result=dict(schema='native-pressure-real-init-results-1',passed=all(c['passed']for c in rows),cases=rows,manifests={p.relative_to(ROOT).as_posix():core.sha(p)for p in [INIT,INIT_CONTROL]},binaries={p.relative_to(ROOT).as_posix():core.sha(p)for p in [core.EXE,core.REF]},protected_files_unchanged=True,full_real_ui_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']

def run_codec(out):
    protected=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False)
    c=world.parent.f.load(CODEC)['cases'][0];a,packed=core.invoke(CODEC,c);b,plain=core.invoke(SAVES,c)
    completed=all(p is not None and'semantic'in p and artifact['returncode']==0 and not artifact['timed_out']and not artifact['output_limit_exceeded']and not artifact['reader_failures']for artifact,p in [(a,packed),(b,plain)])
    checks={'bounded-completed':completed}
    if completed:
        checks['exact-restored-draw-values-config-and-proofs']=all(packed[k]==plain[k]for k in ['semantic','steps','branch_views','settings_values'])
        t=packed['draw_audit_transport'];checks['bounded-shared-state-and-full-round-trip']=t['self_round_trip_verified']and t['frames']<=256 and t['states']<=4096 and t['dictionary_bytes']<=2*1024**2 and t['expanded_frame_byte_bound']<=16*1024**2
        checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 for p in [packed,plain])
    assert protected==world.parent.f.parent.protection.protection()
    row=dict(id='shared-audit-matches-unshared-real-mcm',passed=all(checks.values()),checks=checks,reports=[packed,plain],artifacts=[a,b])
    result=dict(schema='shared-draw-audit-conformance-result-1',passed=row['passed'],cases=[row],manifest_sha256=core.sha(CODEC),binaries={p.relative_to(ROOT).as_posix():core.sha(p)for p in [core.EXE,core.REF]},protected_files_unchanged=True,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));print(json.dumps(dict(id=row['id'],passed=row['passed'],failed=[k for k,v in checks.items()if not v])));return row['passed']

def run_contracts(out):
    protected=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(CONTRACTS)['cases']:
        pairs=[core.invoke(CONTRACTS,c)for _ in range(2)];r=pairs[0][1];mode=c['pressure_mode']
        checks={'bounded-completed':all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p is not None and'semantic'in p for a,p in pairs)}
        stock=stock_a=None
        if checks['bounded-completed']:
            checks['repeat-values-world-and-save']=r['semantic']==pairs[1][1]['semantic']and [s['values']for s in r['steps']if'values'in s]==[s['values']for s in pairs[1][1]['steps']if'values'in s]
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for _,p in pairs)
            values=[s['values']for s in r['steps']if'values'in s]
            if mode=='native-finalizer-aba-refuses':checks['pcall-cannot-hide-finalizer-mutation']=r['steps'][0].get('error')=='Native value finalizer mutation unsupported by pressure policy'and values==[world.values(17.0,23.0,0)]
            else:
                expected=[world.values(0,True,True),world.values(0,True,mode=='deferred-finalizers'),world.values(1,17.0,23.0),world.values(1)]
                checks['finalizers-deferred-then-run-once-and-held-values-survive']=values==expected
                state=r['native_value_pressure']['personal']
                checks['native-limits-and-policy-explicit']=state['enabled']and state['registry_limit']==1024 and not state['custom_native_finalizer_supported']
                if mode=='deferred-finalizers':checks['callback-free-collection-used']=state['cycles']==1 and state['last']['finalizers_invoked_by_pressure']==0 and state['last']['pending_finalizers_after']>0
                if mode=='gc-stop':checks['user-stopped-gc-respected']=state['cycles']==0 and state['stopped_requests']==1
                if mode=='failure-restore':checks['failed-pressure-rebuilds-history']=r['steps'][2].get('error')=='Native pressure injected after collection'and state['cycles']==0
                stock_a,stock=core.invoke(CONTRACTS,c,True)
                checks['stock-backend-completed']=stock is not None and'semantic'in stock and stock_a['returncode']==0 and not stock_a['timed_out']and not stock_a['output_limit_exceeded']
                if checks['stock-backend-completed']:
                    aliases=core.parent.source_aliases(c);checks['stock-values-world-config-and-bytes']=values==[s['values']for s in stock['steps']if'values'in s]and core.parent.strip_audit(r['semantic'],aliases)==core.parent.strip_audit(stock['semantic'],aliases)
            checks['world-and-saves-not-changed-by-pressure']=r['semantic']['world']['coins']==0 and not r['semantic']['world']['effects']
        rows.append(dict(id=c['id'],passed=all(checks.values()),checks=checks,reports=[p for _,p in pairs],artifacts=[a for a,_ in pairs],stock_control=stock,stock_artifact=stock_a));print(json.dumps(dict(id=c['id'],passed=rows[-1]['passed'],failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==world.parent.f.parent.protection.protection()
    result=dict(schema='native-pressure-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=core.sha(CONTRACTS),binaries={p.relative_to(ROOT).as_posix():core.sha(p)for p in [core.EXE,core.REF]},protected_files_unchanged=True,full_real_ui_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','contracts','stress','values','saves','codec','roots','real-init']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='contracts':sys.exit(0 if run_contracts(a.output)else 1)
    elif a.phase=='codec':sys.exit(0 if run_codec(a.output)else 1)
    elif a.phase=='roots':sys.exit(0 if roots.run(a.output,ROOTS)else 1)
    elif a.phase=='real-init':sys.exit(0 if run_init(a.output)else 1)
    elif a.phase=='values':sys.exit(0 if core.run(VALUES,a.output)else 1)
    else:sys.exit(0 if saving.run(a.output,STRESS if a.phase=='stress'else SAVES)else 1)
