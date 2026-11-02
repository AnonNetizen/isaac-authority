local mod=RegisterMod('Slice2 Unresolved Paths',1)
mod:AddCallback(2,function()
    local award=math.random(1,3)
    if Options.Language=='en' then
        if award>1 then Isaac.RenderText('left',1,10,1,1,1,1)
        else Isaac.RenderText('right',2,10,1,1,1,1) end
    end
    -- An unrelated constant contribution cannot prove the earlier random result.
    Isaac.GetPlayer(0):AddCoins(1)
end)
