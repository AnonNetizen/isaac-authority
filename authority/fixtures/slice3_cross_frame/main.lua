local mod=RegisterMod('Slice3 Cross Frame',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local previous
local alias=config
local cached=tostring
local dynamic=assert(load("return function(v)return 'amount='..v end",'@slice3-dynamic'))()
local function tail(v)return dynamic(v) end
mod:AddCallback(2,function()
    if Input.IsButtonTriggered(config.key,0) then config.amount=config.amount+1;config.x=config.x+1 end
    local line=config.language..'|'..tail(alias.amount)
    Isaac.GetPlayer(0):AddCoins(config.amount)
    if previous then Isaac.RenderText(previous,config.x,10,1,1,1,1) end
    Isaac.RenderText(line,config.x,20,1,1,1,1)
    Isaac.RenderText('native='..cached(config.amount),config.x,30,1,1,1,1)
    previous=line
    local saved=json.encode(config)
    mod:SaveData(saved)
    config=json.decode(mod:LoadData());alias=config
end)
