local mod=RegisterMod('Trace Loop Tail Fixture',1)
local function sample() return math.random(1,99) end
local function reward()
    local count=Options.Language=='zh' and 2 or 1
    for i=1,count do return sample() end
end
mod:AddCallback(2,function()
    local award=reward()
    local p=Isaac.GetPlayer(0)
    p:AddCoins(award)
    Isaac.RenderText('award='..award..'|coins='..p:GetNumCoins(),10,10,1,1,1,1)
end)
