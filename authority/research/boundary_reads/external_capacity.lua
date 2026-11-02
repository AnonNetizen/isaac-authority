local mod=RegisterMod('External Read Capacity',1)
mod:AddCallback(2,function()
    for i=1,1100 do Input.IsButtonTriggered('button-'..i) end
    Isaac.RenderText('unreachable',0,0)
end)
