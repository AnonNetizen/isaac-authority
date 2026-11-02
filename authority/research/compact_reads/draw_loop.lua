local mod=RegisterMod('Draw Recipe Missing Loop',1)
local cfg=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()
    local total=0
    for i=1,cfg.amount do total=total+i end
    Isaac.RenderText('T'..total,cfg.x,0)
end)
