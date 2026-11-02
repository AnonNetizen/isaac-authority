local mod=RegisterMod('Slice2 Branch Budget',1)
mod:AddCallback(2,function()
    local award=math.random(1,3)
    if Options.Language=='en' then
        for i=1,9 do if award>1 then Options.HUDOffset=0.6 else Options.HUDOffset=0.7 end end
    end
    Isaac.GetPlayer(0):AddCoins(award)
end)
