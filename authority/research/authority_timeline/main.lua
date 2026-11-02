local m=RegisterMod('Authority Timeline Fixture',1)
local cfg=require('json').decode(m:LoadData())
local p=Isaac.GetPlayer(0)
TimelinePlayer=p
local add=p.AddCoins
local function give(n)add(p,n)end
local function render(prefix)Isaac.RenderText((prefix or cfg.language)..'|setting='..cfg.amount..'|coins='..p:GetNumCoins(),cfg.x,0)end
m:AddCallback(41,function()Before=p:GetNumCoins();give(cfg.amount);After=p:GetNumCoins()end)
m:AddCallback(42,function()render()end)
m:AddCallback(43,function()give(cfg.amount);give(cfg.amount)end)
m:AddCallback(44,function()cfg.x=cfg.x+1;m:SaveData(require('json').encode(cfg));UIState=(UIState or 0)+1;p:GetData().counter=UIState;render()end)
m:AddCallback(45,function()for i=1,2 do give(cfg.amount)end end)
m:AddCallback(46,function()if cfg.extra then Extra=p:GetNumCoins()end;give(cfg.amount)end)
m:AddCallback(47,function()give(cfg.amount+1)end)
m:AddCallback(49,function()if cfg.amount==1 then Isaac.RenderText('one',cfg.x,0)else Isaac.RenderText('other',cfg.x,0)end end)
m:AddCallback(50,function()cfg.x=cfg.x+5;m:SaveData(require('json').encode(cfg));UIState=99;p:GetData().counter=99;render();error('timeline-injected')end)
m:AddCallback(51,function()local r=math.random(1,99);give(r)end)
m:AddCallback(52,function()add(p,1)end)
m:AddCallback(53,function()if cfg.language=='zh' then render('中文')else render('English')end end)
m:AddCallback(54,function()Isaac.RenderText('x='..cfg.x,cfg.x,0)end)
m:AddCallback(55,function()if cfg.extra then give(cfg.amount)else give(cfg.amount)end end)
m:AddCallback(56,function()local v=Vector(cfg.x,20);v.X=7;p.Position=v end)
m:AddCallback(57,function()Isaac.RenderText('reward='..cfg.cosmetic,cfg.x,0)end)
