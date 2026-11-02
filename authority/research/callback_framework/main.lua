CallbackMod=RegisterMod('Callback Framework Fixture',1)
local cfg=require('json').decode(CallbackMod:LoadData())
local private=0
Tex=Sprite();Tex:Load('gfx/ui/modconfig/menu.anm2',false);Tex:SetFrame('Cursor',4)
CallbackMod:AddCallback('fixture.reward',function()Isaac.GetPlayer(0):AddCoins(1)end)
CallbackMod:AddCallback('fixture.ui',function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;private=private+1;CallbackMod:SaveData(require('json').encode(cfg))end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins()..'|private='..private,cfg.x,0)
 if Input.IsButtonTriggered('fail')then CallbackMod:AddCallback('transient',function()return 999 end);CallbackMod:SaveData('not committed');error('callback-injected')end
end)
