local mod=RegisterMod('Bound Caught Error',1)
local cfg=require('json').decode(mod:LoadData())
local function fail()
    local temporary={value=cfg.amount}
    local observed=temporary.value
    error('caught-before-draw:'..observed)
end
mod:AddCallback(2,function()
    pcall(fail)
    Isaac.RenderText('caught',cfg.x,0)
end)
