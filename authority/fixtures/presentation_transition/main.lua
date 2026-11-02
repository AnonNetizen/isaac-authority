local mod=RegisterMod('Transition Gate Fixture',1)
local count=0
local p=Isaac.GetPlayer(0)
mod:AddCallback(2,function()
    count=count+1
    local before=p:GetNumCoins()
    p:AddCoins(1)
    local after=p:GetNumCoins()
    -- Two real observations made by a mixed callback: suppressing its write changes this label.
    Isaac.RenderText(before..'->'..after..'|count='..count,10,10,1,1,1,1)
end)
