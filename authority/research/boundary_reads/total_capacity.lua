local mod=RegisterMod('Total Read Capacity',1)
for group=1,20 do
    mod:AddCallback(2,function()
        for i=1,1000 do Input.IsButtonTriggered('group-'..group..'-button-'..i) end
        Isaac.RenderText('candidate-'..group,0,0)
    end)
end
