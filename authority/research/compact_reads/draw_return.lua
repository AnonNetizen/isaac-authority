local mod=RegisterMod('Draw Recipe Missing Return Summary',1)
local cfg=require('json').decode(mod:LoadData())
local function compute()return cfg.amount+7 end
mod:AddCallback(2,function()Isaac.RenderText('N'..compute(),cfg.x,0)end)
