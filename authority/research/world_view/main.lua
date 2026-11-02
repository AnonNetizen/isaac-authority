ViewMod=RegisterMod('World View Fixture',1)
local cfg=require('json').decode(ViewMod:LoadData())
local private=0
P=Isaac.GetPlayer(0);Q=Isaac.GetPlayer(1);Seeds=Game():GetSeeds();Config=Isaac.GetItemConfig()
local function sample()return tostring(Seeds:HasSeedEffect(10))..':'..P.Position.X end
Trace=''
ViewMod:AddCallback(1,function()
 Trace=sample();P:AddCoins(cfg.amount);P.Position=Vector(cfg.x,20);P.ControlsEnabled=false;Seeds:AddSeedEffect(10);Trace=Trace..'>'..sample()
end)
ViewMod:AddCallback(2,function()
 if Input.IsButtonTriggered(76,0)then cfg.x=cfg.x+10;ViewMod:SaveData(require('json').encode(cfg));SFXManager():Play(171)end
 private=private+1;P:GetData().counter=private
 P.Position=Vector(cfg.x,20);P.Velocity=Vector(0,0);P.ControlsEnabled=false;Seeds:AddSeedEffect(10)
 Isaac.RenderText(cfg.language..'|setting='..cfg.amount..'|coins='..P:GetNumCoins()..'|worldx='..P.Position.X..'|hud='..tostring(Seeds:HasSeedEffect(10))..'|private='..private,cfg.x,0)
 if Input.IsButtonTriggered(70,0)then cfg.x=999;ViewMod:SaveData('rejected');P:GetData().counter=999;error('view-injected')end
end)
ViewMod:AddCallback(3,function()Seeds:RemoveSeedEffect(10);P.Position=Vector(64,20);P.ControlsEnabled=true end)
ViewMod:AddCallback(4,function()Isaac.RenderText(tostring(Config:GetCollectible(78):IsAvailable()),0,0)end)
ViewMod:AddCallback(5,function()Isaac.RenderText(Config:GetCollectible(78).Name,0,0)end)
ViewMod:AddCallback(6,function()VoidReturns=select('#',Seeds:AddSeedEffect(10))end)
ViewMod:AddCallback(7,function()RandomValue=math.random(1,99);P.Position=Vector(RandomValue,20);Seeds:AddSeedEffect(10);ViewMod:SaveData('uncommitted');P:GetData().counter=999;error('authority-injected')end)
ViewMod:AddCallback(8,function()for i=1,513 do P.ControlsEnabled=false end end)
ViewMod:AddCallback(9,function()Seeds:AddSeedEffect(1)end)
