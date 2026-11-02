FlowMod=RegisterMod('UI Flow Fixture',1)
local cfg=require('json').decode(FlowMod:LoadData())
local count=0
G=Game()
A=Sprite();A:Load('gfx/eid_transform_icons.anm2',false);A:Play('Arrow',false)
B=Sprite();B:Load('gfx/ui/modconfig/menu.anm2',false)
FlowMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(cfg.amount)end)
FlowMod:AddCallback(2,function()
 A:Update()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;count=count+1;FlowMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('fail')then A:Update();cfg.x=999;count=999;FlowMod:SaveData('uncommitted');Isaac.RenderText('unpublished',0,0);error('ui-flow-injected')end
 Isaac.RenderText(cfg.language..'|paused='..tostring(G:IsPaused())..'|frame='..A:GetFrame()..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|private='..count,cfg.x,0)
end)
FlowMod:AddCallback(3,function()Isaac.RenderText(tostring(G:IsPaused()),0,0)end)
FlowMod:AddCallback(4,function()Isaac.RenderText(tostring(A:GetFrame()),0,0)end)
FlowMod:AddCallback(5,function()Isaac.RenderText(tostring(A:IsPlaying()),0,0)end)
