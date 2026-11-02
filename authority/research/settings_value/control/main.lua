BoundaryMod=RegisterMod('Settings Value Boundary Controls',1)
local player=Isaac.GetPlayer(0)
BoundaryMod:AddCallback(456,function()
    for i=1,2 do player:AddCoins(ValuesConfig.amount) end
end)
BoundaryMod:AddCallback(457,function()
    Isaac.RenderText('mixed='..(#ModConfigMenu.MenuData+ValuesConfig.amount),0,0)
end)
