local mod=RegisterMod('Slice2 Instruction Budget',1)
mod:AddCallback(2,function()
    local award=math.random(1,3)
    if Options.Language=='en' then
        -- A pure jump loop reaches the instruction cap before the graph cap.
        while true do end
    end
    Isaac.GetPlayer(0):AddCoins(award)
end)
