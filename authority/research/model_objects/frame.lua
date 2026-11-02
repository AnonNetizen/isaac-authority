local m=RegisterMod('Frame Snapshot',1)
local g=Game();m:AddCallback(2,function()Isaac.RenderText(tostring(g:GetFrameCount()),0,0)end)
