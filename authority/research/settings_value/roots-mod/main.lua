RootsMod=RegisterMod('Source Root Fixture',1)
local cfg=ValuesConfig
local holder={entry=cfg.amount+5}
local alias=holder
local captured=cfg.amount+7
local function closed() return captured end
local cachedDraw=Isaac.RenderText
local format=string.format
-- Initially this object's source exists in native constructor metadata. Its Lua
-- upvalue has no materialized vector tag until the first component read.
local delayed=Vector(cfg.x,cfg.amount)
RootsMod:AddCallback(461,function()
    local s=cfg.language..'|a='..alias.entry..'|b='..closed()..'|v='..format('%d:%d',delayed.X,delayed.Y)
    cachedDraw(s,cfg.x,20)
end)
RootsMod:AddCallback(463,function()delayed.Y=cfg.amount+1 end)
