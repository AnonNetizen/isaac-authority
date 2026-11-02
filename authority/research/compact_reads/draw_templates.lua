local mod=RegisterMod('Draw Recipe Operands',1)
local cfg=require('json').decode(mod:LoadData())
local draw=Isaac.RenderText
mod:AddCallback(2,function()
    local amount=cfg.amount
    local alias=cfg
    draw('A|'..amount,alias.x+3,100-cfg.amount);draw('B|'..amount..'/'..cfg.language,cfg.x*2,cfg.x-100)
    draw('raw\0\255'..cfg.language,0,1)
end)
