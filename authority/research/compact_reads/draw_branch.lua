local mod=RegisterMod('Draw Recipe Missing Branch',1)
local cfg=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()
    local x
    if Input.IsButtonTriggered('branch')then x=cfg.x+10 else x=cfg.x-10 end
    Isaac.RenderText('branch',x,0)
end)
