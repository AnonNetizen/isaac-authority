"""Freeze independent incremental inputs without altering earlier fixtures/expectations."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze(version=1):
    prior=ROOT/'research/ui_bounded_suite_v4.json'
    suite=json.loads(prior.read_bytes());suite.update(schema='isaac-ui-incremental-suite-1',mode='ui-incremental',previous_suite_sha256=digest(prior))
    target=ROOT/f'research/ui_incremental_suite_v{version}.json'
    with target.open('x',encoding='utf-8') as f:json.dump(suite,f,indent=2,ensure_ascii=False)
    cases={
        'field-alias-delete-reinsert':"local t={x=1};local a=t;__tag(t,'personal');__tag(t,'personal');a.x=nil;rawset(a,'x',__tag(7,'world'));a.y={z=8};__tag(t,'personal');return t.x,t.y.z,rawlen(t)",
        'structure-resize':"local t={};__tag(t,'config');for i=1,180 do t['k'..i]=i end;for i=1,100 do t[i]=i+1 end;__tag(t,'config');return t.k179,t[100]",
        'cycle-and-shared-child':"local child={x=2};local a={child=child};local b={child=child};a.self=a;b.other=a;__tag(a,'a');__tag(b,'b');child.x=9;__tag(a,'a');__tag(b,'b');return child.x,a.child.x,b.child.x",
        'open-upvalue-scalar':"local x=1;local f=function() return x end;__tag(f,'closure');x=__tag(9,'world');__tag(f,'closure');return f()",
        'closed-shared-upvalue':"local function make() local x={n=1};return function() return x.n end,function(v) x={n=v} end end;local read,write=make();__tag(read,'closure');write(__tag(8,'world'));__tag(read,'closure');__tag(read,'closure');return read()",
        'native-table-effects':"local t={3,1,2};__tag(t,'config');local insert=table.insert;insert(t,__tag(4,'world'));table.remove(t,2);table.sort(t);__tag(t,'config');return table.concat(t,','),t[3]",
        'metamethod-actual-target':"local target={};local proxy=setmetatable({},{__newindex=function(_,k,v) target[k]=v end});__tag(target,'config');proxy.x=__tag(6,'world');__tag(target,'config');return target.x,proxy.x",
        'cached-dynamic-function':"local t={n=3};local fn=assert(load('local t=...;return t.n*2'));local alias=fn;__tag(t,'config');local first=alias(t);t.n=__tag(7,'world');__tag(t,'config');return first,alias(t),string.char(0,255)",
        'stack-relocation-closed-upvalue':"local x=1;local read=function() return x end;__tag(read,'closure');local function grow(n,...) local a,b,c,d,e,f,g,h=1,2,3,4,5,6,7,8;if n>0 then return grow(n-1,a,b,c,d,e,f,g,h) end return ... end;local v=grow(40);x=7;__tag(read,'closure');return read(),v",
        'ordinary-error-and-bytes':"local ok,err=pcall(function() error('sentinel',0) end);return ok,err,nil,false,string.char(0,255)",
    }
    fixtures=ROOT/'research/ui_incremental_fixtures';fixtures.mkdir(exist_ok=False)
    definitions=[]
    for name,source in cases.items():
        p=fixtures/(name+'.lua');p.write_text(source,encoding='utf-8');definitions.append({'id':name,'file':p.relative_to(ROOT).as_posix(),'sha256':digest(p)})
    definitions={'schema':'isaac-incremental-oracle-suite-1','mode':'ui-incremental','work_limit':2000000,'cases':definitions}
    with (ROOT/f'research/ui_incremental_oracle_v{version}.json').open('x',encoding='utf-8') as f:json.dump(definitions,f,indent=2)
    print(json.dumps({'suite':str(target),'real_cases':len(suite['cases']),'oracle_cases':len(cases),'sha256':digest(target)}))
if __name__=='__main__':freeze()
