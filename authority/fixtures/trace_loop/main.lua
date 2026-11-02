local mod=RegisterMod('Trace Loop Fixture',1)
mod:AddCallback(2,function()
    local times=Options.Language=='zh' and 2 or 1
    local award=0
    for i=1,times do award=math.random(1,99) end
    local p=Isaac.GetPlayer(0)
    p:AddCoins(award)
    Isaac.RenderText('award='..award..'|coins='..p:GetNumCoins(),10,10,1,1,1,1)
end)
