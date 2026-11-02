local mod=RegisterMod('Bound Read Time',1)
local cfg=require('json').decode(mod:LoadData())
local draw=Isaac.RenderText
mod:AddCallback(2,function()
    local before=cfg.amount
    cfg.amount=cfg.amount+1
    draw('before|'..before,cfg.x,0)
    local after=cfg.amount
    draw('after|'..after,cfg.x,1)
end)
