local m=RegisterMod('Secondary',1)
local c=require('json').decode(m:LoadData())
m:AddCallback(13,function()Isaac.RenderText(c.language..':'..c.amount,0,0)end)
