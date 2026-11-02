local mod = RegisterMod('Boundary Refusal', 1)
local json = require('json')
local cfg = mod:HasData() and json.decode(mod:LoadData()) or {amount=2,x=137,language='en'}
local player = Isaac.GetPlayer(0)
local add = player.AddCoins
local random = math.random
local count = 0
mod:AddCallback(1, function() add(player,1) end)
mod:AddCallback(2, function()
    count = count + 1
    if Input.IsButtonTriggered('write') then
        cfg.amount = cfg.amount + 1
        mod:SaveData(json.encode(cfg))
        Isaac.RenderText('unpublished',1,0)
        pcall(function() add(player,3) end)
    elseif Input.IsButtonTriggered('random') then
        pcall(function() random(1,2) end)
    elseif Input.IsButtonTriggered('error') then
        cfg.amount = cfg.amount + 1
        mod:SaveData(json.encode(cfg))
        Isaac.RenderText('unpublished',1,0)
        error('injected callback failure')
    elseif Input.IsButtonTriggered('unknown') then
        require('unregistered-native')
    else
        Isaac.RenderText('count=' .. count .. '|amount=' .. cfg.amount, cfg.x, 0)
    end
end)
