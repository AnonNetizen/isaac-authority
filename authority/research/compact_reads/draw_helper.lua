local mod=RegisterMod('Draw Recipe Caller Parameters',1)
local cfg=require('json').decode(mod:LoadData())
local function paint(text,x,y)Isaac.RenderText(text,x,y)end
mod:AddCallback(2,function()paint('helper|'..cfg.amount,cfg.x,0)end)
