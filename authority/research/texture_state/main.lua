TextureMod=RegisterMod('Texture State Fixture',1)
local cfg=require('json').decode(TextureMod:LoadData())
Tex=Sprite();Tex:Load('gfx/ui/modconfig/menu.anm2',false);Tex:SetFrame('Cursor',4)
TextureMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
TextureMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;TextureMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('fail_save')then error('texture-fail-save')end
 if Input.IsButtonTriggered('move')or Input.IsButtonTriggered('fail_replace')then Tex:ReplaceSpritesheet(5,'gfx/ui/modconfig/arrows.png')end
 if Input.IsButtonTriggered('fail_replace')then error('texture-fail-replace')end
 if Input.IsButtonTriggered('graphics')or Input.IsButtonTriggered('fail_graphics')then Tex:LoadGraphics()end
 if Input.IsButtonTriggered('fail_graphics')then error('texture-fail-graphics')end
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins(),cfg.x,0)
 if Input.IsButtonTriggered('fail_draw')then error('texture-fail-draw')end
end)
