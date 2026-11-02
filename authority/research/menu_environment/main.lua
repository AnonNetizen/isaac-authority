MenuMod=RegisterMod('Menu Environment Fixture',1)
local cfg=require('json').decode(MenuMod:LoadData())
local counter=0
P=Isaac.GetPlayer(0);Q=Isaac.GetPlayer(1);R=Game():GetRoom();SFX=SFXManager()
MenuMod:AddCallback(1,function()P:AddCoins(cfg.amount)end)
MenuMod:AddCallback(2,function()
 if Input.IsButtonTriggered(76,0)then cfg.x=cfg.x+10;counter=counter+1;MenuMod:SaveData(require('json').encode(cfg));SFX:Play(171,.5,0,false,1,0)end
 local data=P:GetData();if Input.IsButtonTriggered(70,0)then data.changed=999;cfg.x=999;MenuMod:SaveData('rejected');SFX:Play(171);Isaac.RenderText('rejected',0,0);error('menu-injected')end
 Isaac.RenderText(cfg.language..'|coins='..P:GetNumCoins()..'|private='..counter..'|data='..tostring(data.changed),cfg.x,0)
end)
MenuMod:AddCallback(3,function()Isaac.RenderText(tostring(P:GetPlayerType()),0,0)end)
MenuMod:AddCallback(4,function()Isaac.RenderText(tostring(Input.IsButtonTriggered(76,0)),0,0)end)
MenuMod:AddCallback(5,function()SFX:Play(171);SFX:Play(171,1,0,false,1)end)
MenuMod:AddCallback(6,function()for i=1,129 do SFX:Play(171)end end)
MenuMod:AddCallback(7,function()Isaac.RenderText(tostring(Input.GetMousePosition(true).X),0,0)end)
