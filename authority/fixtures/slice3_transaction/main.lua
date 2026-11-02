local mod=RegisterMod('Slice3 Transaction',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local private=0
mod:AddCallback(2,function()
    private=private+1
    if Input.IsButtonTriggered(config.key,0) then config.amount=config.amount+1;config.x=config.x+1 end
    Isaac.GetPlayer(0):AddCoins(config.amount)
    mod:SaveData(json.encode(config))
    Isaac.RenderText(config.language..'|amount='..config.amount..'|private='..private,config.x,10,1,1,1,1)
    if Input.IsButtonPressed(88,0) then error('slice3 injected after save state draw') end
end)
