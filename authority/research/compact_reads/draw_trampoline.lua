local mod=RegisterMod('Draw Recipe C Wrapper',1)
local cfg=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()pcall(Isaac.RenderText,'P',cfg.x,0)end)
