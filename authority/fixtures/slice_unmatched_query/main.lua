local mod=RegisterMod('Slice Query Gate',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local count=0
mod:AddCallback(2,function()
    count=count+1
    Isaac.GetPlayer(0):AddCoins(1)
    if Input.IsButtonTriggered(config.key,0) then
        config.x=config.x+1
        mod:SaveData(json.encode(config))
        Isaac.RenderText('queued',0,0,1,1,1,1)
        Isaac.RenderText('extra='..Isaac.GetPlayer(0):GetNumCoins(),0,0,1,1,1,1)
    end
    Isaac.RenderText(config.language..'|'..count,config.x,10,1,1,1,1)
end)
