local mod=RegisterMod('Draw Recipe Tailcall',1)
local cfg=require('json').decode(mod:LoadData())
local draw=Isaac.RenderText
mod:AddCallback(2,function()return draw('tail|'..cfg.amount,cfg.x,0)end)
