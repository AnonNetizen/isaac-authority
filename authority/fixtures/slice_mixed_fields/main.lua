local mod=RegisterMod('Slice Mixed Fields',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local memory={award=0,count=0}
local alias=memory
local function award() return alias.award end
mod:AddCallback(2,function()
    memory.count=memory.count+1
    local saved=json.decode(mod:LoadData())
    local previous=saved.previous or 0
    if Input.IsButtonTriggered(config.key,0) then config.x=config.x+1 end
    memory.award=math.random(1,3)
    Isaac.GetPlayer(0):AddCoins(memory.award)
    config.previous=award()
    mod:SaveData(json.encode(config))
    Isaac.RenderText(config.language..'|award='..award()..'|previous='..previous..'|count='..memory.count,config.x,10,1,1,1,1)
end)
