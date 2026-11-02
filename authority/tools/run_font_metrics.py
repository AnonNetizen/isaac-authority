"""Bounded real-font parsing/query contracts; no actual drawing or game process."""
import argparse,copy,gzip,json,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import run_callback_framework as c
import freeze_font_metrics as freeze_fonts
import bounded_font_process
ROOT=c.ROOT;old=c.old;FOLDER=ROOT/'research/font_metrics';PROFILE=FOLDER/'profile.json';MANIFEST=ROOT/'research/font_metrics_v1.json';CURRENT=ROOT/'research/font_metrics_v2.json';TRANSPORT=ROOT/'research/font_metrics_transport_v1.json';REAL=ROOT/'research/font_metrics_real_v1.json'
EXE=ROOT/'build-font-metrics/Release/authority-fonts.exe';REF=EXE.with_name('authority-fonts-reference.exe');EID='font/eid_default.fnt';MCM='mcm_cn_font/pftempestasevencondensed.fnt';BOLD='mcm_cn_font/teammeatfont16bold.fnt'

def freeze():
    profile=c.t.s.e.v.s.o.load(PROFILE);game=Path(profile['game_root']);font_by_alias={alias:a for a in profile['fonts']for alias in a['aliases']};data={a['path']:freeze_fonts.metrics((game/a['path']).read_bytes())[1]for a in profile['fonts']}
    missing=next(i for i in range(256,65536)if not 0xd800<=i<=0xdfff and all(i not in glyphs for glyphs in data.values()));missing_bytes=chr(missing).encode('utf-8');missing_lua='string.char('+','.join(map(str,missing_bytes))+')'
    code="""FontMod=RegisterMod('Font Metrics Fixture',1)
local cfg=require('json').decode(FontMod:LoadData())
Tex=Sprite();Tex:Load('gfx/ui/modconfig/menu.anm2',false);Tex:SetFrame('Cursor',4)
F=Font();F:Load('font/eid_default.fnt','');F:SetMissingCharacter(2)
FontMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
FontMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;FontMod:SaveData(require('json').encode(cfg));F:Load('mcm_cn_font/pftempestasevencondensed.fnt')end
 if Input.IsButtonTriggered('fail')then cfg.x=999;FontMod:SaveData('not committed');F:Load('mcm_cn_font/teammeatfont16bold.fnt');Isaac.RenderText('unpublished',0,0);error('font-injected')end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|width='..F:GetStringWidthUTF8('native bridge'),cfg.x,0)
end)
FontMod:AddCallback(3,function()Isaac.RenderText(tostring(F:GetStringWidth('AB')),0,0)end)
FontMod:AddCallback(4,function()Isaac.RenderText(tostring(F:IsLoaded()),0,0)end)
FontMod:AddCallback(5,function()Isaac.RenderText(tostring(F:GetStringWidth(MISSING)),0,0)end)
""".replace('MISSING',missing_lua)
    source=FOLDER/'main.lua';c.t.s.e.v.s.o.freeze_file(source,code.encode());rr=dict(root=FOLDER.relative_to(ROOT).as_posix(),display='mods/font-metrics-fixture',sha256={'main.lua':old.digest(source)})
    base=copy.deepcopy(c.t.s.e.v.s.o.load(c.t.MANIFEST)['cases'][0]);base={k:v for k,v in base.items()if k in ['objects','value_objects','engine_services','animation_profile','graphics_profile','stores']}
    base.update(source=source.relative_to(ROOT).as_posix(),source_sha256=old.digest(source),modules=dict(entry=0,roots=[rr]),mod_sdk=c.t.s.e.v.s.profile([rr],[{rr['display']:old.store(1,17,'en')},{rr['display']:old.store(2,137,'zh')}],[0]),font_profile=dict(path=PROFILE.relative_to(ROOT).as_posix(),sha256=old.digest(PROFILE)))
    cases=[]
    def ev(code,**kw):return dict(op='evaluate',code=code,**kw)
    def dispatch(**buttons):return dict(op='dispatch',event=2,phase='presentation',input=buttons)
    def cap(event):return dict(op='capture_reads',event=event,phase='presentation')
    def status(event):return dict(op='consumer_status',consumer=event)
    def case(id,steps,values=None,kind='functional',**kw):
        x=copy.deepcopy(base);x.update(id=id,steps=steps,kind=kind,**kw)
        if values is not None:x['expected_values']=c.t.s.e.v.values(*values)
        cases.append(x);return x
    for index,a in enumerate(profile['fonts']):
        alias=a['aliases'][0];m=a['metrics'];case('actual-font-'+str(index),[ev("F:Load("+json.dumps(alias)+");local width=F.GetStringWidthUTF8;return F:IsLoaded(),width(F,'native bridge'),F:GetLineHeight(),F:GetBaselineHeight()")],[True,a['canonical_width'],m['line_height'],m['baseline']],resource=a['path'],native_control=a['native_canonical_width'])
    case('absolute-load-path',[ev('F:Load('+json.dumps((game/font_by_alias[MCM]['path']).as_posix())+");return F:GetStringWidth('native bridge')")],[67],resource=font_by_alias[MCM]['path'])
    case('source-file-legacy-normalization',[ev("F:Load('mods/mod_config_menu_cn_2494192799/scripts/modconfig.lua/../../resources/mcm_cn_font/pftempestasevencondensed.fnt');return F:GetStringWidth('native bridge')")],[67])
    case('windows-case-and-slashes',[ev("F:Load('MCM_CN_FONT\\\\PFTEMPESTASEVENCONDENSED.FNT');return F:GetStringWidth('native bridge')")],[67])
    case('empty-compatibility-argument',[ev("F:Load('"+EID+"','');return F:IsLoaded()")],[True])
    case('empty-string-width',[ev("return F:GetStringWidth('')")],[0])
    chinese='中文AB';width=sum(data[font_by_alias[EID]['path']][ord(ch)]for ch in chinese)
    case('actual-utf8-glyphs',[ev('return F:GetStringWidthUTF8('+json.dumps(chinese,ensure_ascii=False)+')')],[width])
    case('cached-methods',[ev("local load,width=F.Load,F.GetStringWidth;load(F,'"+MCM+"');return width(F,'native bridge')")],[67])
    case('explicit-missing-character',[ev('return F:GetStringWidth('+missing_lua+')')],[data[font_by_alias[EID]['path']][2]])
    case('explicit-question-mark-fallback',[ev('F:SetMissingCharacter(63);return F:GetStringWidth('+missing_lua+')')],[data[font_by_alias[EID]['path']][63]])
    case('known-glyph-read-ignores-fallback-write',[cap(3),ev('F:SetMissingCharacter(63)'),status(3)],valid=[True])
    case('missing-glyph-read-invalidates',[cap(5),ev('F:SetMissingCharacter(63)'),status(5)],valid=[False])
    case('missing-character-aba',[cap(5),ev('F:SetMissingCharacter(63);F:SetMissingCharacter(2)'),status(5)],valid=[False])
    case('resource-reload-invalidates',[cap(3),ev("F:Load('"+EID+"')"),status(3)],valid=[False])
    case('unload-invalidates-loaded-read',[cap(4),ev('F:Unload()'),status(4)],valid=[False],loaded=False)
    case('unloaded-constructor',[ev('local f=Font();return f:IsLoaded()')],[False])
    case('unload-and-reload',[ev("F:Unload();local a=F:IsLoaded();F:Load('"+EID+"');return a,F:IsLoaded(),F:GetStringWidth('native bridge')")],[False,True,65])
    case('independent-settings-and-fonts',[dict(dispatch(),role='host'),dispatch(move=True),dict(dispatch(),role='host')],frames=[['en|x=17|coins=0|width=65'],['zh|x=147|coins=0|width=67'],['en|x=17|coins=0|width=65']],independent_resources=[font_by_alias[EID]['path'],font_by_alias[MCM]['path']])
    case('authority-once-personal-font',[dict(op='dispatch',event=1,phase='authority',role='host'),dispatch(move=True)],expected_coins=1,frames=[['zh|x=147|coins=1|width=67']])
    case('saved-configuration-reload',[dispatch(move=True),dict(op='reload_saved'),dispatch()],frames=[['zh|x=147|coins=0|width=67'],['zh|x=147|coins=0|width=65']])
    case('rollback-save-font-and-draw',[dispatch(move=True),dict(dispatch(move=True,fail=True),expect_error='font-injected'),dispatch()],frames=[['zh|x=147|coins=0|width=67'],['zh|x=147|coins=0|width=67']],resource=font_by_alias[MCM]['path'])
    case('gc-retires-font-state',[ev('for i=1,128 do local f=Font();if i%16==0 then collectgarbage("collect")end end;collectgarbage("collect")'),dict(op='font_state')],live=1)
    case('shared-assets-no-reparse',[ev("for i=1,32 do F:Load('"+EID+"');F:GetStringWidth('AB')end")],cached=True)
    for id,code,error in [
      ('unknown-resource',"F:Load('font/not-registered.fnt')",'Unregistered Font resource'),
      ('outside-root',"F:Load('C:/outside/font.fnt')",'Unregistered Font resource'),
      ('missing-font-query',"Font():GetStringWidth('AB')",'Font resource not loaded'),
      ('nonempty-compatibility',"F:Load('"+EID+"','unknown')",'Only empty Font.Load compatibility argument verified'),
      ('missing-character-range','F:SetMissingCharacter(65536)','Unverified missing character range'),
      ('unknown-default-fallback',"F:Load('"+EID+"');F:GetStringWidth("+missing_lua+')','Font default missing glyph behavior unverified'),
      ('missing-fallback-glyph',"F:Load('"+MCM+"');F:SetMissingCharacter(2);F:GetStringWidth("+missing_lua+')','Configured missing Font glyph unavailable'),
      ('invalid-utf8',"F:GetStringWidth(string.char(192,128))",'Invalid Font UTF-8'),
      ('surrogate',"F:GetStringWidth(string.char(237,160,128))",'Invalid Font UTF-8'),
      ('supplementary',"F:GetStringWidth(string.char(240,159,152,128))",'Font UTF-16 surrogate behavior unverified'),
      ('embedded-nul',"F:GetStringWidth('A'..string.char(0)..'B')",'Font control character behavior unverified'),
      ('multiline',"F:GetStringWidth('A\\nB')",'Font control character behavior unverified'),
      ('foreign-receiver',"F.GetStringWidth(Tex,'AB')",'Foreign or retired Font receiver'),
      ('nil-text','F:GetStringWidth(nil)','Expected string'),
      ('property-write','F.unknown=1','Font properties are read-only'),
      ('draw-unimplemented',"F:DrawString('text',0,0,KColor(1,1,1,1))",'Font.DrawString capture not implemented'),
      ('unknown-method','F:SomethingUnknown()','Font.SomethingUnknown contract not implemented')]:
        case('reject-'+id,[ev(code,expect_error=error),dispatch()],kind='expected-rejection',frames=[['zh|x=137|coins=0|width=65']],resource=font_by_alias[EID]['path'])
    case('reject-text-cap',[ev("F:GetStringWidth(string.rep('a',65537))",expect_error='Font argument byte capacity exceeded')],kind='expected-rejection')
    case('reject-live-font-cap',[ev('held={};for i=1,1025 do held[i]=Font()end')],kind='process-rejection',error='Live Font capacity exceeded')
    for id,change,error,initial in [
      ('file-hash',lambda a:a['files'][0].update(sha256='0'*64),'Font dependency hash mismatch',False),
      ('file-size',lambda a:a['files'][0].update(bytes=a['files'][0]['bytes']+1),'Font dependency size mismatch',False),
      ('page-hash',lambda a:a['files'][1].update(sha256='0'*64),'Font dependency hash mismatch',False),
      ('metric-signature',lambda a:a['metrics'].update(metrics_sha256='0'*64),'Font metric signature mismatch',False),
      ('missing-page',lambda a:a['files'].pop(),'Font page dependency coverage mismatch',True)]:
        bad=copy.deepcopy(profile);a=next(a for a in bad['fonts']if a['path']==font_by_alias[MCM]['path']);change(a);path=FOLDER/(id+'.json');c.t.s.e.v.s.o.freeze_json(path,bad)
        x=case('reject-'+id,[]if initial else[ev("F:Load('"+MCM+"')",expect_error=error),dispatch()],kind='process-rejection'if initial else'expected-rejection',error=error,**({}if initial else dict(frames=[['zh|x=137|coins=0|width=65']],resource=font_by_alias[EID]['path'])))
        x['font_profile']=dict(path=path.relative_to(ROOT).as_posix(),sha256=old.digest(path))
    c.t.s.e.v.s.o.freeze_json(MANIFEST,dict(schema='font-metrics-contracts-1',work_limit=10000000,timeout_seconds=5,cases=cases))
    real=copy.deepcopy(c.t.s.e.v.s.o.load(c.REAL))
    for x in real['cases']:x['font_profile']=copy.deepcopy(base['font_profile'])
    real['schema']='font-metrics-real-entry-1';c.t.s.e.v.s.o.freeze_json(REAL,real);print(json.dumps(dict(frozen=True,cases=len(cases),missing_codepoint=missing)))

def freeze_channels():
    data=copy.deepcopy(c.t.s.e.v.s.o.load(MANIFEST));base=copy.deepcopy(data['cases'][0]);base.pop('native_control',None);base.pop('resource',None)
    for id,code,expected in [
      ('plain-print-channel',"print('font status',true,nil,12);return F:GetStringWidth('AB')",b'font status\ttrue\tnil\t12\r\n'),
      ('metamethod-print-channel',"print(setmetatable({},{__tostring=function()return 'font-table'end}));return F:GetStringWidth('AB')",b'font-table\r\n'),
      ('raw-print-bytes',"print(string.char(0,255));return F:GetStringWidth('AB')",b'\0\xff\r\n')]:
        x=copy.deepcopy(base);x.update(id=id,steps=[dict(op='evaluate',code=code)],expected_values=c.t.s.e.v.values(10),diagnostic_hex=expected.hex());data['cases'].append(x)
    x=copy.deepcopy(base);x.update(id='reject-native-report-cap',steps=[dict(op='evaluate',code="FontMod:SaveData(string.rep('x',1048576))")],kind='process-rejection',error='CLI report capacity exceeded');x.pop('expected_values',None);data['cases'].append(x)
    data['schema']='font-metrics-contracts-2';c.t.s.e.v.s.o.freeze_json(CURRENT,data)
    x=copy.deepcopy(base);x.update(id='diagnostic-output-cap',steps=[dict(op='evaluate',code="print(string.rep('x',262145))")]);x.pop('expected_values',None)
    c.t.s.e.v.s.o.freeze_json(TRANSPORT,dict(schema='font-transport-supervision-1',work_limit=10000000,timeout_seconds=5,cases=[x]));print(json.dumps(dict(channel_cases=len(data['cases']),transport_cases=1)))

def invoke(path,case,reference=False):
    p=bounded_font_process.run([str(REF if reference else EXE),'--font-suite',str(ROOT),str(path),case['id'],'reference'if reference else'boundary'])
    try:r=json.loads(p['stdout'])if not p['timed_out']and not p['output_limit_exceeded']and not p['reader_failures']else None
    except ValueError:r=None
    return dict(returncode=-9 if p['timed_out']else p['returncode'],seconds=p['seconds'],stderr=p['stderr'].decode('utf-8',errors='replace'),stderr_hex=p['stderr'].hex(),output_limit_exceeded=p['output_limit_exceeded'],reader_failures=p['reader_failures'],invalid_stdout=p['stdout'][-4096:].decode('utf-8',errors='replace')if r is None else None),r
def setup():c.EXE=EXE;c.REF=REF;c.invoke=invoke;c.setup()
def run(path,out,real=False):
    setup();r=c.run(path,out,real);cases={x['id']:x for x in c.t.s.e.v.s.o.load(path)['cases']}
    for row in r['cases']:
        case=cases[row['id']];p=row['reports'][1]
        def check(name,value):row['checks'].append(dict(check=name,passed=bool(value)))
        if'diagnostic_hex'in case:check('diagnostic-bytes-separated',all(a['stderr_hex']==case['diagnostic_hex']for a in row['artifacts']))
        if p and'semantic'in p and'font_profile'in case:
            states=p['semantic']['font_states'];s=states[1][0]
            if 'resource'in case:check('font-resource-exact',s['resource']==case['resource'])
            if 'loaded'in case:check('font-unloaded',bool(s['resource'])==case['loaded'])
            if 'live'in case:check('font-retired-state',len(states[1])==case['live'])
            if case.get('independent_resources'):check('role-fonts-independent',[x[0]['resource']for x in states]==case['independent_resources'])
            if 'valid'in case:check('precise-font-consumer-versions',[x['metadata']['versions_valid']for x in p['steps']if'metadata'in x and'versions_valid'in x['metadata']]==case['valid'])
            if case.get('cached'):
                cache=p['metadata'][1]['font_metrics']['resource_cache'];check('font-index-parsed-once',cache['fonts_parsed']==1 and cache['asset_cache_hits']>=32)
            check('repeated-font-state',all(x['semantic']['font_states']==states for x in row['reports']))
        row['passed']=all(x['passed']for x in row['checks'])
    r['passed']=len(r['cases'])==len(cases)and all(x['passed']for x in r['cases']);r['schema']='font-metrics-results-1';r['font_driver_sha256']=old.digest(Path(__file__))
    raw=(json.dumps(r,separators=(',',':'))+'\n').encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));print(json.dumps(dict(font_finished=True,passed=r['passed'],cases=len(r['cases']),failures=[dict(id=x['id'],checks=[q['check']for q in x['checks']if not q['passed']])for x in r['cases']if not x['passed']])),flush=True);return r

def transport(out):
    out.mkdir(parents=True,exist_ok=False);case=c.t.s.e.v.s.o.load(TRANSPORT)['cases'][0];rows=[]
    for reference in [True,False,False]:
        p=bounded_font_process.run([str(REF if reference else EXE),'--font-suite',str(ROOT),str(TRANSPORT),case['id'],'reference'if reference else'boundary']);row={k:v for k,v in p.items()if k not in ['stdout','stderr']};row.update(stdout_bytes=len(p['stdout']),stderr_bytes=len(p['stderr']),passed=p['output_limit_exceeded']and not p['timed_out']and not p['reader_failures']and len(p['stdout'])<=bounded_font_process.REPORT_LIMIT and len(p['stderr'])<=bounded_font_process.DIAGNOSTIC_LIMIT);rows.append(row)
    result=dict(schema='font-transport-supervision-results-1',passed=all(r['passed']for r in rows),reports=rows,binary_sha256=old.digest(EXE),reference_sha256=old.digest(REF),supervisor_sha256=old.digest(Path(bounded_font_process.__file__)),report_limit=bounded_font_process.REPORT_LIMIT,diagnostic_limit=bounded_font_process.DIAGNOSTIC_LIMIT,child_timeout_seconds=5)
    raw=json.dumps(result,separators=(',',':')).encode();(out/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));print(json.dumps(result));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','real','callbacks','transport']);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.phase=='freeze':freeze();freeze_channels()
    elif a.phase=='transport':sys.exit(0 if transport(a.output.resolve())['passed']else 1)
    else:sys.exit(0 if run(REAL if a.phase=='real'else c.CURRENT if a.phase=='callbacks'else CURRENT,a.output.resolve(),a.phase=='real')['passed']else 1)
