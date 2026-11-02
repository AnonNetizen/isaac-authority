local mod=RegisterMod('Bound Stock Lua Scalars',1)
local cfg=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()
    local n=cfg.amount+0.5
    Isaac.RenderText('n='..n..'|q='..((n*2)/3)..'|s='..(cfg.x>>1),cfg.x//2,-cfg.amount)
end)
