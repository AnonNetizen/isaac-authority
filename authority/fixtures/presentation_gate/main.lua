-- Ordinary legacy callback API; this fixture is never installed as a game mod.
local mod=RegisterMod('Presentation Gate Fixture',1)
local json=require('json')
local config=mod:HasData() and json.decode(mod:LoadData()) or {language='en',x=20,key=77,amount=1}
local count=0
local p=Isaac.GetPlayer(0)
local cachedAdd=p.AddCoins
local cachedCoins=p.GetNumCoins
mod:AddCallback(2,function()
    count=count+1
    if Input.IsButtonTriggered(config.key,0) then
        config.amount=config.amount+1
        config.x=config.x+1
        Options.Language='fr'
        mod:SaveData(json.encode(config))
    end
    cachedAdd(p,config.amount)
    if Input.IsButtonPressed(88,0) then cachedAdd(p,2) end
    Isaac.RenderText(config.language..'|coins='..cachedCoins(p)..'|count='..count,config.x,10,1,1,1,1)
end)
