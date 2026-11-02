CaptureMod=RegisterMod('Font Capture Fixture',1)
local cfg=require('json').decode(CaptureMod:LoadData())
local count=0
F=Font();F:Load('font/eid_default.fnt');F:SetMissingCharacter(2)
S=FontRenderSettings();S:SetAlignment(0)
C=KColor(.25,.5,.75,1)
Work=function()F:DrawString(cfg.language..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|private='..count,cfg.x,23,1,1,C,S)end
CaptureMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(cfg.amount)end)
CaptureMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;count=count+1;CaptureMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('fail')then cfg.x=999;count=999;CaptureMod:SaveData('uncommitted');F:Load('font/eid_default.fnt');F:SetMissingCharacter(63);S:SetAlignment(8);C.Red=1;F:DrawString('unpublished',0,0,1,1,C,S);error('font-capture-injected')end
 Work()
end)
CaptureMod:AddCallback(3,function()Isaac.RenderText(tostring(S:GetLineHeightModifier()),0,0)end)
CaptureMod:AddCallback(4,function()Isaac.RenderText(tostring(S:GetAlignment()),0,0)end)
