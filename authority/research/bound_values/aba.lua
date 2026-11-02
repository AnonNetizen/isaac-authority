local mod=RegisterMod('Bound Equal Values Distinct Versions',1)
local cfg=require('json').decode(mod:LoadData())
local draw=Isaac.RenderText
mod:AddCallback(2,function()
    local first=cfg.amount
    draw('first|'..first,cfg.x,0)
    cfg.amount=cfg.amount+1
    cfg.amount=cfg.amount-1
    draw('last|'..cfg.amount,cfg.x,1)
end)
