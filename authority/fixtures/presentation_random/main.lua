local mod=RegisterMod('Random Gate Fixture',1)
local json=require('json')
local config=mod:HasData() and json.decode(mod:LoadData()) or {language='en',key=77,x=20}
local count=0
local random=math.random
local clock=os.clock
mod:AddCallback(2,function()
    count=count+1
    local value=random(1,3)
    if Input.IsButtonPressed(99,0) then value=random(1,3) end
    local now=Isaac.GetTime()
    if Input.IsButtonTriggered(config.key,0) then
        config.x=config.x+1
        Options.Language='fr'
        mod:SaveData(json.encode(config))
        Isaac.RenderText('queued before failure',0,0,1,1,1,1)
        -- Return-bearing mutation with no authoritative operation/argument match.
        value=random(4,6)
    end
    Isaac.GetPlayer(0):AddCoins(value)
    Isaac.RenderText(config.language..'|v='..value..'|t='..now..'|clock='..clock()..'|count='..count,config.x,10,1,1,1,1)
end)
