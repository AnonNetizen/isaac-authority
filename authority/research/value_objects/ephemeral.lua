local m=RegisterMod('Ephemeral Value',1)
m:AddCallback(2,function()local v=Vector(7,8);Isaac.RenderText(string.format('%.0f',v.X),0,0)end)
