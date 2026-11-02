local mod=RegisterMod('Trace Generic Loop Fixture',1)
mod:AddCallback(2,function()
    local award=0
    for _,amount in ipairs({1,2}) do award=math.random(1,99)+amount end
    Isaac.GetPlayer(0):AddCoins(award)
    Isaac.RenderText('award='..award,10,10,1,1,1,1)
end)
