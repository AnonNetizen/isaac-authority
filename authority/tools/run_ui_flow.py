"""Bounded pause-query and explicit-play animation clock checks."""
import argparse,copy,gzip,hashlib,json,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_font_capture as parent
import bounded_font_process
ROOT=parent.ROOT;FOLDER=ROOT/'research/ui_flow';PROFILE=FOLDER/'profile.json';MANIFEST=ROOT/'research/ui_flow_v2.json';REAL=ROOT/'research/ui_flow_real_v1.json'
EXE=ROOT/'build-ui-flow/Release/authority-ui-flow.exe';REF=EXE.with_name('authority-ui-flow-reference.exe')
load=parent.load;digest=parent.digest;freeze_json=parent.freeze_json;ev=parent.ev;dispatch=parent.dispatch

def freeze():
    source=FOLDER/'main.lua';code='''FlowMod=RegisterMod('UI Flow Fixture',1)
local cfg=require('json').decode(FlowMod:LoadData())
local count=0
G=Game()
A=Sprite();A:Load('gfx/eid_transform_icons.anm2',false);A:Play('Arrow',false)
B=Sprite();B:Load('gfx/ui/modconfig/menu.anm2',false)
FlowMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(cfg.amount)end)
FlowMod:AddCallback(2,function()
 A:Update()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;count=count+1;FlowMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('fail')then A:Update();cfg.x=999;count=999;FlowMod:SaveData('uncommitted');Isaac.RenderText('unpublished',0,0);error('ui-flow-injected')end
 Isaac.RenderText(cfg.language..'|paused='..tostring(G:IsPaused())..'|frame='..A:GetFrame()..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|private='..count,cfg.x,0)
end)
FlowMod:AddCallback(3,function()Isaac.RenderText(tostring(G:IsPaused()),0,0)end)
FlowMod:AddCallback(4,function()Isaac.RenderText(tostring(A:GetFrame()),0,0)end)
FlowMod:AddCallback(5,function()Isaac.RenderText(tostring(A:IsPlaying()),0,0)end)
''';parent.frozen(source,code.encode());base=copy.deepcopy(load(parent.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k in ['objects','value_objects','engine_services','animation_profile','graphics_profile','stores','mod_sdk','font_profile','font_capture_profile']}
    rr=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/ui-flow-fixture',sha256={'main.lua':digest(source)});base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=digest(source),modules=dict(entry=0,roots=[rr]),ui_flow_profile=dict(path=PROFILE.relative_to(ROOT).as_posix(),sha256=digest(PROFILE)))
    base['objects']['scene']['is_paused']=False;base['mod_sdk']['stores']=[{rr['display']:json.dumps(dict(amount=1,language='en',x=17),separators=(',',':'))},{rr['display']:json.dumps(dict(amount=2,language='zh',x=137),separators=(',',':'))}]
    cases=[]
    def case(id,steps,expected=None,**kw):
        c=copy.deepcopy(base);c.update(id=id,steps=steps,kind=kw.pop('kind','functional'),**kw)
        if expected is not None:c['values']=parent.values(*expected)
        cases.append(c);return c
    def scene(revision,paused,frame=42,players=2):return dict(op='set_scene',role='host',scene=dict(revision=revision,is_paused=paused,frame_count=frame,num_players=players))
    def capture(event):return dict(op='capture_reads',event=event,phase='presentation')
    def status(consumer):return dict(op='consumer_status',consumer=consumer)
    case('explicit-pause-snapshot',[ev('return G:IsPaused()')],[False])
    case('pause-change-visible-to-both-roles',[scene(2,True),dict(ev('return G:IsPaused()'),role='host'),ev('return G:IsPaused()')],[True],value_rows=[parent.values(True),parent.values(True)])
    case('pause-read-ignores-frame-change',[capture(3),scene(2,False,frame=43),status(3)],valid=[True])
    case('pause-aba-invalidates',[capture(3),scene(2,True),scene(3,False),status(3)],valid=[False])
    case('loop-next-frame',[ev('A:Update();return A:GetFrame(),A:IsPlaying(),A:IsFinished()')],[1,True,False])
    case('loop-cycle-wrap',[ev('for i=1,47 do A:Update()end;local last=A:GetFrame();A:Update();return last,A:GetFrame(),A:IsPlaying("Arrow"),A:IsFinished("Arrow")')],[47,0,True,False])
    case('loop-10000-updates-fixed-storage',[ev('for i=1,10000 do A:Update()end;return A:GetFrame()'),dict(op='flow_state'),dict(op='sprite_state')],[16],stable_updates=10000)
    case('noop-play-preserves-current-loop',[ev('for i=1,7 do A:Update()end;A:Play("active",false);return A:GetFrame(),A:GetAnimation(),A:IsPlaying("Arrow"),A:IsPlaying("active")')],[7,'Arrow',True,False])
    case('forced-play-restarts',[ev('for i=1,7 do A:Update()end;A:Play("Arrow",true);return A:GetFrame(),A:IsPlaying()')],[0,True])
    case('cached-update-and-query',[ev('local update,frame=A.Update,A.GetFrame;update(A);update(A);return frame(A)')],[2])
    case('paused-game-keeps-explicit-ui-updates',[scene(2,True),ev('A:Update();return G:IsPaused(),A:GetFrame()')],[True,1])
    case('frame-aba-invalidates',[capture(4),ev('for i=1,48 do A:Update()end'),status(4)],valid=[False])
    case('playback-query-ignores-loop-ticks',[capture(5),ev('for i=1,48 do A:Update()end'),status(5)],valid=[True])
    case('forced-play-invalidates-playback-query',[capture(5),ev('A:Play("Arrow",true)'),status(5)],valid=[False])
    case('non-loop-interior-frame',[ev('B:Play("Slider1",true);B:Update();return B:GetFrame()')],[1])
    case('clock-gc-reclaims-owned-sprites',[ev('for i=1,128 do local s=Sprite();s:Load("gfx/eid_transform_icons.anm2",false);s:Play("Arrow",true);s:Update();if i%16==0 then collectgarbage("collect")end end;collectgarbage("collect")'),dict(op='flow_state')],live=1,retired=128)
    case('independent-ui-clocks-and-config',[dict(dispatch(),role='host'),dispatch(move=True),dict(dispatch(),role='host')],frames=[['en|paused=false|frame=1|coins=0|private=0'],['zh|paused=false|frame=1|coins=0|private=1'],['en|paused=false|frame=2|coins=0|private=0']],positions=[17,147,17])
    case('authority-reward-once',[dict(op='dispatch',event=1,phase='authority',role='host'),dispatch(move=True)],frames=[['zh|paused=false|frame=1|coins=1|private=1']],coins=1)
    case('clock-config-save-rollback',[dispatch(move=True),dict(dispatch(move=True,fail=True),expect_error='ui-flow-injected'),dispatch(),dict(op='flow_state')],frames=[['zh|paused=false|frame=1|coins=0|private=1'],['zh|paused=false|frame=2|coins=0|private=1']],restored=True)
    case('accepted-history-rebuild',[dispatch(move=True),dict(op='rebuild'),dispatch()],frames=[['zh|paused=false|frame=1|coins=0|private=1'],['zh|paused=false|frame=2|coins=0|private=1']])
    case('saved-config-reload',[dispatch(move=True),dict(op='reload_saved'),dispatch()],frames=[['zh|paused=false|frame=1|coins=0|private=1'],['zh|paused=false|frame=1|coins=0|private=0']])
    for id,code,error in [
        ('clock-after-setframe','A:SetFrame("Arrow",2);A:Update()','Animation playback state unverified after Load or SetFrame'),
        ('playing-after-setframe','A:SetFrame("Arrow",2);A:IsPlaying()','Animation playback state unverified after Load or SetFrame'),
        ('continuation-after-setframe','A:SetFrame("Arrow",2);A:Play("Arrow",false)','Animation Play continuation state unverified'),
        ('clock-after-reload','A:Load("gfx/eid_transform_icons.anm2",false);A:Update()','Animation playback state unverified after Load or SetFrame'),
        ('non-loop-terminal','B:Play("Idle",true);B:Update()','Animation terminal transition unverified'),
        ('non-loop-flags','B:Play("Idle",true);B:IsFinished()','Animation non-loop playback flags unverified'),
        ('playback-speed','A.PlaybackSpeed=2','Sprite property write not implemented: PlaybackSpeed'),
        ('update-argument','A:Update(1)','Sprite.Update signature unsupported'),
        ('pause-argument','G:IsPaused(1)','Game.IsPaused signature unsupported'),
        ('foreign-update','A.Update(G)','Foreign or stale object receiver'),
        ('personal-reward','Isaac.GetPlayer(0):AddCoins(1)','World write requires authority phase')]:
        case('reject-'+id,[ev(code,expect_error=error),dispatch()],kind='expected-rejection',frames=[['zh|paused=false|frame=1|coins=0|private=0']])
    case('reject-personal-authority',[dict(op='dispatch',event=1,phase='authority',expect_error='Personal context cannot execute authority phase'),dispatch()],kind='expected-rejection',frames=[['zh|paused=false|frame=1|coins=0|private=0']])
    c=case('reject-missing-pause',[ev('G:IsPaused()',expect_error='Missing authoritative scene field: is_paused'),ev('return A:GetFrame()')],[0],kind='expected-rejection');c['objects']['scene'].pop('is_paused')
    c=case('reject-nonboolean-pause',[],kind='process-rejection',error='Authoritative pause field must be boolean');c['objects']['scene']['is_paused']=0
    c=case('reject-flow-profile-hash',[],kind='process-rejection',error='UI flow profile hash mismatch');c['ui_flow_profile']['sha256']='0'*64
    freeze_json(MANIFEST,dict(schema='ui-flow-contracts-2',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(load(parent.PROBES));real['schema']='ui-flow-real-post-render-1'
    for c in real['cases']:c['ui_flow_profile']=copy.deepcopy(base['ui_flow_profile']);c['objects']['scene']['is_paused']=False
    freeze_json(REAL,real);print(json.dumps(dict(frozen=True,cases=len(cases),real_probes=len(real['cases']))))

def invoke(path,c,reference=False):
    p=bounded_font_process.run([str(REF if reference else EXE),'--ui-flow-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary']);raw=p.pop('stdout');error=p.pop('stderr');p.update(stderr_hex=error.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest(),stdout_bytes=len(raw))
    try:r=json.loads(raw)if not p['timed_out']and not p['output_limit_exceeded']and not p['reader_failures']else None
    except ValueError:r=None
    return p,r

def run(path,out,real=False,regression=False):
    before=parent.protection.protection();out.mkdir(parents=True,exist_ok=False);rows=[];start=time.perf_counter();spec=load(path)
    baseline={c['id']:c['reports'][1]for c in json.loads(gzip.decompress((ROOT/'reports/font-capture-v3/result.json.gz').read_bytes()))['cases']}if regression else{}
    for c in spec['cases']:
        artifacts=[];reports=[];checks=[]
        def check(name,test):checks.append(dict(check=name,passed=bool(test)))
        for reference in ([False]if regression or real else[True,False,False]):
            a,p=invoke(path,c,reference);artifacts.append(a);reports.append(p);check('bounded-structured-result',p is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures'])
        p=reports[0]if regression or real else reports[1]
        if p is not None:
            check('limits-and-permissions',all(r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())and not r['game_started']and not r['full_trace_enabled']for r in reports if r))
            if c.get('kind')=='process-rejection':check('specific-process-refusal',all(a['returncode']==1 and c['error']in r.get('first_unsupported_entry','')for a,r in zip(artifacts,reports)if r))
            else:check('completed',all(a['returncode']==0 and r is not None and'semantic'in r for a,r in zip(artifacts,reports)))
            if regression:
                b=baseline[c['id']];check('old-state-and-evidence-preserved',all(p.get(k)==b.get(k)for k in ['semantic','steps','first_unsupported_entry']))
            elif'semantic'in p:
                if not real:
                    ordinary=lambda r:[{k:v for k,v in step.items()if k!='metadata'}for step in r['steps']];check('stock-ordinary-results',all(r.get('semantic')==p['semantic']and ordinary(r)==ordinary(p)for r in reports if r));check('private-state-and-evidence-repeat',reports[2].get('semantic')==p['semantic']and reports[2].get('steps')==p['steps'])
                frames=[step['draws']for step in p['steps']if'draws'in step]
                if'frames'in c:check('exact-frame-contents',[[bytes.fromhex(d['text_hex']).decode()for d in frame]for frame in frames]==c['frames'])
                if'positions'in c:check('private-ui-positions',[frame[0]['x']for frame in frames]==c['positions'])
                if'values'in c:check('exact-return-values',[s['values']for s in p['steps']if'values'in s][-1]==c['values'])
                if'value_rows'in c:check('all-role-return-values',[s['values']for s in p['steps']if'values'in s]==c['value_rows'])
                if'valid'in c:check('precise-invalidations',[s['metadata']['versions_valid']for s in p['steps']if'metadata'in s and'versions_valid'in s['metadata']]==c['valid'])
                if'coins'in c:check('authority-once',p['semantic']['world']['coins']==c['coins']and len(p['semantic']['world']['effects'])==1)
                if c.get('stable_updates'):
                    clocks=p['steps'][-2]['clocks'];states=p['steps'][-1]['states'];check('fixed-live-clock-and-operation-storage',len(clocks)==1 and clocks[0]['updates']==c['stable_updates']and len(states[0]['commands'])==2 and p['steps'][-2]['metadata']['per_update_journal_records']==0)
                if'live'in c:check('clock-gc-reclaimed',len(p['semantic']['sprite_clocks'][1])==c['live']and p['steps'][-1]['metadata']['retired']==c['retired'])
                if c.get('restored'):check('config-and-clock-recovered',json.loads(bytes.fromhex(p['semantic']['mod_stores'][1]['mods/ui-flow-fixture']['data_hex']))==dict(amount=2,language='zh',x=147)and p['steps'][-1]['clocks'][0]['updates']==2)
                if c.get('kind')=='expected-rejection':check('rejected-case-never-wrote-world',p['semantic']['world']['coins']==0 and not p['semantic']['world']['effects'])
                check('native-equivalence-not-claimed',all(not m['ui_flow']['native_update_equivalence_verified']and not m['ui_flow']['non_loop_terminal_supported']for m in p['metadata']))
        row=dict(id=c['id'],kind=c.get('kind'),passed=all(x['passed']for x in checks),checks=checks,reports=reports,artifacts=artifacts);rows.append(row);print(json.dumps(dict(id=c['id'],passed=row['passed'],failure=(p or{}).get('first_unsupported_entry'),failed_checks=[x['check']for x in checks if not x['passed']])),flush=True)
    assert before==parent.protection.protection();result=dict(schema='ui-flow-results-1',manifest_sha256=digest(path),binaries={p.relative_to(ROOT).as_posix():digest(p)for p in[EXE,REF]},driver_sha256=digest(Path(__file__)),cases=rows,passed=all(x['passed']for x in rows),work_limit=10000000,child_timeout_seconds=5,protected_files_unchanged=True,seconds=time.perf_counter()-start,rendering_verified=False,authority_projection_passed=False,playable=False,game_started=False)
    raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((out/'result.json.gz').read_bytes())==raw;print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows),seconds=result['seconds'])));return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real','regressions']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(parent.MANIFEST if a.phase=='regressions'else REAL if a.phase=='real'else MANIFEST,a.output.resolve(),a.phase=='real',a.phase=='regressions')else 1)
