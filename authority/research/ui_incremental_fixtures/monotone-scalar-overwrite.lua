local value=1;local function read() return value end
__tag(read,"personal");__tag(read,"world");__tag(read,"personal")
value=false;__tag(read,"personal");local first=read()
value=nil;__tag(read,"world");local second=read()
value=5+6;__tag(read,"personal")
return first,second,read()
