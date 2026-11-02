local m=RegisterMod('Reward Timeline Fixture',1)
local json=require('json')
local cfg=json.decode(m:LoadData())
local p=Isaac.GetPlayer(0)
TimelinePlayer=p
local random,seed=math.random,math.randomseed
local last=0
local second=0
local state='initial'
local function give(n)p:AddCoins(n)end
local function show()
 Isaac.RenderText(cfg.language..'|reward='..last..'|second='..second..'|coins='..p:GetNumCoins()..'|state='..state,cfg.x,0)
end
m:AddCallback(101,function()
 SeedReturns=select('#',seed(cfg.seed))
 last=random(cfg.low,cfg.high);RewardValue=last;give(last)
end)
m:AddCallback(102,show)
m:AddCallback(103,function()last=random();RewardValue=last end)
m:AddCallback(104,function()last=random(cfg.high);RewardValue=last;give(last)end)
m:AddCallback(105,function()last=random(1,9);second=random(1,9);RewardValue=last;RewardSecond=second;give(last);give(second)end)
m:AddCallback(106,function()last=random(1,9);RewardValue=last;give(last);give(last)end)
m:AddCallback(107,function()
 last=random(1,9);RewardValue=last;give(last)
 if cfg.draw then if last>4 then state='big'else state='small'end;show()end
end)
m:AddCallback(108,function()
 give(cfg.amount)
 if cfg.draw then if cfg.amount>0 then state='positive'else state='other'end;show()end
end)
m:AddCallback(109,function()
 give(cfg.amount)
 if cfg.draw then if cfg.amount==1 then state='one'else state='other'end;show()end
end)
m:AddCallback(110,function()
 SeedReturns=select('#',seed(cfg.seed));last=random(1,9);RewardValue=last;give(last)
 m:SaveData('rejected');p:GetData().counter=999;error('reward-host-injected')
end)
m:AddCallback(111,function()
 cfg.x=cfg.x+5;m:SaveData(json.encode(cfg));UIState=(UIState or 0)+1;p:GetData().counter=UIState
 last=random(1,9);RewardValue=last;give(last)
 if cfg.draw then show();error('reward-personal-injected')end
end)
m:AddCallback(112,function()
 SeedReturns=select('#',seed(123));last=random(1,9);seed(123);second=random(1,9)
 RewardValue=last;RewardSecond=second;give(last);give(second)
end)
m:AddCallback(113,function()
 last=random(1,9);RewardValue=last;give(last)
 if cfg.draw then second=random(1,9);show()end
end)
m:AddCallback(114,function()last=os.time();give(last)end)
m:AddCallback(115,function()last=random(3,2);give(last)end)
m:AddCallback(116,function()last=random(1,9);RewardValue=last;give(last);if cfg.draw then show();show()end end)
m:AddCallback(117,function()SeedReturns=select('#',seed(cfg.seed));RewardValue=0 end)
m:AddCallback(118,function()last=random(1.5,9);give(last)end)
m:AddCallback(119,function()last=random(1,9,3);give(last)end)
