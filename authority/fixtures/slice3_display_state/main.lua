local mod=RegisterMod('Slice3 Display State',1)
local json=require('json')
local config=json.decode(mod:LoadData())
mod:AddCallback(2,function()
    if Input.IsButtonTriggered(config.key,0) then config.x=config.x+1 end
    Isaac.GetPlayer(0):AddCoins(config.amount)
    if config.amount==2 then config.x=config.x+5 end
    Isaac.RenderText(config.language..'|amount='..config.amount,config.x,10,1,1,1,1)
    mod:SaveData(json.encode(config))
end)
