local mod=RegisterMod('Trace Serialization Fixture',1)
local json=require('json')
local config=mod:HasData() and json.decode(mod:LoadData()) or {language='en',key=77,x=20,amount=1}
local count=0
local p=Isaac.GetPlayer(0)
mod:AddCallback(2,function()
    count=count+1
    local saved=mod:HasData() and json.decode(mod:LoadData()) or {}
    local previous=saved.previous or 0
    local before=p:GetNumCoins()
    p:AddCoins(config.amount)
    local after=p:GetNumCoins()
    if Input.IsButtonTriggered(config.key,0) then config.x=config.x+1 end
    config.previous=after
    mod:SaveData(json.encode(config))
    Isaac.RenderText(config.language..'|previous='..previous..'|'..before..'->'..after..'|count='..count,config.x,10,1,1,1,1)
end)
