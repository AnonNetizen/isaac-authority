local mod=RegisterMod('Write Barrier GC',1)
local held={value=1}
local weak=setmetatable({target=held,[1]=held},{__mode='v'})
local cfg={amount=2}
mod:AddCallback(2,function()
    if Input.IsButtonTriggered('release') then held=nil;collectgarbage('collect') end
    if Input.IsButtonTriggered('replace') then cfg={amount=2};collectgarbage('collect') end
    Isaac.RenderText('amount='..cfg.amount..'|weak='..tostring(weak.target~=nil),0,0)
end)
