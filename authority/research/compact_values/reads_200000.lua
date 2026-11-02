local m=RegisterMod('Million Reads',1)
local cfg=require('json').decode(m:LoadData())
local total=0
m:AddCallback(2,function()for i=1,200000 do total=total+cfg.amount end;Isaac.RenderText('total='..total,cfg.x,0)end)
