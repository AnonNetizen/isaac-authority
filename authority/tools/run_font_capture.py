"""Bounded tests of captured native font arguments and real frozen EID code."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_font_metrics as old
import bounded_font_process
import measure_font_uncapped as protection
ROOT=old.ROOT;FOLDER=ROOT/'research/font_capture';PROFILE=FOLDER/'profile.json'
MANIFEST=ROOT/'research/font_capture_v2.json';REAL=ROOT/'research/font_capture_real_v1.json';PROBES=ROOT/'research/font_capture_probes_v1.json'
EXE=ROOT/'build-font-capture/Release/authority-font-capture.exe';REF=EXE.with_name('authority-font-capture-reference.exe')

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def frozen(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert p.read_bytes()==data,'Frozen input differs: '+str(p)
    else:p.write_bytes(data)
def freeze_json(p,data):frozen(p,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())
def values(*items):
    return [dict(type='nil')if x is None else dict(type='boolean',value=x)if type(x)==bool else dict(type='integer',value=x)if type(x)==int else dict(type='number',value=x)if type(x)==float else dict(type='string',hex=x.encode().hex())for x in items]
def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
def dispatch(**buttons):return dict(op='dispatch',event=2,phase='presentation',input=buttons)

def freeze():
    parent=load(old.PROFILE);main=ROOT/'research/slice3_ui_inputs/resources/scripts/main.lua';lines=main.read_bytes().splitlines(keepends=True)
    witness=ROOT/'runs/j460-final-ready/native.jsonl'
    with witness.open('rb')as stream:stream.seek(2019);raw=stream.read(7066)
    assert hashlib.sha256(raw).hexdigest()=='42c1dfe2e7b6a16f4508b0e1eb2159e0f0a08b13efebee6b61c3b87b5f3d7bb2'
    defaults=json.loads(raw)['data']['body']['commands'][12]['settings'];defaults['alignment']=None
    profile=dict(schema='frozen-font-capture-1',main_sha256=digest(main),metrics_sha256=digest(old.PROFILE),wrapper=dict(first=304,last=351,sha256=hashlib.sha256(b''.join(lines[303:351])).hexdigest()),settings_witness=dict(path=witness.relative_to(ROOT).as_posix(),offset=2019,bytes=7066,sha256=hashlib.sha256(raw).hexdigest(),command_index=12),observed_defaults=defaults,default_alignment_verified=False,default_basis='J460 legacy wrapper creates fresh settings, sets only alignment; native getters witness other five fields',api_docs=['https://wofsauge.github.io/IsaacDocs/rep/FontRenderSettings.html','https://wofsauge.github.io/IsaacDocs/rep/Font.html'])
    freeze_json(PROFILE,profile)
    code='''CaptureMod=RegisterMod('Font Capture Fixture',1)
local cfg=require('json').decode(CaptureMod:LoadData())
local count=0
F=Font();F:Load('font/eid_default.fnt');F:SetMissingCharacter(2)
S=FontRenderSettings();S:SetAlignment(0)
C=KColor(.25,.5,.75,1)
Work=function()F:DrawString(cfg.language..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|private='..count,cfg.x,23,1,1,C,S)end
CaptureMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(cfg.amount)end)
CaptureMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;count=count+1;CaptureMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('fail')then cfg.x=999;count=999;CaptureMod:SaveData('uncommitted');F:Load('font/eid_default.fnt');F:SetMissingCharacter(63);S:SetAlignment(8);C.Red=1;F:DrawString('unpublished',0,0,1,1,C,S);error('font-capture-injected')end
 Work()
end)
CaptureMod:AddCallback(3,function()Isaac.RenderText(tostring(S:GetLineHeightModifier()),0,0)end)
CaptureMod:AddCallback(4,function()Isaac.RenderText(tostring(S:GetAlignment()),0,0)end)
'''
    source=FOLDER/'main.lua';frozen(source,code.encode());base=copy.deepcopy(load(old.CURRENT)['cases'][0]);base={k:v for k,v in base.items()if k in ['objects','value_objects','engine_services','animation_profile','graphics_profile','stores','mod_sdk','font_profile']}
    root=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/font-capture-fixture',sha256={'main.lua':digest(source)})
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=digest(source),modules=dict(entry=0,roots=[root]),font_capture_profile=dict(path=PROFILE.relative_to(ROOT).as_posix(),sha256=digest(PROFILE)))
    base['mod_sdk']['stores']=[{root['display']:json.dumps(dict(amount=1,language='en',x=17),separators=(',',':'))},{root['display']:json.dumps(dict(amount=2,language='zh',x=137),separators=(',',':'))}]
    asset=next(a['path']for a in parent['fonts']if'font/eid_default.fnt'in a['aliases'])
    setting=dict(alignment=0,line_height=1.0,max_characters=65535,missing_character=4294967295,auto_wrap=False,truncation=False)
    rgba=dict(r=.25,g=.5,b=.75,a=1.0,ro=0,go=0,bo=0)
    def font(text,x=17,y=23,sx=1,sy=1,**kw):return dict(op='font',method='DrawString',asset=asset,text_hex=text.encode().hex(),x=x,y=y,sx=sx,sy=sy,color=kw.get('color',rgba),native_signature=True,settings=dict(setting,**kw.get('settings',{})))
    def default(x=137,count=0,coins=0,language='zh'):return font(language+'|coins='+str(coins)+'|private='+str(count),x)
    cases=[]
    def case(id,steps,expected=None,**kw):
        c=copy.deepcopy(base);c.update(id=id,steps=steps,kind=kw.pop('kind','functional'),**kw)
        if expected is not None:c['values']=values(*expected)
        cases.append(c);return c
    def work(code):return ev('Work=function()\n'+code+'\nend')
    def drawcase(id,body,expected,**kw):return case(id,[work(body),dispatch()],frames=[expected],**kw)
    case('known-defaults',[ev('local s=FontRenderSettings();return type(s),s:GetLineHeightModifier(),s:GetMaxCharacters(),s:GetMissingCharacterOverride(),s:IsAutoWrapEnabled(),s:IsTruncationEnabled()')],['userdata',1.0,65535,4294967295,False,False])
    case('explicit-setting-fields',[ev('S:SetAlignment(8);S:SetLineHeightModifier(1.5);S:SetMaxCharacters(12);S:SetMissingCharacterOverride(63);S:EnableAutoWrap(true);S:EnableTruncation(true);return S:GetAlignment(),S:GetLineHeightModifier(),S:GetMaxCharacters(),S:GetMissingCharacterOverride(),S:IsAutoWrapEnabled(),S:IsTruncationEnabled()')],[8,1.5,12,63,True,True])
    case('setter-void-return',[ev("return select('#',S:SetAlignment(2))")],[0])
    drawcase('modern-native-signature',"F:DrawString('modern',17,23,1,1,C,S)",[font('modern')])
    drawcase('legacy-draw-string',"F:DrawString('legacy',17,23,C)",[font('legacy')])
    drawcase('legacy-utf8',"F:DrawStringUTF8('中文',17,23,C)",[font('中文')])
    drawcase('legacy-scaled',"F:DrawStringScaled('scaled',17.5,23.25,.5,1.25,C)",[font('scaled',17.5,23.25,.5,1.25)])
    drawcase('legacy-scaled-utf8',"F:DrawStringScaledUTF8('中文',17,23,2,.5,C,0,false)",[font('中文',17,23,2,.5)])
    drawcase('legacy-center',"F:DrawString('AB',17,23,C,20,true)",[font('AB',27,settings={'alignment':1})])
    drawcase('legacy-right',"F:DrawStringUTF8('AB',17,23,C,20,false)",[font('AB',37,settings={'alignment':2})])
    case('cached-method',[ev("local fn=F.DrawString;Work=function()fn(F,'cached',17,23,1,1,C,S)end"),dispatch()],frames=[[font('cached')]])
    case('cached-legacy-method',[ev("local fn=F.DrawStringScaledUTF8;Work=function()fn(F,'cached legacy',17,23,1,1,C)end"),dispatch()],frames=[[font('cached legacy')]])
    drawcase('settings-and-color-snapshots',"F:DrawString('a',17,23,1,1,C,S);S:SetAlignment(2);C.Alpha=.5;F:DrawString('b',17,23,1,1,C,S)",[font('a'),font('b',settings={'alignment':2},color=dict(rgba,a=.5))])
    drawcase('font-state-snapshots',"F:DrawString('a',17,23,1,1,C,S);F:SetMissingCharacter(63);F:DrawString('b',17,23,1,1,C,S)",[font('a'),font('b')],missing=[2,63])
    binary=font('');binary['text_hex']='4100ffc0af'
    drawcase('raw-text-bytes',"F:DrawString(string.char(65,0,255,192,175),17,23,1,1,C,S)",[binary])
    drawcase('mixed-command-order',"Isaac.RenderText('before',1,2);F:DrawString('font',17,23,1,1,C,S);Isaac.RenderText('after',3,4)",[dict(text_hex=b'before'.hex(),x=1,y=2),font('font'),dict(text_hex=b'after'.hex(),x=3,y=4)])
    case('independent-personal-configuration',[dict(dispatch(),role='host'),dispatch(move=True),dict(dispatch(),role='host')],frames=[[default(17,language='en')],[default(147,1)],[default(17,language='en')]])
    case('authority-reward-once',[dict(op='dispatch',event=1,phase='authority',role='host'),dispatch(move=True)],frames=[[default(147,1,1)]],coins=1)
    case('save-and-reload',[dispatch(move=True),dict(op='reload_saved'),dispatch()],frames=[[default(147,1)],[default(147)]])
    case('rollback-all-updated-state',[dispatch(move=True),dict(dispatch(move=True,fail=True),expect_error='font-capture-injected'),dispatch(),dict(op='capture_state'),dict(op='font_state')],frames=[[default(147,1)],[default(147,1)]],restored=True)
    case('accepted-history-rebuild',[dispatch(move=True),dict(op='rebuild'),dispatch()],frames=[[default(147,1)],[default(147,1)]])
    case('frame-queue-reset',[dispatch()for _ in range(12)]+[dict(op='capture_state')],frames=[[default()]for _ in range(12)],frame_reset=True)
    case('gc-retires-settings',[ev('for i=1,200 do local s=FontRenderSettings();s:SetAlignment(i%9);if i%16==0 then collectgarbage("collect")end end;collectgarbage("collect")'),dict(op='capture_state')],live=1)
    case('precise-settings-read-sets',[dict(op='capture_reads',event=3,phase='presentation'),ev('S:SetAlignment(2)'),dict(op='consumer_status',consumer=1),ev('S:SetLineHeightModifier(2)'),dict(op='consumer_status',consumer=1)],valid=[True,False])
    case('settings-aba-invalidates',[dict(op='capture_reads',event=4,phase='presentation'),ev('S:SetAlignment(2);S:SetAlignment(0)'),dict(op='consumer_status',consumer=1)],valid=[False])
    # SDK callback IDs are registration IDs: event 2 is callback 2, event 3 is callback 3.
    for c in cases:
        if c['id']=='precise-settings-read-sets':
            for step in c['steps']:
                if step['op']=='consumer_status':step['consumer']=3
        if c['id']=='settings-aba-invalidates':c['steps'][-1]['consumer']=4
    case('draw-reads-settings-fields',[dict(op='capture_reads',event=2,phase='presentation'),ev('S:EnableTruncation(true)'),dict(op='consumer_status',consumer=2)],valid=[False],frames=[[default()]])
    for id,code,error in [
        ('default-alignment',"FontRenderSettings():GetAlignment()",'FontRenderSettings default alignment unverified'),
        ('unknown-setting',"S:UnknownOperation()",'FontRenderSettings.UnknownOperation contract not implemented'),
        ('property-write','S.alignment=1','FontRenderSettings properties are read-only'),
        ('alignment-range','S:SetAlignment(9)','FontRenderSettings alignment outside frozen enum'),
        ('max-range','S:SetMaxCharacters(65536)','FontRenderSettings integer range unverified'),
        ('missing-sentinel','S:SetMissingCharacterOverride(-1)','FontRenderSettings integer range unverified'),
        ('boolean-required','S:EnableAutoWrap()','FontRenderSettings setter signature unsupported'),
        ('boolean-type',"S:EnableTruncation('yes')",'FontRenderSettings explicit boolean required'),
        ('nonfinite-line','S:SetLineHeightModifier(0/0)','Nonfinite value component unsupported'),
        ('foreign-receiver','S.GetAlignment(C)','Foreign or retired FontRenderSettings receiver'),
        ('outside-render',"F:DrawString('no',0,0,1,1,C,S)",'Font draw outside presentation phase')]:
        case('reject-'+id,[ev(code,expect_error=error),dispatch()],kind='expected-rejection',frames=[[default()]])
    for id,body,error in [
        ('unknown-alignment',"local s=FontRenderSettings();F:DrawString('no',0,0,1,1,C,s)",'FontRenderSettings default alignment unverified'),
        ('foreign-settings',"F:DrawString('no',0,0,1,1,C,C)",'Foreign or retired FontRenderSettings receiver'),
        ('foreign-color',"F:DrawString('no',0,0,1,1,Color(1,1,1,1,0,0,0),S)",'Foreign or retired value receiver'),
        ('nonfinite-position',"F:DrawString('no',0/0,0,1,1,C,S)",'Nonfinite value component unsupported'),
        ('unloaded-font',"F:Unload();F:DrawString('no',0,0,1,1,C,S)",'Font resource not loaded'),
        ('count-limit',"for i=1,1025 do F:DrawString('x',0,0,1,1,C,S)end",'Captured draw frame capacity exceeded'),
        ('byte-limit',"for i=1,32 do F:DrawString(string.rep('x',32768),0,0,1,1,C,S)end",'Captured draw frame capacity exceeded')]:
        case('reject-'+id,[work(body),dict(dispatch(),expect_error=error),dispatch()],kind='expected-rejection',frames=[[default()]])
    case('reject-unproven-source-projection',[dict(op='capture_plans',event=2,phase='presentation',expect_error='Font capture source projection not implemented'),dispatch()],kind='expected-rejection',frames=[[default()]])
    case('reject-live-settings-limit',[ev('held={};for i=1,1025 do held[i]=FontRenderSettings()end')],kind='process-rejection',error='Live FontRenderSettings capacity exceeded')
    case('reject-work-limit',[ev('while true do end')],kind='process-rejection',error='Boundary work limit exceeded')
    c=case('reject-profile-hash',[],kind='process-rejection',error='Font capture profile hash mismatch');c['font_capture_profile']['sha256']='0'*64
    freeze_json(MANIFEST,dict(schema='font-capture-contracts-2',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(load(old.REAL))
    for c in real['cases']:c['font_capture_profile']=copy.deepcopy(base['font_capture_profile'])
    for original in load(old.REAL)['cases']:
        if original['id']not in['eid','combined']:continue
        c=copy.deepcopy(original);c.update(id=original['id']+'-render-string',font_capture_profile=copy.deepcopy(base['font_capture_profile']))
        c['steps']=[ev("EID:AddCallback('research.font.capture',function()EID:renderString('native bridge',Vector(17,23),Vector(1,1),KColor(.25,.5,.75,1))end)"),dict(op='dispatch',event='research.font.capture',phase='presentation')];c['frames']=[[font('native bridge')]];c['kind']='functional-real-source';real['cases'].append(c)
    real['schema']='font-capture-real-source-1';freeze_json(REAL,real)
    probes=copy.deepcopy(real);probes['cases']=[]
    for original in real['cases'][:3]:
        c=copy.deepcopy(original);c.update(id=original['id']+'-post-render',steps=[dict(op='dispatch',event=2,phase='presentation')],kind='required-function-probe');probes['cases'].append(c)
    probes['schema']='font-capture-required-probes-1';freeze_json(PROBES,probes)
    print(json.dumps(dict(frozen=True,cases=len(cases),real_cases=len(real['cases']),required_probes=3)))

def invoke(path,c,reference=False):
    p=bounded_font_process.run([str(REF if reference else EXE),'--font-capture-suite',str(ROOT),str(path),c['id'],'reference'if reference else'boundary'])
    raw=p.pop('stdout');error=p.pop('stderr');p.update(stderr_hex=error.hex(),stdout_sha256=hashlib.sha256(raw).hexdigest(),stdout_bytes=len(raw))
    try:r=json.loads(raw)if not p['timed_out']and not p['output_limit_exceeded']and not p['reader_failures']else None
    except ValueError:r=None
    if r is None:p['invalid_stdout_hex']=raw[-2048:].hex()
    return p,r

def run(path,out,regression=False,probes=False):
    before=protection.protection();spec=load(path);out.mkdir(parents=True,exist_ok=False);rows=[];start=time.perf_counter()
    baselines={c['id']:c['reports'][1]for c in json.loads(gzip.decompress((ROOT/'reports/font-metrics-v2/result.json.gz').read_bytes()))['cases']}if regression else{}
    for c in spec['cases']:
        artifacts=[];reports=[];checks=[]
        def check(name,passed):checks.append(dict(check=name,passed=bool(passed)))
        for reference in ([False]if regression or probes else[True,False,False]):
            a,r=invoke(path,c,reference);artifacts.append(a);reports.append(r)
            check('bounded-structured-result',r is not None and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures'])
        p=reports[0]if regression or probes else reports[1]
        if p is not None:
            check('limits-and-permissions',all(r['budget']['limit']==10000000 and r['budget']['used']==sum(r['budget']['categories'].values())and not r['game_started']and not r['full_trace_enabled']for r in reports if r))
            if c.get('kind')=='process-rejection':check('specific-process-rejection',all(a['returncode']==1 and c['error']in r.get('first_unsupported_entry','')for a,r in zip(artifacts,reports)if r))
            else:check('completed',all(a['returncode']==0 and r is not None and'semantic'in r for a,r in zip(artifacts,reports)))
            if regression:
                b=baselines[c['id']];check('old-functional-state-and-rejection-preserved',p.get('semantic')==b.get('semantic')and p.get('steps')==b.get('steps')and p.get('first_unsupported_entry')==b.get('first_unsupported_entry'))
            elif 'semantic'in p:
                if not probes:
                    ordinary=lambda r:[{k:v for k,v in step.items()if k!='metadata'}for step in r['steps']]
                    check('stock-and-private-ordinary-results',all(r.get('semantic')==p['semantic']and ordinary(r)==ordinary(p)for r in reports if r))
                    check('repeated-private-state-and-evidence',reports[2].get('semantic')==p['semantic']and reports[2].get('steps')==p['steps'])
                frames=[s['draws']for s in p['steps']if'draws'in s]
                if'frames'in c:
                    actual=[[{k:cmd[k]for k in expected}for cmd,expected in zip(frame,wanted)]for frame,wanted in zip(frames,c['frames'])]
                    check('exact-argument-frames',len(frames)==len(c['frames'])and all(len(x)==len(y)for x,y in zip(frames,c['frames']))and actual==c['frames'])
                if'values'in c:check('exact-return-values',[s['values']for s in p['steps']if'values'in s][-1]==c['values'])
                if'coins'in c:check('authority-world-once',p['semantic']['world']['coins']==c['coins']and len(p['semantic']['world']['effects'])==1)
                if'valid'in c:check('precise-read-invalidation',[s['metadata']['versions_valid']for s in p['steps']if'metadata'in s and'versions_valid'in s['metadata']]==c['valid'])
                if'live'in c:check('settings-reclaimed',len(p['semantic']['font_render_settings'][1])==c['live'])
                if c.get('frame_reset'):check('frame-bytes-reset',p['steps'][-1]['metadata']['frame_bytes']<2048 and len(p['semantic']['draws'][1])==1)
                if c.get('restored'):
                    check('settings-and-font-restored',p['steps'][-2]['settings'][0]['values']['alignment']==0 and p['steps'][-1]['states'][0]['resource_version']==1 and p['steps'][-1]['states'][0]['missing_character']==2)
                    saved=p['semantic']['mod_stores'][1][c['modules']['roots'][0]['display']]['data_hex'];check('personal-config-save-restored',json.loads(bytes.fromhex(saved))==dict(amount=2,language='zh',x=147))
                commands=[cmd for frame in frames for cmd in frame if cmd.get('op')=='font']
                check('captured-without-native-drawing',all(m['font_capture']['native_draw_calls']==0 and not m['font_capture']['authority_projection_proven']for m in p['metadata']))
                check('resource-and-state-proof-retained',all(len(cmd['capture_state']['resource_sha256'])==64 and cmd['capture_state']['purpose']=='unclassified'and not cmd['capture_state']['authority_projection_proven']and len(cmd['capture_state']['settings_versions'])==6 for cmd in commands))
                if'missing'in c:check('font-missing-policy-snapshots',[cmd['capture_state']['font_missing_character']for cmd in commands]==c['missing'])
        row=dict(id=c['id'],kind=c.get('kind'),passed=all(x['passed']for x in checks),checks=checks,reports=reports,artifacts=artifacts);rows.append(row)
        print(json.dumps(dict(id=c['id'],passed=row['passed'],failure=(p or{}).get('first_unsupported_entry'),failed_checks=[x['check']for x in checks if not x['passed']])),flush=True)
    assert before==protection.protection()
    result=dict(schema='font-capture-results-1',manifest=path.relative_to(ROOT).as_posix(),manifest_sha256=digest(path),binaries={p.relative_to(ROOT).as_posix():digest(p)for p in[EXE,REF]},driver_sha256=digest(Path(__file__)),passed=all(x['passed']for x in rows),cases=rows,seconds=time.perf_counter()-start,work_limit=10000000,child_timeout_seconds=5,protected_files_unchanged=True,game_started=False,authority_projection_passed=False,rendering_verified=False)
    raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress((out/'result.json.gz').read_bytes())==raw
    print(json.dumps(dict(finished=True,passed=result['passed'],cases=len(rows),seconds=result['seconds'])),flush=True);return result['passed']

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['freeze','run','real','probes','regressions']);parser.add_argument('--output',type=Path);a=parser.parse_args()
    if a.phase=='freeze':freeze()
    else:sys.exit(0 if run(old.CURRENT if a.phase=='regressions'else REAL if a.phase=='real'else PROBES if a.phase=='probes'else MANIFEST,a.output.resolve(),a.phase=='regressions',a.phase=='probes')else 1)
