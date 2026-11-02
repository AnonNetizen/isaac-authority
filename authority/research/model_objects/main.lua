ObjectModelMod=RegisterMod('Object Model',1)
local cfg=require('json').decode(ObjectModelMod:LoadData())
ObjectSprite=Sprite();ObjectSprite:Load('gfx/ui/modconfig/menu.anm2',false)
OtherSprite=Sprite();OtherSprite:Load('gfx/ui/modconfig/menu.anm2',false)
local sprite=ObjectSprite;local game=Game()
ObjectModelMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
ObjectModelMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;ObjectModelMod:SaveData(require('json').encode(cfg))end
 if Input.IsButtonTriggered('change')then sprite:Load('gfx/eid_transform_icons.anm2',false)end
 Isaac.RenderText(cfg.language..'|amount='..cfg.amount..'|default='..sprite:GetDefaultAnimationName()..'|players='..game:GetNumPlayers(),cfg.x,game:GetFrameCount())
 if Input.IsButtonTriggered('fail')then cfg.x=cfg.x+100;ObjectModelMod:SaveData(require('json').encode(cfg));sprite:Load('gfx/eid_transform_icons.anm2',false);Isaac.RenderText('unpublished',0,0);error('object-injected')end
 if Input.IsButtonTriggered('unknown')then pcall(sprite.Reset,sprite)end
end)
