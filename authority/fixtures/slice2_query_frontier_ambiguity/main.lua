local mod=RegisterMod('Slice2 Query Frontier',1)
mod:AddCallback(2,function()
    local p=Isaac.GetPlayer(0)
    if Options.Language=='zh' then p:AddCoins(1) end
    if Options.Language=='en' then Isaac.RenderText('coins='..p:GetNumCoins(),124,10,1,1,1,1) end
end)
