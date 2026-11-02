local mod=RegisterMod('Bound Nested Selectors',1)
local cfg=require('json').decode(mod:LoadData())
cfg.inner={amount=cfg.amount}
local function paint(value)Isaac.RenderText('helper|'..value.amount,cfg.x,1)end
mod:AddCallback(2,function()
    local alias=cfg.inner
    Isaac.RenderText('alias|'..alias.amount,cfg.x,0)
    paint(alias)
end)
