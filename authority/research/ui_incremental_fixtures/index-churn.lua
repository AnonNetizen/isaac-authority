local t={};__tag(t,'config')
for i=1,48 do t['key'..i]=i;__tag(t,'config') end
for i=2,48,2 do t['key'..i]=nil;__tag(t,'config') end
for i=2,48,2 do rawset(t,'key'..i,__tag(i+1,'world'));__tag(t,'config') end
return t.key1,t.key24,t.key48
