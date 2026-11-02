local mod=RegisterMod('Trace Cached Fixture',1)
local random=math.random
local p=Isaac.GetPlayer(0)
local add=p.AddCoins
local coins=p.GetNumCoins
mod:AddCallback(2,function()
    if Options.Language=='zh' then random(1,99) end
    local award=random(1,99)
    add(p,award)
    Isaac.RenderText('award='..award..'|coins='..coins(p),10,10,1,1,1,1)
end)
