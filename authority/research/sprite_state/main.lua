SpriteMod=RegisterMod('Sprite State Fixture',1)
local cfg=require('json').decode(SpriteMod:LoadData())
SP=Sprite();SP:Load('gfx/ui/modconfig/menu.anm2');SP:SetFrame('Cursor',4)
SpriteMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
SpriteMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;SpriteMod:SaveData(require('json').encode(cfg));SP:SetFrame('Cursor',1);SP.Color=Color(1,0.5,0.25,0.5)end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|root='..SP:GetFrame(),cfg.x,0)
 if Input.IsButtonTriggered('fail')then cfg.x=999;SpriteMod:SaveData('uncommitted');SP:SetFrame('Slider1',7);SP.Color=Color(0,0,0);Isaac.RenderText('unpublished',0,0);error('sprite-injected')end
end)
SpriteMod:AddCallback(3,function()Isaac.RenderText(SP:GetAnimation(),0,0)end)
SpriteMod:AddCallback(4,function()Isaac.RenderText(tostring(SP:GetFrame()),0,0)end)
