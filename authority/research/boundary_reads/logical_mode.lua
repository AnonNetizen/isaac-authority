local mod=RegisterMod('Logical Mode Reads',1)
local meta={__mode='v'}
local value=setmetatable({},meta)
mod:AddCallback(2,function()Isaac.RenderText(getmetatable(value).__mode,0,0)end)
mod:AddCallback(3,function()meta.__mode='k';meta.__mode='v'end)
