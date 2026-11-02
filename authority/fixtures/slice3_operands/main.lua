local mod=RegisterMod('Slice3 Operands',1)
local config=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()
    Isaac.GetPlayer(0):AddCoins(config.amount)
    local a=config.amount*3+4
    local b=10-config.amount
    local c=config.amount-10
    Isaac.RenderText(config.language..'|'..a..','..b..','..c,config.x,10,1,1,1,1)
end)
