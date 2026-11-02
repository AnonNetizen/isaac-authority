ValueMod=RegisterMod('Value Fixture',1)
local cfg=require('json').decode(ValueMod:LoadData())
V=Vector(cfg.x,42);C=Color(1,0.5,0.25);K=KColor(0.25,0.5,0.75,1)
local alias=V;local cached=V.LengthSquared
ValueMod:AddCallback(1,function()Isaac.GetPlayer(0):AddCoins(1)end)
ValueMod:AddCallback(2,function()
 if Input.IsButtonTriggered('move')then cfg.x=cfg.x+10;alias.X=cfg.x;C.A=0.5;K.Alpha=0.25;ValueMod:SaveData(require('json').encode(cfg))end
 Isaac.RenderText(cfg.language..'|x='..string.format('%.0f',alias.X)..'|coins='..Isaac.GetPlayer(0):GetNumCoins(),cfg.x,0)
 if Input.IsButtonTriggered('fail')then alias.Y=999;C.RO=2;K.Red=0.9;ValueMod:SaveData('uncommitted');Isaac.RenderText('unpublished',0,0);error('value-injected')end
end)
ValueMod:AddCallback(3,function()Isaac.RenderText(string.format('%.0f',alias.X),0,0)end)
ValueMod:AddCallback(4,function()Isaac.RenderText(string.format('%.0f',cached(alias)),0,0)end)
ValueMod:AddCallback(5,function()Isaac.RenderText(string.format('%.1f',C.A),0,0)end)
