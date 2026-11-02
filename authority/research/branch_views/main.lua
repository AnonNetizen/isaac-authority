local m=RegisterMod('Branch Views Fixture',1)
local json=require('json')
local cfg=json.decode(m:LoadData())
local p=Isaac.GetPlayer(0)
local hits=0
local ui='initial'
local count=0
local alias=cfg
Inspect=function()return cfg.amount,cfg.x,cfg.language,hits,ui,count,p:GetData().counter end
local function save()m:SaveData(json.encode(cfg))end
local function show()Isaac.RenderText(cfg.language..'|amount='..cfg.amount..'|ui='..ui..'|hits='..hits..'|count='..count,cfg.x,0)end
local function choose()if alias.amount==1 then return 'one'else return 'other'end end
m:AddCallback(201,function()p:AddCoins(cfg.amount)end)
m:AddCallback(202,function()
 if Input.IsButtonTriggered(76,0)then cfg.x=cfg.x+10;save()end
 hits=hits+1;p:GetData().counter=hits
 if cfg.amount==1 then ui='one';count=count+1 else ui='other';count=count+2 end
 show()
end)
m:AddCallback(203,show)
m:AddCallback(204,function()
 if cfg.amount==1 then cfg.x=cfg.x+1;ui='one'else cfg.x=cfg.x+2;ui='other'end
 save();show()
end)
m:AddCallback(205,function()
 if cfg.amount==1 then cfg.amount=cfg.amount+100;ui='one'else cfg.amount=cfg.amount+200;ui='other'end
 save();show()
end)
m:AddCallback(206,function()ui=choose();show()end)
m:AddCallback(207,function()
 hits=hits+1;p:GetData().counter=hits;cfg.x=cfg.x+5;save()
 if cfg.amount==1 then ui='one';show();error('presentation-only-injected')else ui='other'end
end)
m:AddCallback(208,function()p:AddCoins(cfg.amount);p:AddCoins(cfg.amount)end)
local hidden=1
m:AddCallback(209,function()if cfg.amount==hidden then ui='one'else ui='other'end;show()end)
m:AddCallback(210,function()
 cfg.x=cfg.x+5;save();hits=hits+1;p:GetData().counter=hits
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 if cfg.amount==1 then count=count+1 end
 show()
end)
m:AddCallback(211,function()
 local ok=pcall(function()if cfg.amount==hidden then ui='one'else ui='other'end end)
 if not ok then ui='swallowed'end;show()
end)
m:AddCallback(212,function()
 ui=choose();if Input.IsButtonTriggered(76,0)then cfg.language='custom';cfg.x=cfg.x+10;save()end;show()
end)
