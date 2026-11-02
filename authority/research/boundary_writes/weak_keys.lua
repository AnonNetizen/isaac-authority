local mod=RegisterMod('Write Barrier Weak Keys',1)
local held={}
local weak=setmetatable({marker=7,[held]=9},{__mode='k'})
mod:AddCallback(2,function()
    if Input.IsButtonTriggered('release') then held=nil;collectgarbage('collect') end
    local count=0
    for _ in pairs(weak) do count=count+1 end
    Isaac.RenderText('count='..count..'|marker='..weak.marker,0,0)
end)
