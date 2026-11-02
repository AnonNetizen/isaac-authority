local child={1,2,3};local root={child=child,position=10}
__tag(root,"personal");root.position=11;__tag(root,"personal")
child[2]={value=7};__tag(root,"personal")
child[2]=nil;for i=4,32 do child[i]=i end;__tag(root,"personal")
local old=child;root.child={value=9};__tag(root,"personal")
old[1]=__tag(6,"other");__tag(root,"personal")
return root.child.value,old[1],old[32]
