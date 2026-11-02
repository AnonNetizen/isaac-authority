local t={10,20,30,40};__tag(t,'config');t[2]=nil;__tag(t,'config');t[2]=__tag(21,'world')
t[64]=64;t[-2]=12;t[1.5]=15;t[true]=7;t[false]=8;t.name=9;__tag(t,'config')
local object={n=1};t[object]=11;__tag(t,'config');t.name=nil;__tag(t,'config');t.name=19;__tag(t,'config')
return t[2],t[64],t[-2],t[1.5],t[true],t[false],t[object],t.name
