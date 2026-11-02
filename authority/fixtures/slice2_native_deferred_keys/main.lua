local mod=RegisterMod('Slice2 Native Deferred Keys',1)
mod:AddCallback(2,function()
    local reward=math.random(1,3)
    local t={10,20,30}
    if Options.Language=='en' then
        if Input.IsButtonPressed(77,0) then
            local value=rawget(t,reward)
            Isaac.RenderText('read='..(value or 0),124,10,1,1,1,1)
        elseif Input.IsButtonPressed(78,0) then
            rawset(t,reward,99)
        elseif Input.IsButtonPressed(79,0) then
            local ok,value=pcall(function() return next(t,reward) end)
            Isaac.RenderText('next='..tostring(ok),124,10,1,1,1,1)
        end
    end
    Isaac.GetPlayer(0):AddCoins(reward)
end)
