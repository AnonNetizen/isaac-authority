if not kept then
    kept=__authority_ui_userdata('Vector',{amount=7,x=137})
    kept.read=function()return kept.amount end
end
local garbage={}
for i=1,16 do
    local object=__authority_ui_userdata('Vector',{amount=i})
    object.self=object
    local alias=object
    object.read=function()return alias.amount end
    garbage[i]=object
end
garbage=nil
collectgarbage('collect')
return kept.read(),kept.x
