FontMod=RegisterMod('Font Metrics Fixture',1)
local cfg=require('json').decode(FontMod:LoadData())
Tex=Sprite();Tex:Load('gfx/ui/modconfig/menu.anm2',false);Tex:SetFrame('Cursor',4)
F=Font();F:Load('font/eid_default.fnt','');F:SetMissingCharacter(2)
FontMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
FontMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;FontMod:SaveData(require('json').encode(cfg));F:Load('mcm_cn_font/pftempestasevencondensed.fnt')end
 if Input.IsButtonTriggered('fail')then cfg.x=999;FontMod:SaveData('not committed');F:Load('mcm_cn_font/teammeatfont16bold.fnt');Isaac.RenderText('unpublished',0,0);error('font-injected')end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|width='..F:GetStringWidthUTF8('native bridge'),cfg.x,0)
end)
FontMod:AddCallback(3,function()Isaac.RenderText(tostring(F:GetStringWidth('AB')),0,0)end)
FontMod:AddCallback(4,function()Isaac.RenderText(tostring(F:IsLoaded()),0,0)end)
FontMod:AddCallback(5,function()Isaac.RenderText(tostring(F:GetStringWidth(string.char(196,162))),0,0)end)
