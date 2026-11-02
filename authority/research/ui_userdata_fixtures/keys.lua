local a=__authority_ui_userdata('Vector',{amount=11})
local b=__authority_ui_userdata('Vector',{amount=22})
local map={[a]=a.amount,[b]=b.amount}
__tag(map,'personal_input:keys')
collectgarbage('collect')
return map[a]+map[b],a~=b
