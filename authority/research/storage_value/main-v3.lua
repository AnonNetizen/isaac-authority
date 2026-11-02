StorageMod=RegisterMod('Storage Value Fixture',1)
local cfg=require('json').decode(StorageMod:LoadData())
local alias=cfg
local scalar=cfg.amount
local function set(v)scalar=v end
local function show()return scalar end
local function draw(v)Isaac.RenderText(tostring(v),0,0)end
StorageMod:AddCallback(1,function()local old=cfg.amount;cfg.amount=9;cfg.amount=old;draw(old..':'..cfg.amount)end)
StorageMod:AddCallback(2,function()cfg.amount=7;draw(cfg.amount)end)
StorageMod:AddCallback(3,function()rawset(alias,'amount',8);draw(cfg.amount)end)
StorageMod:AddCallback(4,function()table.insert(cfg.list,cfg.amount);local n=table.remove(cfg.list);draw(n..':'..tostring(cfg.list[1]==nil))end)
StorageMod:AddCallback(5,function()set(7);draw(show())end)
StorageMod:AddCallback(6,function()local old=show();set(9);set(old);draw(old..':'..show())end)
StorageMod:AddCallback(7,function()local n=cfg.amount;local function get()return n end;Getter=get;local old=get();n=n+1;draw(old..':'..get())end)
StorageMod:AddCallback(8,function()local n=cfg.amount;local function get()return n end;local old=get();local t={};for i=1,600 do t[i]=i end;local function arity(...)return select('#',...)end;local count=arity(table.unpack(t));draw(old..':'..get()..':'..count)end)
StorageMod:AddCallback(9,function()local t={a=cfg.amount};local old=t.a;t=nil;collectgarbage('collect');local other={a=cfg.amount};draw(old..':'..other.a)end)
StorageMod:AddCallback(10,function()draw(cfg.amount)end)
StorageMod:AddCallback(11,function()cfg.x=cfg.x+1 end)
StorageMod:AddCallback(12,function()local weak=setmetatable({},{__mode='v'});weak.a={amount=cfg.amount};collectgarbage('collect');draw(weak.a==nil)end)
StorageMod:AddCallback(13,function()cfg.amount=8;StorageMod:SaveData(require('json').encode(cfg));draw(cfg.amount);error('storage-injected')end)
StorageMod:AddCallback(14,function()cfg[{}]=1;draw(cfg.amount)end)
StorageMod:AddCallback(15,function()local n=cfg.amount;local function get()return n end;local old=get();n=7;draw(old..':'..get())end)
StorageMod:AddCallback(16,function()local n=cfg.amount;local function get()return n end;local old=get();n=n..'x';draw(old..':'..get())end)
StorageMod:AddCallback(17,function()scalar=6;draw(show())end)
StorageMod:AddCallback(18,function()local t={a=cfg.amount};local old=t.a;t.a=9;t.a=old;draw(old..':'..t.a)end)
StorageMod:AddCallback(19,function()cfg.amount=nil;draw(cfg.amount==nil)end)
StorageMod:AddCallback(20,function()draw(show())end)
StorageMod:AddCallback(21,function()pcall(function()local n=0;for i=1,4200 do n=n+cfg.amount end end);draw('continued')end)
