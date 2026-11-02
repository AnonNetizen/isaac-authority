local mod = RegisterMod('Opaque Initialization Table', 1)
local json = require('json')
local cfg = json.decode(mod:LoadData())
local cold = {}
for i=1,cfg.bulk do cold[i] = 'description:' .. i end
mod:AddCallback(2, function()
    Isaac.RenderText('length=' .. #cold .. '|amount=' .. cfg.amount, cfg.x, 0)
end)
