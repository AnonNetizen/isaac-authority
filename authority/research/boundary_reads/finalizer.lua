local mod=RegisterMod('Real Finalizer Reads',1)
local cfg={amount=2}
local held=setmetatable({}, {__gc=function()Isaac.RenderText('final='..cfg.amount,0,0)end})
mod:AddCallback(2,function()
    held=nil
    collectgarbage('collect')
    Isaac.RenderText('done',0,1)
end)
mod:AddCallback(3,function()cfg.amount=cfg.amount+1;cfg.amount=cfg.amount-1 end)
