"""Actual frozen MCM settings values, independent UI and authority HUD."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_trusted_settings as parent
import bounded_font_process
import shared_draw_audit
ROOT=parent.ROOT;DIR=ROOT/'research/settings_value'
EXE=ROOT/'build-settings-value/Release/authority-settings-value.exe'
REF=EXE.with_name('authority-settings-value-reference.exe')
MANIFEST=DIR/'suite-v2.json';OWNER='mods/settings-value-fixture'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
    mod=DIR/'mod/main.lua';mod.parent.mkdir(parents=True,exist_ok=True)
    parent.parent.world.parent.f.parent.frozen(mod,(ROOT/'settings_value_runtime/fixture.lua').read_bytes())
    base=copy.deepcopy(parent.parent.world.parent.f.load(ROOT/'research/trusted_settings/real-v1.json')['cases'][0])
    base.update(source=mod.relative_to(ROOT).as_posix(),source_sha256=sha(mod))
    base['modules']['entry']=1;base['modules']['roots'].append(dict(root=mod.parent.relative_to(ROOT).as_posix(),display=OWNER,sha256={'main.lua':sha(mod)}))
    base['mod_sdk']['load_order']=[0,1]
    for store,amount in zip(base['mod_sdk']['stores'],[1,2]):store[OWNER]=json.dumps(dict(amount=amount,private=0,x=137,language='zh'),separators=(',',':'))
    cases=[]
    def case(name,*,fork=False,change=False,swap=False,duplicate=False,rebuild=False,required=False):
        c=copy.deepcopy(base);c['id']=name
        if swap:
            for store,amount in zip(c['mod_sdk']['stores'],[2,1]):
                v=json.loads(store[OWNER]);v['amount']=amount;store[OWNER]=json.dumps(v,separators=(',',':'))
        steps=[dict(parent.parent.world.dispatch(1,451,'host'),phase='authority')]
        frame=0
        def d(event=2,button=None,action=None):
            nonlocal frame
            frame+=1
            return parent.parent.world.dispatch(frame,event,input=parent.parent.world.device(button=button,action=action))
        if fork:steps.append(d(452))
        steps.extend([d(button=76),d(action=3),d(action=3),d(action=1)])
        if change:steps.append(d(action=1))
        h=d(453);steps.append(h)
        if duplicate:steps.extend([dict(op='purpose_state'),h,dict(op='purpose_state')])
        if rebuild:steps.extend([dict(op='rebuild'),d(453)])
        steps.extend([parent.parent.world.ev('return ValuesConfig.amount,ValuesConfig.private,ValuesConfig.x')])
        c.update(steps=steps,fork=fork,change=change,swap=swap,duplicate=duplicate,rebuild=rebuild,required_compatibility=required,compact_audit=True)
        c['authority_timeline']=dict(schema='authority-state-timeline-1',branch_views=True,links={f"{s['role']}:{s['phase']}:{s['event']}:{s['frame_id']}":dict(authority='host:authority:451:1',view='end',project_hud=True)for s in steps if s.get('op')=='dispatch'and s.get('role')=='personal'})
        cases.append(c)
    case('real-menu-personal-value-and-outside-helper-authority-hud')
    case('real-menu-and-outside-branch-swap-host-personal',swap=True)
    case('real-menu-onchange-saves-personal-field-only',change=True)
    case('read-only-setting-forwards-personal-forked-private-value',fork=True)
    case('duplicate-frame-does-not-repeat-settings-call',duplicate=True)
    case('reconstruction-restores-menu-and-game-views',rebuild=True)
    case('required-save-after-private-state-fork',fork=True,change=True,required=True)
    parent.parent.world.parent.f.freeze_json(MANIFEST,dict(schema='settings-value-functional-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    recovery=copy.deepcopy(cases[-1]);recovery['id']='different-save-receipt-refuses-and-restores-both-views';recovery['safety_recovery']=True
    menu=[s for s in recovery['steps']if s.get('op')=='dispatch'and s.get('event')==2];menu[-1]['expect_error']='Settings callback effect transcripts differ'
    parent.parent.world.parent.f.freeze_json(DIR/'recovery-v1.json',dict(schema='settings-value-recovery-1',work_limit=10000000,timeout_seconds=5,cases=[recovery]))
    real=copy.deepcopy(parent.parent.world.parent.f.load(ROOT/'research/trusted_settings/real-v1.json'))
    parent.parent.world.parent.f.freeze_json(DIR/'real-v1.json',real)
    control=DIR/'control/main.lua';control.parent.mkdir(parents=True,exist_ok=True)
    parent.parent.world.parent.f.parent.frozen(control,(ROOT/'settings_value_runtime/control.lua').read_bytes())
    negatives=[]
    for name,event,role,error in [('mod-loop-cannot-use-sdk-dispatch-iteration-proof',456,'host','Timeline cyclic control flow requires iteration proof'),('opaque-local-length-does-not-hide-related-game-operand',457,'personal','Timeline scalar contract unsupported')]:
        c=copy.deepcopy(base);c['id']=name;c['modules']['roots'].append(dict(root=control.parent.relative_to(ROOT).as_posix(),display='mods/settings-value-controls',sha256={'main.lua':sha(control)}));c['mod_sdk']['load_order']=[0,1,2]
        c['steps']=[dict(parent.parent.world.dispatch(1,451,'host'),phase='authority'),dict(parent.parent.world.dispatch(1,event,role),phase='authority'if role=='host'else'presentation',expect_error=error),parent.parent.world.ev('return ValuesConfig.amount')]
        c['authority_timeline']=dict(schema='authority-state-timeline-1',branch_views=True,links={f'personal:presentation:{event}:1':dict(authority='host:authority:451:1',view='end',project_hud=True)}if role=='personal'else{})
        c['diagnostic_error']=error;negatives.append(c)
    parent.parent.world.parent.f.freeze_json(DIR/'controls-v1.json',dict(schema='settings-value-boundaries-1',work_limit=10000000,timeout_seconds=5,cases=negatives))
    print(json.dumps(dict(frozen=True,cases=len(cases))))
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--settings-value-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'])
    raw=a.pop('stdout');err=a.pop('stderr');a.update(stdout_sha256=hashlib.sha256(raw).hexdigest(),stderr_hex=err.hex())
    try:r=shared_draw_audit.decode(json.loads(raw))
    except (ValueError,TypeError,KeyError,RecursionError)as e:a['decode_failure']=str(e);r=None
    return a,r
def run(path,out):
    protected=parent.parent.world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in parent.parent.world.parent.f.load(path)['cases']:
        pairs=[invoke(path,c)for _ in range(2)];r=pairs[0][1]
        checks={'bounded-completed':all(a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']and p is not None and'semantic'in p for a,p in pairs)}
        if checks['bounded-completed']:
            p=pairs[1][1];checks['repeat-values-draws-config-and-proofs']=r['semantic']==p['semantic']and r['steps']==p['steps']and r['settings_values']==p['settings_values']and r['branch_views']==p['branch_views']
            checks['formal-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for _,p in pairs)
            if c.get('diagnostic_error'):
                checks['exact-explicit-refusal']=any(s.get('error')==c['diagnostic_error']for s in r['steps'])
                checks['authority-and-personal-recovered']=r['semantic']['world']['coins']==1 and len(r['semantic']['world']['effects'])==1 and r['steps'][-1]['values']==parent.parent.world.values(2)
                rows.append(dict(id=c['id'],passed=all(checks.values()),checks=checks,boundary_diagnostic=True,reports=[r for _,r in pairs],artifacts=[a for a,_ in pairs]));print(json.dumps(dict(id=c['id'],passed=rows[-1]['passed'],failed=[k for k,v in checks.items()if not v])),flush=True);continue
            if c.get('safety_recovery'):
                checks['expected-save-mismatch-observed']=any(s.get('error')=='Settings callback effect transcripts differ'for s in r['steps'])
                checks['normal-private-state-restored']=[s['values']for s in r['steps']if'values'in s][-1]==parent.parent.world.values(2,20,137)
                saved=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][OWNER]['data_hex']));checks['failed-save-not-published']=saved['amount']==2 and saved['private']==0
                frames=[t['draws']for s,t in zip(c['steps'],r['steps'])if s.get('event')==453]
                checks['game-view-restored']=[[bytes.fromhex(d['text_hex']).decode('utf-8')for d in f]for f in frames]==[['amount=1','one','private=10','coins=1']]
                checks['authority-not-double-committed']=r['semantic']['world']['coins']==1 and len(r['semantic']['world']['effects'])==1
                rows.append(dict(id=c['id'],passed=all(checks.values()),checks=checks,boundary_diagnostic=True,reports=[r for _,r in pairs],artifacts=[a for a,_ in pairs]));print(json.dumps(dict(id=c['id'],passed=rows[-1]['passed'],failed=[k for k,v in checks.items()if not v])),flush=True);continue
            frames=[(s,t)for s,t in zip(c['steps'],r['steps'])if s.get('op')=='dispatch'and s.get('role')=='personal'and'draws'in t]
            menus=[t for s,t in frames if s['event']==2]
            menu=[d for t in menus for d in t['draws']if'text_hex'in d]
            texts=[bytes.fromhex(d['text_hex']).decode('utf-8')for d in menu]
            personal=1 if c.get('swap')else 2;host=2 if c.get('swap')else 1
            checks['menu-reads-personal-result']=f'amount={personal}'in texts and ('one'if personal==1 else'other')in texts
            hud=[t['draws']for s,t in frames if s['event']==453]
            expected=[f'amount={host}','one'if host==1 else'other','private=10'if c.get('fork')else'private=0',f'coins={host}']
            checks['outside-helper-and-hud-read-game-view']=all([bytes.fromhex(d['text_hex']).decode('utf-8')for d in f]==expected for f in hud)
            checks['personal-position']=all(d['x']==137 for f in hud for d in f)
            checks['authority-reward-once']=r['semantic']['world']['coins']==host and len(r['semantic']['world']['effects'])==1
            branch=r['branch_views']['presentation_settings_values'];all_proofs=[p for t in menus for p in t['branch_views']['settings_values']['proofs']];proofs=[p for p in all_proofs if p['kind']=='paired-setting-return']
            checks['proof-kinds-explicit']=all(p['kind']in ['paired-setting-return','settings-save-accepted-context-pass-through']for p in all_proofs)
            checks['actual-callback-body-and-unique-receipts']=branch['forwarded_values']>0 and branch['active_scopes']==0 and bool(proofs) and all(p['body_executed']and p['effects_matched']and len(p['call']['callee'])==64 for p in proofs) and all(t['branch_views']['settings_values']['frame_calls']==t['branch_views']['settings_values']['consumed_calls']for t in menus)
            if c.get('fork'):checks['menu-personal-private-setting-survives-fork']='private=20'in texts
            vals=[s['values']for s in r['steps']if'values'in s][-1]
            checks['ordinary-personal-state']=vals==parent.parent.world.values(personal+(1 if c.get('change')else 0),20 if c.get('fork')else 0,137)
            if c.get('change'):
                save=json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][OWNER]['data_hex']));checks['published-save-is-personal']=save['amount']==personal+1
                checks['changed-menu-shows-new-personal-value']=f'amount={personal+1}'in [bytes.fromhex(d['text_hex']).decode('utf-8')for d in menus[-1]['draws']if'text_hex'in d]
                if c.get('fork'):
                    saved_proofs=[p for p in all_proofs if p['kind']=='settings-save-accepted-context-pass-through']
                    checks['divergent-save-is-unchanged-field-pass-through']=bool(saved_proofs)and all(p['root']['owner']==OWNER and not p['presentation_save_published']and all(f['ordinary']['unchanged_since_entry']and f['presentation']['unchanged_since_entry']for f in p['unchanged_divergent_fields'])for p in saved_proofs)
                    shadow=json.loads(bytes.fromhex(r['branch_views']['presentation_stores'][OWNER]['data_hex']))
                    checks['both-saved-private-views-retained']=save['private']==20 and shadow['private']==10
            if c.get('duplicate'):
                states=[s for s in r['steps']if'forwarded_values'in s];checks['duplicate-skips-callback-and-save']=states[0]==states[1]
            checks['still-does-not-claim-full-mod-compatibility']=not branch['arbitrary_callback_effects_supported']and not branch['full_ui_gate_passed']
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,required_compatibility=c.get('required_compatibility',False),reports=[r for _,r in pairs],artifacts=[a for a,_ in pairs]));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==parent.parent.world.parent.f.parent.protection.protection()
    result=dict(schema='settings-value-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=sha(path),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,full_real_ui_gate_passed=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','controls','recovery','real','capture-regressions','branch-regressions','api-regressions','storage-regressions','original-gates']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase=='run':sys.exit(0 if run(MANIFEST,a.output)else 1)
    elif a.phase=='controls':sys.exit(0 if run(DIR/'controls-v1.json',a.output)else 1)
    elif a.phase=='recovery':sys.exit(0 if run(DIR/'recovery-v1.json',a.output)else 1)
    else:
        parent.parent.EXE=EXE;parent.parent.REF=REF;parent.parent.invoke=invoke
        if a.phase=='real':passed=parent.parent.run(DIR/'real-v1.json',a.output,True)
        elif a.phase=='capture-regressions':passed=parent.parent.run(parent.parent.MANIFEST,a.output)
        elif a.phase in ['branch-regressions','original-gates']:
            import check_branch_views as b
            b.EXE=EXE;b.REF=REF;b.invoke=invoke;passed=b.run(a.output)if a.phase=='branch-regressions'else b.original_gates(a.output)
        elif a.phase=='storage-regressions':
            import check_storage_values as b
            b.EXE=EXE;b.REF=REF;b.invoke=invoke;passed=b.run(a.output)
        else:
            world=parent.parent.world;world.EXE=EXE;world.REF=REF;world.invoke=invoke;passed=world.run(world.MANIFEST,a.output)
        sys.exit(0 if passed else 1)
