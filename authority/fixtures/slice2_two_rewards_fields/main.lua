local mod=RegisterMod('Slice2 Two Rewards Fields',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local memory={first=0,second=0,count=0}
local alias=memory
local function rewards() return alias.first,alias.second end
local cached=math.random
mod:AddCallback(2,function()
    memory.count=memory.count+1
    local previous=json.decode(mod:LoadData())
    memory.first=cached(1,3)
    memory.second=cached(4,6)
    if Input.IsButtonTriggered(config.key,0) then
        config.x=config.x+1
        memory.second=memory.first
    end
    local p=Isaac.GetPlayer(0)
    p:AddCoins(memory.first)
    p:AddCoins(memory.second)
    local first,second=rewards()
    config.previousFirst=first
    config.previousSecond=second
    mod:SaveData(json.encode(config))
    Isaac.RenderText(config.language..'|'..memory.count..'|first='..first..'|second='..second..'|prev='..(previous.previousFirst or 0)..','..(previous.previousSecond or 0),config.x,10,1,1,1,1)
end)
