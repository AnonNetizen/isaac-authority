"""Freeze API registration expectations from the actual MCM source contract."""
import argparse, json
from pathlib import Path
from start_slice3_ui import digest
ROOT=Path(__file__).resolve().parents[1]
def result(value):
    if isinstance(value,str):return {'t':'string','hex':value.encode().hex()}
    if isinstance(value,bool):return {'t':'boolean','v':value}
    if isinstance(value,int):return {'t':'integer','v':value}
    if value is None:return {'t':'nil'}
    raise TypeError(value)
def check(name,code,values):return {'id':name,'code':code,'expected':[result(v) for v in values]}
def freeze(version):
    inputs=json.loads((ROOT/'research/slice3_ui_inputs.json').read_text())
    checks=[
        check('two-arg-return-identity',"local s={Type=ModConfigMenu.OptionType.NUMBER,CurrentSetting=2,Display='value'};local r=ModConfigMenu.AddSetting('Contract Two Arg',s);return rawequal(s,r),ModConfigMenu.GetSubcategoryIDByName('Contract Two Arg','Uncategorized')~=nil",[True,True]),
        check('nil-subcategory-false',"local s={Type=ModConfigMenu.OptionType.BOOLEAN,CurrentSetting=false,Display=function()return false end};local r=ModConfigMenu.AddSetting('Contract Nil',nil,s);return rawequal(s,r),r.CurrentSetting,r.Display()",[True,False,False]),
        check('function-false-and-change',"local n=false;local s={Type=ModConfigMenu.OptionType.BOOLEAN,CurrentSetting=function()return n end,OnChange=function(v)n=v;return false end,Display=function(selected,options,pos)return tostring(selected)..'|'..tostring(options)..'|'..pos.X end};local r=ModConfigMenu.AddSetting('Contract Function','Values',s);local before=r.CurrentSetting();local ret=r.OnChange(true);return before,ret,r.CurrentSetting(),r.Display(false,true,Vector(17,23))",[False,False,True,'false|true|17']),
        check('numeric-category-identity',"local s={CurrentSetting=3};local id=ModConfigMenu.GetCategoryIDByName('Contract Two Arg');return rawequal(ModConfigMenu.AddSetting(id,nil,s),s)",[True]),
        check('invalid-category-error',"local ok,e=pcall(ModConfigMenu.AddSetting,false,{});return ok,string.find(e,'No valid category name provided',1,true)~=nil",[False,True]),
        check('bytes-and-alias',"local s={Display=function()return string.char(97,0,255)end};local r=ModConfigMenu.AddSetting('Contract Bytes',s);return rawequal(s,r),#r.Display(),string.byte(r.Display(),1,3)",[True,3,97,0,255]),
        check('userdata-field-alias',"local v=Vector(2,3);local a=v;a.X=7;local sum=v+Vector(1,2);return type(v),rawequal(a,v),v.X,sum.X,sum.Y",['userdata',True,7,8,5]),
    ]
    cases=[]
    for label,mods in [('mcm',[inputs['mods'][0]]),('eid',[inputs['mods'][1]]),('combined',inputs['mods'])]:
        for lang in ('zh','en'):
            cases.append({'id':label+'-'+lang,'mods':mods,'options':{'Language':lang,'HUDOffset':0.2 if lang=='zh' else 0.6},'checks':checks if label!='eid' else [check('real-eid-language',"return EID:getLanguage()",['zh_cn' if lang=='zh' else 'en_us'])]})
    if version>=4:
        resources=json.loads((ROOT/'research/slice3_ui_resources.json').read_text())
        font=next(x for x in resources['resources'] if x['kind']=='font' and 'eid_default.fnt' in x['path'])
        metrics=font['metrics'];width=sum(metrics['advances'][str(ord(c))] for c in 'AB')+metrics['kerning'].get('65:66',0)
        object_checks=[
            check('vector-alias-and-cached-method',"local v=Vector(3,4);local alias=v;local length=v.Length;alias.X=0;return type(v),rawequal(v,alias),length(v),v.Y",['userdata',True,4,4]),
            check('independent-color-fields',"local c=KColor(1,0.5,0.25,0.75);c.Red=0.125;return c.Red,c.Green,c.Blue,c.Alpha",[]),
            check('field-upvalue-and-string-bytes',"local v=Vector(7,8);local function f()return v.X end;v.Y=99;return f(),v.Y,string.char(0,255)",[7,99]),
            check('actual-font-metrics',"local f=Font();f:Load('font/eid_default.fnt');local width=f.GetStringWidthUTF8;return f:IsLoaded(),width(f,'AB')",[True,width]),
        ]
        object_checks[1]['expected']=[{'t':'number','v':v} for v in (0.125,0.5,0.25,0.75)]
        object_checks[2]['expected'].append({'t':'string','hex':'00ff'})
        if version>=5:
            # sqrt returns a Lua float, even when its value is integral.
            # Keep v4's erroneous oracle frozen; do not change the API result.
            object_checks[0]['expected'][2]={'t':'number','v':4.0}
            if version==5:
                object_checks.append(check('explicit-unknown-object-error',"local v=Vector(1,2);local ok,e=pcall(function()return v.UnregisteredMethod end);return ok,string.find(e,'Vector.UnregisteredMethod',1,true)~=nil",[False,True]))
                object_checks.append(check('resource-failure-preserves-object',"local f=Font();local ok,e=pcall(function()f:Load('font/not-registered.fnt')end);return ok,f:IsLoaded(),string.find(e,'Unsupported frozen UI resource',1,true)~=nil",[False,False,True]))
        cases.append({'id':'registered-object-baseline','mods':[],'load_enums':False,'options':{'Language':'en','HUDOffset':0.6},'checks':object_checks})
        if version>=6:
            for name,code,error in (
                ('unknown-object-refusal','return Vector(1,2).UnregisteredMethod','Vector.UnregisteredMethod'),
                ('missing-resource-refusal',"local f=Font();f:Load('font/not-registered.fnt')",'Unsupported frozen UI resource'),
            ):
                cases.append({'id':name,'case_kind':'safety','mods':[],'load_enums':False,
                    'options':{'Language':'en',**({'HUDOffset':0.6} if version>=7 else {})},'expected_unsupported':error,'checks':[check(name,code,[])]})
    manifest={'schema':'isaac-slice3-ui-suite-1','mode':'slice3-ui','view_rule':'personal-settings-authority-hud-v1',
        'purpose':'Stage 1 actual-source initialization and registration contracts; rendering remains unverified',
        'bootstrap_sha256':digest(ROOT/'research/slice3_ui_context.lua'),
        'enums_sha256':inputs['scripts']['resources/scripts/enums.lua'],
        'resources_sha256':digest(ROOT/'research/slice3_ui_resources.json'),
        'cases':cases,'limits':{'paths':32,'unresolved_conditions':8,'exploration_work':2000000}}
    out=ROOT/('research/slice3_ui_contract_suite'+('' if version==1 else '_v'+str(version))+'.json')
    if out.exists():raise ValueError('Refusing to change frozen suite; use a new version')
    out.write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'cases':len(cases),'sha256':digest(out)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',type=int,default=1);freeze(p.parse_args().version)
