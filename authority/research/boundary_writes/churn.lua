local mod=RegisterMod('Write Barrier Churn',1)
local current
local function make()
    local cfg={amount=2}
    return function() cfg.amount=cfg.amount+1;Isaac.RenderText('amount='..cfg.amount,0,0) end
end
current=make()
mod:AddCallback(2,current)
mod:AddCallback(3,function()
    mod:RemoveCallback(2,current)
    current=nil
    collectgarbage('collect')
    current=make()
    mod:AddCallback(2,current)
end)
