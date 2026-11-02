local mod=RegisterMod('Bound Unproven Metamethod',1)
local cfg=require('json').decode(mod:LoadData())
local proxy=setmetatable({}, {__index=function()return cfg.amount end})
mod:AddCallback(2,function()Isaac.RenderText('meta|'..proxy.amount,cfg.x,0)end)
