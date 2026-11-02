"""Create new immutable bounded-tracking fixtures without editing older manifests."""
import argparse, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def freeze(version):
    target=ROOT/'research'/f'ui_bounded_suite_v{version}.json'
    original=json.loads((ROOT/'research/slice3_ui_contract_suite_v7.json').read_text())
    original.update(schema='isaac-ui-bounded-suite-1',mode='ui-bounded',purpose='Bounded CFG and ordinary Lua equivalence before real drawing/navigation')
    original['previous_suite_sha256']=hashlib.sha256((ROOT/'research/slice3_ui_contract_suite_v7.json').read_bytes()).hexdigest()
    original['basic_block_limit']=4096
    def case(name,code,expected=None,refusal=None,enums=False):
        item={'id':name,'mods':[],'load_enums':enums,'options':{'Language':'en','HUDOffset':0.6},'checks':[{'id':name,'code':code,'expected':expected or []}]}
        if refusal:item.update(case_kind='safety',expected_unsupported=refusal)
        return item
    def i(value):return {'t':'integer','v':value}
    def b(value):return {'t':'boolean','v':value}
    def s(value):return {'t':'string','hex':value.encode().hex()}
    original['cases'] += [
        case('j460-enums-alone','return ButtonAction.ACTION_ITEM,CollectibleType.COLLECTIBLE_SAD_ONION',[i(9),i(1)],enums=True),
        case('large-linear-function','local function f() local x=0;'+('x=x+1;'*7000)+'return x end;return f()',[i(7000)]),
        case('branch-table-closure-bytes',"local t={n=1};local a=t;local function f(flag) if flag then a.n=7 else a.n=3 end;return function() return t.n end end;local g=f(false);local v=g();g=f(true);return v,g(),string.char(0,255)..'x'",[i(3),i(7),{'t':'string','hex':'00ff78'}]),
        case('numeric-generic-loop-and-tail',"local function f(n) if n==0 then return 4 end return f(n-1) end;local sum=0;for i=1,5 do sum=sum+i end;for _,v in ipairs({3,7}) do sum=sum+v end;return sum,f(4)",[i(25),i(4)]),
        case('cached-dynamic-load',"local loader=load;local f=assert(loader('local n=...;if n>2 then return n+7 else return n-1 end'));local alias=f;return f(1),alias(3)",[i(0),i(10)]),
        case('ordinary-error-nil-false',"local ok,err=pcall(function() error('bounded sentinel',0) end);return ok,err,nil,false",[b(False),s('bounded sentinel'),{'t':'nil'},b(False)]),
        case('block-cap-refusal','local x=0;'+('if x>1 then x=x+1 end;'*1800)+'return x',refusal='basic-block limit exceeded'),
        case('no-exit-refusal','local function f() while true do end end;return true',refusal='cannot prove an exit path'),
        case('work-cap-refusal','local x=0;'+('x=x+1;'*120000)+'return x',refusal='Bounded UI work budget exceeded'),
        case('parser-cap-refusal',';'*2000050,refusal='Bounded UI work budget exceeded: parser_token'),
        case('caught-budget-cannot-resume',"local ran=false;pcall(function() load(string.rep(';',2000050)) end);ran=true;return ran",[b(True)],refusal='Bounded UI work budget exceeded: parser_token'),
    ]
    for item in original['cases']:
        # One empty framework.describe() loop plus three user iterator calls.
        if item['id']=='numeric-generic-loop-and-tail':item['required_opcode_counts']={'TFORCALL':4,'TFORLOOP':4}
    with target.open('x',encoding='utf-8') as out:json.dump(original,out,ensure_ascii=False,indent=2)
    print(json.dumps({'manifest':str(target),'cases':len(original['cases']),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',type=int,required=True);a=p.parse_args();freeze(a.version)
