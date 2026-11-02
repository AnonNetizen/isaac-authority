local m=RegisterMod('Copy On Write Versions',1)
local cfg=require('json').decode(m:LoadData())
m:AddCallback(2,function()for i=1,3 do local a=cfg.amount;Isaac.RenderText('amount='..a,cfg.x,0);cfg.amount=cfg.amount+1 end end)
