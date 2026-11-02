local mod=RegisterMod('Draw Captured Local Writer',1)
local cfg=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()
    local amount=cfg.amount
    local function overwrite()amount=7 end
    overwrite()
    Isaac.RenderText('actual='..amount,cfg.x,0)
end)
