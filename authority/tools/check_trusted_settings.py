"""Bounded real MCM identity audit. This ABI never forwards a personal value."""
import argparse, copy, gzip, hashlib, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
import check_menu_capture as parent
import bounded_font_process
ROOT = parent.ROOT
DIR = ROOT / 'research/trusted_settings'
MANIFEST = DIR / 'suite-v3.json'
EXE = ROOT / 'build-trusted-settings/Release/authority-trusted-settings.exe'
REF = EXE.with_name('authority-trusted-settings-reference.exe')
OWNER = 'mods/trusted-settings-fixture'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def freeze():
    frozen = DIR / 'fixture-v3/main.lua'
    # Reuse the frozen spoof bytes; only the main test mod gained fault cases.
    spoof = DIR / 'fixture-v2/scripts/modconfig.lua'
    frozen.parent.mkdir(parents=True, exist_ok=True)
    spoof.parent.mkdir(parents=True, exist_ok=True)
    parent.world.parent.f.parent.frozen(frozen, (ROOT / 'trusted_settings_runtime/fixture.lua').read_bytes())
    parent.world.parent.f.parent.frozen(spoof, (ROOT / 'trusted_settings_runtime/spoof.lua').read_bytes())
    base = copy.deepcopy(parent.world.parent.f.load(DIR / 'real-v1.json')['cases'][0])
    base['source'] = frozen.relative_to(ROOT).as_posix()
    base['source_sha256'] = sha(frozen)
    base['modules']['entry'] = 1
    base['modules']['roots'].append(dict(
        root=spoof.parent.parent.relative_to(ROOT).as_posix(), display=OWNER,
        sha256={'main.lua': sha(frozen), 'scripts/modconfig.lua': sha(spoof)},
        source_paths={'main.lua': frozen.relative_to(ROOT).as_posix(),
                      'scripts/modconfig.lua': spoof.relative_to(ROOT).as_posix()}))
    base['mod_sdk']['load_order'] = [0, 1]
    for store, amount in zip(base['mod_sdk']['stores'], [1, 2]):
        store[OWNER] = json.dumps(dict(amount=amount), separators=(',', ':'))
    frame = 0
    def d(action=None, button=None, event=2, **kw):
        nonlocal frame
        frame += 1
        return parent.world.dispatch(frame, event, input=parent.world.device(button=button, action=action), **kw)
    def nav():
        nonlocal frame
        frame = 0
        # Real Input queries: open, select the third category, enter its options.
        return [d(button=76), d(action=3), d(action=3), d(action=1)]
    def ev(code, **kw):
        return parent.world.ev(code, **kw)
    cases = []
    def case(name, steps, **kw):
        c = copy.deepcopy(base)
        c.update(id=name, steps=steps, **kw)
        cases.append(c)
    case('real-framework-navigation-change-and-info',
         nav() + [d(action=1), dict(op='settings_state'),
                  ev('return AuditValue,AuditChanges,AuditInfo>0,AuditArgs')],
         require_roles=['Display','Info','CurrentSetting','OnChange'], changed=3)
    case('direct-cached-setting-function-outside-menu-is-ordinary',
         [d(event=401), dict(op='settings_state')], outside=True)
    case('spoof-framework-path-and-function-cannot-grant-purpose',
         [d(event=403), dict(op='settings_state')], outside=True)
    case('nested-and-tail-cached-callbacks-preserve-identity',
         nav() + [dict(op='settings_state')], tails=True)
    case('nested-render-scope-ends-before-outside-cached-call',
         nav() + [ev("AuditMode='nested-draw'"), d(), dict(op='settings_state'),
                  d(event=401), dict(op='settings_state')], nested=True)
    case('actual-return-false-nil-and-extra-values-are-preserved',
         nav() + [ev("AuditMode='false-nil'"), d(), dict(op='settings_state')], returns='false-nil')
    case('actual-zero-return-is-distinct-from-nil',
         nav() + [ev("AuditMode='none'"), d(), dict(op='settings_state')], returns='none')
    case('translation-selected-by-real-framework-not-function-name',
         nav() + [ev('AuditSetting.DisplayTranslate=AuditTranslated'), d(), dict(op='settings_state')], translated=True)
    case('callback-exception-restores-before-next-menu-frame',
         nav() + [ev("AuditMode='error'"), d(expect_error='settings-callback-injected'),
                  ev("AuditMode='normal'"), d(), dict(op='settings_state')], recovered=True)
    case('callback-save-private-and-draw-failure-is-atomic',
         nav() + [ev("AuditMode='error-after-effects'"), d(expect_error='settings-effects-injected'),
                  ev("AuditMode='normal'"), d(), dict(op='settings_state'),
                  ev('return AuditValue,AuditChanges')], recovered=True, effects_rollback=True)
    case('info-table-original-callback-result-and-drawing-preserved',
         nav() + [ev("AuditMode='table-info'"), d(), dict(op='settings_state')], table_info=True)
    case('pcall-cannot-hide-unwound-settings-scope',
         nav() + [ev("AuditMode='error'"), d(event=402, expect_error='Settings callback scope unwound without completion'),
                  ev("AuditMode='normal'"), d(), dict(op='settings_state')], recovered=True, boundary=True)
    s = nav(); duplicate = d()
    case('duplicate-menu-frame-keeps-audit-and-callback-count',
         s + [duplicate, dict(op='settings_state'), duplicate, dict(op='settings_state')], duplicate=True)
    case('history-rebuild-restores-registered-identities',
         nav() + [dict(op='settings_state'), dict(op='rebuild'), dict(op='settings_state'), d()], rebuilt=True)
    case('wrong-frozen-profile-hash-is-explicitly-rejected', [], fatal='Settings profile hash mismatch')
    cases[-1]['settings_profile']['sha256']='0'*64
    case('changed-framework-source-hash-is-explicitly-rejected', [], fatal='Frozen module source hash mismatch')
    cases[-1]['modules']['roots'][0]['sha256']['scripts/modconfig.lua']='0'*64
    parent.world.parent.f.freeze_json(MANIFEST, dict(schema='trusted-settings-audit-1',
        work_limit=10000000, timeout_seconds=5, cases=cases))
    deep=copy.deepcopy(base)
    deep.update(id='real-menu-after-lua-stack-growth-preserves-values', steps=[
        ev("IdentityMod:AddCallback(404,function() local function deep(n) if n==0 then ModConfigMenu.PostRender();return 0 end return 1+deep(n-1) end AuditDepth=deep(200) end)"),
        d(button=76,event=404),dict(op='settings_state'),ev('return AuditDepth,ModConfigMenu.IsVisible')], stack_probe=True)
    parent.world.parent.f.freeze_json(DIR/'stack-v1.json',dict(schema='trusted-settings-stack-1',work_limit=10000000,timeout_seconds=5,cases=[deep]))
    print(json.dumps(dict(frozen=True, cases=len(cases))))

def invoke(path, c, reference=False):
    a = bounded_font_process.run([str(REF if reference else EXE), '--trusted-settings-suite',
        str(ROOT), str(path), c['id'], 'reference' if reference else 'boundary'])
    raw = a.pop('stdout'); err = a.pop('stderr')
    a.update(stdout_sha256=hashlib.sha256(raw).hexdigest(), stderr_hex=err.hex())
    try: r = json.loads(raw)
    except ValueError: r = None
    return a, r

def source_aliases(c):
    aliases={}
    for root in c['modules']['roots']:
        for name in root['sha256']:
            p=ROOT/root.get('source_paths',{}).get(name,root['root']+'/'+name)
            physical='@'+str(p.resolve()).replace('\\','/').lower()
            virtual='@'+root['display']+'/'+name
            assert physical not in aliases or aliases[physical]==virtual
            aliases[physical]=virtual
    return aliases

def strip_audit(v, aliases=None):
    if isinstance(v,list): return [strip_audit(x,aliases) for x in v]
    if isinstance(v,dict):
        out={k:strip_audit(x,aliases) for k,x in v.items() if k not in ['settings_audit','presentation_settings']}
        if aliases and 'source_hex'in out:
            source=bytes.fromhex(out['source_hex']).decode('utf-8')
            canonical=aliases.get(source.replace('\\','/').lower(),source)
            out['source_hex']=canonical.encode('utf-8').hex()
        return out
    return v

def run(path, out):
    protected = parent.world.parent.f.parent.protection.protection()
    out.mkdir(parents=True, exist_ok=False)
    rows=[]
    for c in parent.world.parent.f.load(path)['cases']:
        pairs = [invoke(path,c) for _ in range(2)]
        artifacts = [a for a,_ in pairs]; reports = [r for _,r in pairs]
        r = reports[0]; checks={}
        if c.get('fatal'):
            checks['explicit-fatal-diagnostic']=all(a['returncode']!=0 and not a['timed_out'] and not a['output_limit_exceeded'] and not a['reader_failures'] and p is not None and c['fatal']in p.get('first_unsupported_entry','') and 'semantic'not in p for a,p in pairs)
        else:
            checks['bounded-completed'] = all(a['returncode']==0 and not a['timed_out'] and not a['output_limit_exceeded'] and not a['reader_failures'] and p is not None and 'semantic'in p for a,p in pairs)
        control_a, control = invoke(path,c,True)
        # Scope-error rejection is specific to tracked Lua; stock naturally catches it.
        if checks.get('bounded-completed'):
            checks['repeat-values-config-commands-and-identities'] = r['semantic']==reports[1]['semantic'] and r['steps']==reports[1]['steps'] and r['settings_audit']==reports[1]['settings_audit']
            states=[s for s in r['steps'] if 'registered_objects'in s]
            audit=r['settings_audit'][1]
            checks['balanced-callback-scopes']=all(s['active_scopes']==0 and s['entries']==s['returns'] for s in states+[audit])
            checks['real-settings-registered']=audit['registered_objects']==25
            checks['audit-does-not-pretend-to-forward']=not audit['personal_result_forwarding_implemented'] and not audit['configuration_sidecar_implemented']
            if not c.get('boundary'):
                checks['stock-completed']=control_a['returncode']==0 and control is not None and 'semantic'in control
                if checks['stock-completed']:
                    aliases=source_aliases(c)
                    checks['stock-state-config-and-world-equivalence']=strip_audit(control['semantic'],aliases)==strip_audit(r['semantic'],aliases)
                    left=[strip_audit(s,aliases)for s in r['steps']if'registered_objects'not in s]
                    right=[strip_audit(s,aliases)for s in control['steps']if'registered_objects'not in s]
                    checks['stock-return-and-command-equivalence']=left==right
            proofs=[p for s in states for p in s['proofs']]
            if c.get('outside'):
                checks['no-false-setting-purpose']=audit['entries']==0 and not any(d.get('settings_audit')for s in r['steps']for d in s.get('draws',[]))
            else:
                checks['actual-identity-witnesses']=audit['entries']>0 and all(p['identity_matched'] and len(p['callee_source_sha256'])==64 and p['setting_id']>0 for p in proofs if p['kind']=='settings-enter')
            if c.get('require_roles'):
                checks['four-real-callback-roles']=set(c['require_roles'])<=set(p['role'] for p in proofs)
                values=[s['values']for s in r['steps']if'values'in s][-1]
                checks['personal-change-real-callback']=values[:3]==parent.world.values(3,1,True)
                data=r['semantic']['mod_stores'][1][OWNER]
                checks['actual-personal-save']=json.loads(bytes.fromhex(data['data_hex']))['amount']==3
                checks['host-setting-and-save-independent']=json.loads(bytes.fromhex(r['semantic']['mod_stores'][0][OWNER]['data_hex']))['amount']==1 and r['settings_audit'][0]['entries']==0
            if c.get('tails'): checks['tail-return-completes-original-setting']=any(p.get('tail_calls',0)>0 for p in proofs)
            if c.get('returns'):
                expected=parent.world.values(False,None,7)if c['returns']=='false-nil'else[]
                checks['exact-return-arity-and-false-nil']=any(p['kind']=='settings-return'and p['role']=='Display'and p['values']==expected and p['actual_arity']==len(expected) for p in proofs)
            if c.get('translated'):
                checks['real-translation-callback-selected']=any(p['kind']=='settings-return'and p['values']==parent.world.values('translated=2') for p in proofs)
            if c.get('table_info'):
                checks['table-return-is-not-serialized-as-scalar']=any(p['kind']=='settings-return'and p['role']=='Info'and p['values']==[dict(type='table')]for p in proofs)
                frames=[s['draws']for s in r['steps']if'draws'in s]
                texts=[bytes.fromhex(d['text_hex']).decode('utf-8')for d in frames[-1]if'text_hex'in d]
                checks['actual-info-table-text']=all(t in texts for t in ['info-first','info-second'])
            if c.get('nested'):
                frames=[s['draws']for s in r['steps']if'draws'in s]
                checks['nested-draw-trusted-only-in-real-call']=any(d.get('settings_audit',{}).get('kind')=='setting-callback'for d in frames[-2]) and all('settings_audit'not in d for d in frames[-1])
            if c.get('duplicate'): checks['duplicate-skips-setting-execution']=states[-1]==states[-2]
            if c.get('rebuilt'): checks['rebuild-retains-identity-and-proof']=states[0]==states[1]
            if c.get('recovered'): checks['failure-recorded-and-restored']=any('error'in s for s in r['steps']) and states[-1]['active_scopes']==0
            if c.get('stack_probe'): checks['deep-stack-original-result']=[s['values']for s in r['steps']if'values'in s][-1]==parent.world.values(200,True)
            if c.get('effects_rollback'):
                checks['private-and-save-restored']=[s['values']for s in r['steps']if'values'in s][-1]==parent.world.values(2,0) and json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][OWNER]['data_hex']))['amount']==2
                checks['rejected-draw-not-published']=all(d.get('text_hex')!='discarded-setting-draw'.encode().hex()for s in r['steps']for d in s.get('draws',[]))
            checks['formal-resource-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values()) and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started'] and not p['full_trace_enabled'] for p in reports)
        passed=all(checks.values())
        rows.append(dict(id=c['id'],passed=passed,checks=checks,reports=reports,artifacts=artifacts,stock_control=control,stock_artifact=control_a,boundary_diagnostic=bool(c.get('boundary')or c.get('fatal'))))
        print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert protected==parent.world.parent.f.parent.protection.protection()
    result=dict(schema='trusted-settings-audit-results-1',passed=all(r['passed']for r in rows),cases=rows,manifest_sha256=sha(path),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,personal_value_forwarding=False,full_real_ui_gate_passed=False,playable=False)
    raw=json.dumps(result,separators=(',',':')).encode()
    (out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    return result['passed']

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['freeze','run','stack-probe','real','capture-regressions','branch-regressions','api-regressions','original-gates']);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.phase=='freeze':freeze()
    elif args.phase=='run':sys.exit(0 if run(MANIFEST,args.output)else 1)
    elif args.phase=='stack-probe':sys.exit(0 if run(DIR/'stack-v1.json',args.output)else 1)
    else:
        parent.EXE=EXE;parent.REF=REF;parent.invoke=invoke
        if args.phase=='real':passed=parent.run(DIR/'real-v1.json',args.output,True)
        elif args.phase=='capture-regressions':passed=parent.run(parent.MANIFEST,args.output)
        elif args.phase in ['branch-regressions','original-gates']:
            import check_branch_views as branch
            branch.EXE=EXE;branch.REF=REF;branch.invoke=invoke
            passed=branch.run(args.output)if args.phase=='branch-regressions'else branch.original_gates(args.output)
        else:
            parent.world.EXE=EXE;parent.world.REF=REF;parent.world.invoke=invoke
            passed=parent.world.run(parent.world.MANIFEST,args.output)
        sys.exit(0 if passed else 1)
