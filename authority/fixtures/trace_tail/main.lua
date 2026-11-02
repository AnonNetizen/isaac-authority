local mod=RegisterMod('Trace Tail Fixture',1)
local function sample() return math.random(1,99) end
local function reward() return sample() end
local function paint()
    if Options.Language=='zh' then reward() end
    local award=reward()
    local p=Isaac.GetPlayer(0)
    p:AddCoins(award)
    Isaac.RenderText('award='..award..'|coins='..p:GetNumCoins(),10,10,1,1,1,1)
end
mod:AddCallback(2,function() return paint() end)
