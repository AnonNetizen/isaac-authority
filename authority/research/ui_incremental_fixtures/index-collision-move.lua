local t={};__tag(t,'personal')
for i=1,72 do local k='collision_'..i;t[k]=i;__tag(t,'personal') end
local sum=0;for i=1,72 do sum=sum+t['collision_'..i] end
return sum,t.collision_17,t.collision_71
