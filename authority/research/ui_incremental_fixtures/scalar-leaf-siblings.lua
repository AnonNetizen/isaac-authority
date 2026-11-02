local left={};for i=1,40 do left[i]=i end
local root={left=left,right={value=2}}
__tag(root,"personal");root.right.value=7;__tag(root,"personal")
root.right={value=9};__tag(root,"personal")
return root.left[1],root.left[40],root.right.value
