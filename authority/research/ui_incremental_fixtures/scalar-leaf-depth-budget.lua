local leaf={value=1};__tag(leaf,"personal")
local root=leaf;for i=1,24 do root={next=root} end
__tag(root,"personal")
return leaf.value
