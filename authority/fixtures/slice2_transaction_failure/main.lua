local mod=RegisterMod('Slice2 Transaction Failure',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local count=0
mod:AddCallback(2,function()
    count=count+1
    local reward=math.random(1,3)
    local p=Isaac.GetPlayer(0)
    p:AddCoins(reward)
    if Input.IsButtonTriggered(config.key,0) then
        config.x=config.x+1
        mod:SaveData(json.encode(config))
        Isaac.RenderText('staged='..count,config.x,10,1,1,1,1)
        error('slice2 injected after save private state and queued draw')
    end
    Isaac.RenderText(config.language..'|'..count..'|reward='..reward,config.x,10,1,1,1,1)
end)
