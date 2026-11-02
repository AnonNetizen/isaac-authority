local mod=RegisterMod('Slice2 Helper Queries',1)
local function present(p)
    if Options.Language=='en' then Isaac.RenderText('before='..p:GetNumCoins(),124,10,1,1,1,1) end
    p:AddCoins(1)
    if Options.Language=='en' then Isaac.RenderText('after='..p:GetNumCoins(),124,20,1,1,1,1) end
end
mod:AddCallback(2,function() present(Isaac.GetPlayer(0)) end)
