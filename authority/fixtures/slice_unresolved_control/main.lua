local mod=RegisterMod('Slice Control Gate',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local count=0
mod:AddCallback(2,function()
    count=count+1
    local reward=math.random(1,3)
    if Input.IsButtonTriggered(config.key,0) then
        config.x=config.x+1
        mod:SaveData(json.encode(config))
        Isaac.RenderText('queued',0,0,1,1,1,1)
        reward=math.random(4,6)
        if reward>4 then config.x=config.x+1 end
    end
    Isaac.GetPlayer(0):AddCoins(reward)
    Isaac.RenderText(config.language..'|'..count..'|reward='..reward,config.x,10,1,1,1,1)
end)
