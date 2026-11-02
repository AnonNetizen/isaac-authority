local mod=RegisterMod('Trace Dynamic Fixture',1)
local sample=assert(load('return function() return math.random(1,99) end','@trace-dynamic','t'))()
mod:AddCallback(2,function()
    if Options.Language=='zh' then sample() end
    local award=sample()
    local p=Isaac.GetPlayer(0)
    p:AddCoins(award)
    Isaac.RenderText('award='..award..'|coins='..p:GetNumCoins(),10,10,1,1,1,1)
end)
