local target={a=1};local proxy=setmetatable({},{__newindex=target});__tag(target,'config')
for i=1,40 do proxy['x'..i]=i;__tag(target,'config') end
local cache=rawset;cache(target,'a',nil);__tag(target,'config');cache(target,'a',5);__tag(target,'config')
return target.a,target.x40,proxy.x40
