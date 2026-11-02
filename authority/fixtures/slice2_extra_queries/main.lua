local mod=RegisterMod('Slice2 Extra Queries',1)
mod:AddCallback(2,function()
    local p=Isaac.GetPlayer(0)
    if Options.Language=='en' then Isaac.RenderText('before='..p:GetNumCoins(),124,10,1,1,1,1) end
    p:AddCoins(1)
    if Options.Language=='en' then Isaac.RenderText('after='..p:GetNumCoins(),124,20,1,1,1,1) end
end)
