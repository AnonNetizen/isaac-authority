local mod=RegisterMod('Slice2 Comparisons',1)
mod:AddCallback(2,function()
    local reward=math.random(1,3)
    if Options.Language=='en' then reward=math.random(4,6) end
    local equal,less,le,truth
    if reward==3.0 then equal='equal' else equal='different' end
    if reward<4 then less='less' else less='more' end
    if reward<=3 then le='le' else le='gt' end
    truth=reward and 'truth' or 'false'
    Isaac.GetPlayer(0):AddCoins(reward)
    Isaac.RenderText(equal..'|'..less..'|'..le..'|'..truth..'|'..reward,124,10,1,1,1,1)
end)
