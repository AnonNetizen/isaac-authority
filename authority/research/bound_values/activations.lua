local mod=RegisterMod('Bound Shared Helper Activations',1)
local cfg=require('json').decode(mod:LoadData())
local function paint(text,x,y)Isaac.RenderText(text,x,y)end
mod:AddCallback(2,function()
    paint('first',cfg.x,0)
    paint('second',cfg.x+1,1)
end)
