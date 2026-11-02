local m=RegisterMod('Owned Observation Strings',1)
local cfg=require('json').decode(m:LoadData())
m:AddCallback(2,function()for i=1,3 do cfg.text=string.rep(string.char(96+i),2048);Isaac.RenderText(cfg.text,cfg.x,0)end;cfg.text=nil;collectgarbage('collect')end)
