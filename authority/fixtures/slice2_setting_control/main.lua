local mod=RegisterMod('Slice2 Setting Control',1)
local json=require('json')
local config=json.decode(mod:LoadData())
mod:AddCallback(2,function()
    Isaac.GetPlayer(0):AddCoins(config.amount)
    if config.amount==2 then
        Isaac.RenderText('branch',config.x,10,1,1,1,1)
    else
        Isaac.RenderText('other',config.x,10,1,1,1,1)
    end
end)
