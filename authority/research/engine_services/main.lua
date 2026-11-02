ServiceMod=RegisterMod('Engine Services Fixture',1)
local cfg=require('json').decode(ServiceMod:LoadData())
Config=Isaac.GetItemConfig();Item=Config:GetCollectible(1)
local cached=Config.GetCollectible
Isaac.DebugString('init:'..cfg.language)
ServiceMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
ServiceMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;ServiceMod:SaveData(require('json').encode(cfg))end
 Isaac.DebugString(cfg.language..'|'..Item.Name)
 Isaac.RenderText(cfg.language..'|x='..cfg.x..'|coins='..Isaac.GetPlayer(0):GetNumCoins(),cfg.x,0)
 if Input.IsButtonTriggered('fail')then cfg.x=999;ServiceMod:SaveData('uncommitted');Isaac.DebugString('uncommitted');Isaac.RenderText('unpublished',0,0);error('service-injected')end
end)
ServiceMod:AddCallback(3,function()Isaac.RenderText(cached(Config,1).Name..'|q='..Item.Quality,0,0)end)
