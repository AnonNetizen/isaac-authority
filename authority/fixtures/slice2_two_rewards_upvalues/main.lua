local mod=RegisterMod('Slice2 Two Rewards Upvalues',1)
local first,second=0,0
local function getFirst() return first end
local function getSecond() return second end
local function roll(lo,hi) return math.random(lo,hi) end
mod:AddCallback(2,function()
    first=roll(1,3)
    second=roll(4,6)
    if Options.Language=='en' then second=first end
    local p=Isaac.GetPlayer(0)
    p:AddCoins(getFirst())
    p:AddCoins(getSecond())
    Isaac.RenderText('first='..getFirst()..'|second='..getSecond(),124,10,1,1,1,1)
end)
