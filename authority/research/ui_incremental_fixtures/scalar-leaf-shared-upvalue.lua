local x=1;local function read() return x end
local root={first=read,second=read,position=2}
__tag(root,"personal");root.position=3;__tag(root,"personal")
x=false;root.position=4;__tag(root,"personal");local first=read()
x=__tag(8,"world");root.position=5;__tag(root,"personal")
return first,read(),root.position
