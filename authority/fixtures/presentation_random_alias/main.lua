local mod=RegisterMod('Return Alias Gate Fixture',1)
mod:AddCallback(2,function()
    -- Different personal branches can issue indistinguishable RNG operations for different purposes.
    if Options.Language=='zh' then math.random(1,99) end
    local award=math.random(1,99)
    local p=Isaac.GetPlayer(0)
    p:AddCoins(award)
    Isaac.RenderText('award='..award..'|coins='..p:GetNumCoins(),10,10,1,1,1,1)
end)
