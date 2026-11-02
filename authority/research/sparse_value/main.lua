SparseMod=RegisterMod('Sparse Value Fixture',1)
local cfg=require('json').decode(SparseMod:LoadData())
local alias=cfg
local cached=tostring
local function tail(v)return v end
local function helper(v)return cached(v)..'\0' end
local function closure()return alias.amount end
local captured=closure()
local P=Isaac.GetPlayer(0)
SparseMod:AddCallback(1,function()P:AddCoins(alias.amount)end)
SparseMod:AddCallback(2,function()Isaac.RenderText(cfg.language..'|'..helper(tail(closure()+cfg.x*2)),cfg.x,0)end)
SparseMod:AddCallback(3,function()Isaac.RenderText(string.upper(cfg.language)..':'..cfg.amount,0,0)end)
SparseMod:AddCallback(4,function()cfg.amount=cfg.amount+1;Isaac.RenderText(cached(cfg.amount),0,0)end)
SparseMod:AddCallback(5,function()local t={a=alias.amount};rawset(t,'a',tail(t.a));Isaac.RenderText(cached(t.a),0,0)end)
SparseMod:AddCallback(6,function()local t={};table.insert(t,cfg.amount);Isaac.RenderText(cached(t[1]),0,0)end)
SparseMod:AddCallback(7,function()if cfg.amount>1 then Isaac.RenderText('high',0,0)else Isaac.RenderText('low',0,0)end end)
SparseMod:AddCallback(8,function()local n=0;for i=1,4200 do n=n+cfg.amount end;Isaac.RenderText(cached(n),0,0)end)
SparseMod:AddCallback(9,function()local n=0;for i=1,10000 do n=n+i end;Isaac.RenderText(cached(n),0,0)end)
SparseMod:AddCallback(10,function()Isaac.RenderText(cached(captured),0,0)end)
SparseMod:AddCallback(11,function()cfg.amount=cfg.amount+1;error('sparse-injected')end)
SparseMod:AddCallback(12,function()Isaac.RenderText(cfg.language..':'..cfg.amount,0,0)end)
