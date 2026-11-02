local mod = RegisterMod('Boundary Handoff', 1)
local json = require('json')
local cfg = mod:HasData() and json.decode(mod:LoadData()) or {amount=2,x=137,language='en'}
local alias = cfg
local player = Isaac.GetPlayer(0)
local get = player.GetNumCoins
local add = player.AddCoins
local random = math.random
local draw = Isaac.RenderText
local triggered = Input.IsButtonTriggered
local count = 0
local function makeReader(state)
    return function() return state.amount end
end
local reader = makeReader(cfg)
mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    add(player, random(1,1))
end)
mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    if triggered('aba') then cfg.amount = cfg.amount + 1; cfg.amount = cfg.amount - 1 end
    if triggered('move') then
        alias.x = alias.x + 10
        cfg.amount = cfg.amount + 1
        mod:SaveData(json.encode(cfg))
    end
    count = count + 1
    draw(cfg.language .. '|setting=' .. cfg.amount .. '|coins=' .. get(player) .. '|reader=' .. reader(), cfg.x, 0)
end)
mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    draw('counter=' .. count, cfg.x, 1)
end)
