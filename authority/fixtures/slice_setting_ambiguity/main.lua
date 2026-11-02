local mod=RegisterMod('Slice Setting Ambiguity',1)
local json=require('json')
local config=json.decode(mod:LoadData())
mod:AddCallback(2,function()
    Isaac.GetPlayer(0):AddCoins(config.amount)
    -- Identical dataflow cannot prove whether this is a setting or an award.
    Isaac.RenderText(config.language..'|amount='..config.amount,config.x,10,1,1,1,1)
end)
