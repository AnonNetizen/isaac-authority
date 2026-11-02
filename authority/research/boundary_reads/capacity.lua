local mod=RegisterMod('Read Capacity',1)
local cfg={}
for i=1,1100 do cfg[i]=i end
mod:AddCallback(2,function()
    local total=0
    for i=1,1100 do total=total+cfg[i] end
    Isaac.RenderText(tostring(total),0,0)
end)
