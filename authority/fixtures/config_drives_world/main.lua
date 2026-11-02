-- Counterexample: a personal key changes a setting that also changes gameplay.
local mod=RegisterMod('Config Drives World Fixture',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local renders=0
mod:AddCallback(ModCallbacks.MC_POST_RENDER,function()
    renders=renders+1
    if Input.IsButtonTriggered(config.key,0) then
        config.amount=config.amount+1
        mod:SaveData(json.encode(config))
    end
    Isaac.GetPlayer(0):AddCoins(config.amount)
    Isaac.RenderText(config.language..'|'..renders,config.x,40,1,1,1,1)
end)
