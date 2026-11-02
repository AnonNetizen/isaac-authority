local mod=RegisterMod('Slice3 Multiple Views',1)
local config=require('json').decode(mod:LoadData())
mod:AddCallback(2,function()
    local amount=config.amount
    Isaac.GetPlayer(0):AddCoins(amount)
    Isaac.GetPlayer(0):AddCoins(amount)
    Isaac.RenderText('amount='..amount,config.x,10,1,1,1,1)
end)
