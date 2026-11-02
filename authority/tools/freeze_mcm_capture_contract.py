"""Freeze source evidence and executable API probes; this does not grant menu purpose."""
import copy,hashlib,json,re,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as world
ROOT=world.ROOT;DIR=ROOT/'research/menu_capture'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=ROOT/'research/menu_environment/pristine_modconfig.lua';raw=source.read_bytes();assert sha(source)=='19a0366d7db6faae98a94dd46c5111f5ec4e5d4dc1bc456cb7fd3cacac3ffaf2';lines=raw.decode('utf-8').splitlines()
    needles=['function ModConfigMenu.AddSetting(', 'optionCurrent()', 'optionOnChange(', 'textToDraw = optionDisplay(', 'numberToShow = optionDisplay(', 'function ModConfigMenu.ConvertDisplayToTextTable(', 'displayValue = displayValue()']
    sites={needle:[dict(line=i+1,line_sha256=hashlib.sha256(line.encode('utf-8')).hexdigest(),text=line.strip())for i,line in enumerate(lines)if needle in line]for needle in needles};assert all(sites.values())
    contract=dict(schema='frozen-mcm-capture-contract-1',source=source.relative_to(ROOT).as_posix(),source_sha256=sha(source),locations_are_diagnostic_only=True,runtime_purpose_enforcement_implemented=False,required_identity=['frozen framework source','actual function prototype','actual registered setting object','actual consumer call instruction'],source_sites=sites,api=dict(AddSetting=dict(forms=['category, setting','category, subcategory, setting'],nil_subcategory='Uncategorized',returns='original setting table'),CurrentSetting=dict(args=[],returns='Lua value; preserve false and nil'),OnChange=dict(args=['selected value'],returns='preserve callback return behavior'),Display=dict(args=['cursorIsAtThisOption','configMenuInOptions','lastOptionPos']),translation='DisplayTranslate or Display; InfoTranslate or Info',Info=dict(consumed_by='ConvertDisplayToTextTable',callback_args=[])))
    world.parent.f.freeze_json(DIR/'mcm-contract-v1.json',contract)
    base=copy.deepcopy(world.parent.f.load(ROOT/'research/sparse_value/real-init-v1.json')['cases'][0]);cases=[]
    probes=[
      ('actual-addsetting-two-argument-original-table',"local s={Type=ModConfigMenu.OptionType.NUMBER};local r=ModConfigMenu.AddSetting('Contract Probe',s);local id=ModConfigMenu.GetCategoryIDByName('Contract Probe');local a=ModConfigMenu.MenuData[id].Subcategories[1];return r==s,a.Name,#a.Options,a.Options[1]==s",[True,'Uncategorized',1,True]),
      ('actual-addsetting-nil-subcategory-original-table',"local s={Type=ModConfigMenu.OptionType.NUMBER};local r=ModConfigMenu.AddSetting('Contract Probe',nil,s);local id=ModConfigMenu.GetCategoryIDByName('Contract Probe');return r==s,ModConfigMenu.MenuData[id].Subcategories[1].Name",[True,'Uncategorized']),
      ('actual-setting-callbacks-preserve-args-and-false-nil',"local changed;local current=function()return false end;local s={Type=ModConfigMenu.OptionType.NUMBER,CurrentSetting=current,OnChange=function(v)changed=v;return 'sentinel'end,Display=function(a,b,p)return tostring(a)..'|'..tostring(b)..'|'..p.X end,Info=function()return nil end};ModConfigMenu.AddSetting('Contract Probe','Sub',s);return s.CurrentSetting==current,select('#',s.CurrentSetting()),s.CurrentSetting(),s.OnChange(2),changed,s.Display(true,false,Vector(3,4)),select('#',s.Info()),s.Info()",[True,1,False,'sentinel',2,'true|false|3.0',1,None]),
      ('actual-addsetting-retains-original-errors',"local a,e=pcall(ModConfigMenu.AddSetting,{},{});local b,f=pcall(ModConfigMenu.AddSetting,'Contract Probe',{},{});return a,tostring(e):find('No valid category name provided',1,true)~=nil,b,tostring(f):find('No valid subcategory name provided',1,true)~=nil",[False,True,False,True]),
    ]
    for id,code,expected in probes:
        c=copy.deepcopy(base);c.update(id=id,steps=[world.ev(code)],values=world.values(*expected));cases.append(c)
    world.parent.f.freeze_json(DIR/'contracts-v1.json',dict(schema='mcm-api-capture-probes-1',work_limit=10000000,timeout_seconds=5,cases=cases));print(json.dumps(dict(source_verified=True,contract_cases=len(cases),trusted_menu_purpose_implemented=False)))
if __name__=='__main__':main()
