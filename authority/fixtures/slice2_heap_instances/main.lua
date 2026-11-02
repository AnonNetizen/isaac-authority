local mod=RegisterMod('Slice2 Heap Instances',1)
local function cell() return {reward=0} end
local first,second=cell(),cell()
mod:AddCallback(2,function()
    first.reward=math.random(1,3)
    second.reward=math.random(4,6)
    if Options.Language=='en' then second.reward=first.reward end
    local p=Isaac.GetPlayer(0)
    p:AddCoins(first.reward)
    p:AddCoins(second.reward)
    Isaac.RenderText(first.reward..'|'..second.reward,124,10,1,1,1,1)
end)
