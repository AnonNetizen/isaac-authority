local mod=RegisterMod('Bound Cached State',1)
local cfg=require('json').decode(mod:LoadData())
local cached='seed|'..cfg.amount
local draw=Isaac.RenderText
mod:AddCallback(2,function()draw(cached,cfg.x,0)end)
mod:AddCallback(3,function()cfg.amount=cfg.amount+1;cfg.x=cfg.x+10 end)
