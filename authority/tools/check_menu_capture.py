"""Replay-program capture and actual frozen MCM render frontiers, never pixels."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as world
import bounded_font_process
ROOT=world.ROOT;DIR=ROOT/'research/menu_capture';MANIFEST=DIR/'suite-v3.json';REAL=DIR/'real-v2.json'
EXE=ROOT/'build-menu-capture/Release/authority-menu-capture.exe';REF=EXE.with_name('authority-menu-capture-reference.exe');OWNER='mods/sprite-capture-fixture'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def invoke(path,c,reference=False):
    a=bounded_font_process.run([str(REF if reference else EXE),'--menu-capture-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary']);raw=a.pop('stdout');err=a.pop('stderr');a.update(stderr_hex=err.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest())
    try:r=json.loads(raw)
    except ValueError:r=None
    return a,r
def freeze():
    source=ROOT/'menu_capture_runtime/fixture.lua';frozen=DIR/'main-v3.lua';world.parent.f.parent.frozen(frozen,source.read_bytes());base=copy.deepcopy(world.parent.f.load(world.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k not in ['id','steps','kind','values']}
    base.update(source=frozen.relative_to(ROOT).as_posix(),source_sha256=sha(frozen),modules=dict(entry=0,roots=[dict(root=DIR.relative_to(ROOT).as_posix(),display=OWNER,sha256={'main.lua':sha(frozen)},source_paths={'main.lua':frozen.relative_to(ROOT).as_posix()})]));base['mod_sdk']['stores']=[{OWNER:'{"x":17}'},{OWNER:'{"x":137}'}];cases=[]
    def d(event=401,frame=1,**kw):return dict(world.dispatch(frame,event,**kw),phase='presentation')
    def case(id,steps,frames,**kw):
        c=copy.deepcopy(base);c.update(id=id,steps=steps,frame_counts=frames,**kw);cases.append(c)
    case('sprite-render-snapshots-preserve-ordered-property-versions',[d()],[2],snapshot_pair=True)
    case('cached-render-method-and-omitted-clips',[d(404)],[1],cached=True)
    case('play-update-render-order-retains-update-operation',[d(405)],[1],update=True)
    case('texture-replace-loadgraphics-render-order',[d(408)],[1],texture=True)
    case('duplicate-render-frame-returns-identical-snapshot',[d(),d()],[2,2],duplicate=True)
    case('history-rebuild-restores-program-and-draws',[d(),dict(op='rebuild'),d(402)],[2,1],rebuilt=True)
    case('failure-after-save-property-and-render-restores-all',[d(403,expect_error='sprite-capture-injected'),d(402)],[1],rollback=True)
    case('resource-failure-does-not-queue-render',[d(406,expect_error='Unregistered animation resource'),d(402)],[1],rollback=True,boundary=True)
    case('retired-sprite-program-is-reclaimed-after-gc',[d(407),dict(op='gc'),dict(op='sprite_capture_state')],[2],gc=True)
    case('unknown-render-vector-is-rejected',[d(409,expect_error='Foreign or retired value receiver'),d(402)],[1],rollback=True,boundary=True)
    case('unverified-animation-result-is-never-fabricated',[d(410,expect_error='Sprite state query requires native replay'),d(402)],[1],rollback=True,boundary=True)
    for name,event,text,error in [
        ('world-vector-math-keeps-native-result-producer',411,'57.0|1.0',None),
        ('initial-vector-origin-is-materialized-only-on-use',412,'11.0|22.0',None),
        ('vector-storage-alias-keeps-field-version',414,'9.0|18.0',None),
        ('changed-initial-vector-origin-is-rejected',413,None,'UI vector boundary origin unavailable'),
        ('tainted-vector-mutation-remains-rejected',415,None,'Timeline vector mutation contract unavailable')
    ]:
        steps=[dict(world.dispatch(1,777,'host'),phase='authority'),d(event,**({'expect_error':error}if error else{}))]
        c=copy.deepcopy(base);c.update(id=name,steps=steps,frame_counts=[]if error else[1],expected_text=text,boundary=bool(error),authority_timeline=dict(schema='authority-state-timeline-1',links={f'personal:presentation:{event}:1':dict(authority='host:authority:777:1',view='end',project_hud=True)}));cases.append(c)
    world.parent.f.freeze_json(MANIFEST,dict(schema='menu-capture-model-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    controls=copy.deepcopy(cases)
    for c in controls:
        if'authority_timeline'in c:
            c.pop('authority_timeline');c['steps']=[s for s in c['steps']if'expect_error'not in s]
    world.parent.f.freeze_json(DIR/'controls-v3.json',dict(schema='menu-capture-controls-1',work_limit=10000000,timeout_seconds=5,cases=controls))
    real=[];prior=world.parent.f.load(world.REAL)['cases']
    c=copy.deepcopy(next(c for c in prior if c['id']=='mcm-open-via-personal-input'));c['id']='mcm-open-render-capture';c['steps']=[c['steps'][0],dict(world.dispatch(1,2,'host'),phase='presentation'),world.dispatch(2),world.ev('return ModConfigMenu.IsVisible'),world.ev('return ModConfigMenu.IsVisible',role='host')];real.append(c)
    c=copy.deepcopy(c);c['id']='mcm-open-render-capture-three-contexts';c['steps'].insert(0,dict(world.dispatch(1,777,'host'),phase='authority'));c['steps'].append(dict(op='branch_observe',code='return ModConfigMenu.IsVisible'));c['authority_timeline']=dict(schema='authority-state-timeline-1',branch_views=True,links=dict({f'personal:presentation:2:{f}':dict(authority='host:authority:777:1',view='end',project_hud=True)for f in [1,2]},**{'host:presentation:2:1':dict(authority='host:authority:777:1',view='end',project_hud=True)}));real.append(c)
    for name in ['eid-post-render','combined-post-render','eid-authority-unlock-warning']:real.append(copy.deepcopy(next(c for c in prior if c['id']==name)))
    world.parent.f.freeze_json(REAL,dict(schema='menu-capture-real-1',work_limit=10000000,timeout_seconds=5,cases=real));print(json.dumps(dict(frozen=True,model_cases=len(cases),real_cases=len(real))))
def run(path,out,real=False):
    before=world.parent.f.parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[]
    for c in world.parent.f.load(path)['cases']:
        pairs=[invoke(path,c)for _ in range(2)];reports=[r for _,r in pairs];r=reports[0];checks={}
        checks['bounded-completed']=all(x['returncode']==0 and not x['timed_out']and not x['output_limit_exceeded']and not x['reader_failures']and p is not None and'semantic'in p for x,p in pairs)
        control=None;a=None
        if not real:a,control=invoke(DIR/'controls-v3.json',c,True);checks['stock-control-completed']=a['returncode']==0 and control is not None and'semantic'in control
        if checks['bounded-completed']and checks.get('stock-control-completed',True):
            checks['repeat-state-programs-and-evidence']=r['semantic']==reports[1]['semantic']and r['steps']==reports[1]['steps']and r['sprite_capture']==reports[1]['sprite_capture']
            if not real:checks['stock-lua-contract-equivalence']=control['semantic']==r['semantic']and('authority_timeline'in c or control['steps']==r['steps'])
            frames=[s['draws']for s in r['steps']if'draws'in s];sprites=[d for f in frames for d in f if d.get('op')=='sprite'];fonts=[d for f in frames for d in f if d.get('op')=='font']
            if'frame_counts'in c:checks['exact-render-counts']=[len(f)for f in frames]==c['frame_counts']
            if c.get('expected_text')is not None:checks['exact-vector-expression-result']=[[bytes.fromhex(d['text_hex']).decode('utf-8')for d in f]for f in frames]==[[c['expected_text']]]
            checks['complete-program-and-resource-identities']=all(d['capture_state']['program'][0]['op']=='Construct'and any(o['op']=='Load'for o in d['capture_state']['program'])and all(len(i['sha256'])==64 for i in d['capture_state']['loaded_images'])for d in sprites)
            if c.get('snapshot_pair'):
                a0,b0=sprites[:2];aa,bb=[d['capture_state']for d in [a0,b0]];checks['snapshots-not-final-state']=aa['program']==bb['program'][:-2]and [o['op']for o in bb['program'][-2:]]==['Color','Scale']and a0['arguments']==[[10,20],[0,0],[0,0]]and b0['arguments']==[[30,40],[1,2],[3,4]]
            if c.get('cached'):checks['omitted-clips-preserved']=sprites[0]['native_argument_count']==1 and sprites[0]['arguments']==[[5,7]]
            if c.get('update'):checks['update-recorded-in-order']=[o['op']for o in sprites[0]['capture_state']['program'][-2:]]==['Play','Update']and not sprites[0]['capture_state']['model_state_queryable']and sprites[0]['capture_state']['model_root_frame']is None
            if c.get('texture'):checks['replacement-recorded-in-order']=[o['op']for o in sprites[0]['capture_state']['program'][-2:]]==['ReplaceSpritesheet','LoadGraphics']
            if c.get('duplicate'):checks['duplicate-does-not-mutate-program']=frames[0]==frames[1]
            if c.get('rollback'):checks['program-and-config-restored']=sprites[0]['capture_state']['program_version']==5 and json.loads(bytes.fromhex(r['semantic']['mod_stores'][1][OWNER]['data_hex']))==dict(x=137)
            if c.get('gc'):checks['dead-program-retired']=next(s for s in r['steps']if'live_programs'in s)['live_programs']==1
            if real:
                checks['real-render-has-draws']=bool(sprites or fonts)
                if c['id'].startswith('mcm-open'):
                    values=[s['values']for s in r['steps']if'values'in s];checks['actual-menu-is-open']=values[-2]==world.values(True);checks['host-menu-remains-closed']=values[-1]==world.values(False)and all(not result.get('draws',[])for step,result in zip(c['steps'],r['steps'])if step.get('role')=='host'and step.get('phase')=='presentation');checks['menu-background-and-fonts-captured']=bool(sprites)and bool(fonts)
                    checks['world-not-changed-by-menu']=r['semantic']['menu_snapshot']==world.parent.f.load(world.frozen.MENU)['snapshot']and r['semantic']['world']['coins']==0 and r['semantic']['world']['effects']==[]
                    if c['id'].endswith('three-contexts'):checks['presentation-menu-agrees-with-personal']=[s['presentation_values']for s in r['steps']if'presentation_values'in s][-1]==world.values(True)
                text=[bytes.fromhex(d['text_hex']).decode('utf-8')for d in fonts];checks['actual-category-text-present']=all(t in text for t in ['通用','Mod配置菜单','同步游戏设置: 是','ESCAPE','ENTER'])
            checks['formal-resource-limits']=all(p['budget']['limit']==10000000 and p['budget']['used']==sum(p['budget']['categories'].values())and p['seconds']<5 and p['private_commit_bytes']<1024**3 and not p['game_started']and not p['full_trace_enabled']for p in reports)
        passed=all(checks.values());rows.append(dict(id=c['id'],passed=passed,checks=checks,boundary_diagnostic=c.get('boundary',False),reports=reports,artifacts=[x for x,_ in pairs],stock_control=control,stock_artifact=a));print(json.dumps(dict(id=c['id'],passed=passed,failed=[k for k,v in checks.items()if not v],first_failure=(r or{}).get('first_unsupported_entry'))),flush=True)
    assert before==world.parent.f.parent.protection.protection();result=dict(schema='menu-capture-results-1',passed=all(c['passed']for c in rows),cases=rows,manifest_sha256=sha(path),binaries={p.relative_to(ROOT).as_posix():sha(p)for p in [EXE,REF]},protected_files_unchanged=True,real_source=real,trusted_settings_purpose_implemented=False,configuration_sidecar_implemented=False,pixels_verified=False,playable=False)
    (out/'result.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0));return result['passed']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real','regressions','branch-regressions','contracts','original-gates']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    elif a.phase in ['run','real']:sys.exit(0 if run(REAL if a.phase=='real'else MANIFEST,a.output,a.phase=='real')else 1)
    elif a.phase=='branch-regressions':
        import check_branch_views as branch
        branch.EXE=EXE;branch.REF=REF;branch.invoke=invoke;sys.exit(0 if branch.run(a.output)else 1)
    elif a.phase=='original-gates':
        import check_branch_views as branch
        branch.EXE=EXE;branch.REF=REF;branch.invoke=invoke;sys.exit(0 if branch.original_gates(a.output)else 1)
    else:
        world.EXE=EXE;world.REF=REF;world.invoke=invoke;sys.exit(0 if world.run(DIR/'contracts-v1.json'if a.phase=='contracts'else world.MANIFEST,a.output)else 1)
