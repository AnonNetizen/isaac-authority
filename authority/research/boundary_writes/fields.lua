local mod = RegisterMod('Write Barrier Fields', 1)
local cfg = {amount=2,x=137,language='zh',[1]=3,[2]=1,[3]=2,['1']=11}
local alias = cfg
local proxy = setmetatable({}, {__newindex=cfg})
local denied = setmetatable({}, {__newindex=function() error('denied-write') end})
local raw = rawset
local insert, remove, move, sort = table.insert, table.remove, table.move, table.sort
mod:AddCallback(2, function()
    if Input.IsButtonTriggered('aba') then alias.amount=3;cfg.amount=2 end
    if Input.IsButtonTriggered('same') then cfg.amount=cfg.amount end
    if Input.IsButtonTriggered('raw') then raw(alias,'amount',3);raw(cfg,'amount',2) end
    if Input.IsButtonTriggered('nil') then cfg.new=7;cfg.new=nil;cfg.new=nil end
    if Input.IsButtonTriggered('typed') then cfg[1.0]=9;cfg['1']=12 end
    if Input.IsButtonTriggered('insert') then insert(cfg,2,9) end
    if Input.IsButtonTriggered('remove') then remove(cfg,2) end
    if Input.IsButtonTriggered('move') then move(cfg,1,3,2,cfg) end
    if Input.IsButtonTriggered('sort') then sort(cfg) end
    if Input.IsButtonTriggered('sibling') then
        for i=1,1000 do cfg['cold'..i]=i end
        for i=1,1000 do cfg[i+10]=i end
        for i=1,1000 do cfg[i+10]=nil end
    end
    if Input.IsButtonTriggered('proxy') then proxy.amount=3;proxy.amount=2 end
    if Input.IsButtonTriggered('deny') then
        assert(not pcall(function() denied.amount=3 end))
        assert(not pcall(function() rawset(cfg,nil,1) end))
        assert(not pcall(function() rawset(cfg,0/0,1) end))
    end
    if Input.IsButtonTriggered('meta') then setmetatable(cfg,{});setmetatable(cfg,nil) end
    if Input.IsButtonTriggered('many') then for i=1,20000 do cfg.amount=2 end end
    Isaac.RenderText(cfg.language..'|'..cfg.amount..'|'..cfg[1]..'|'..cfg['1'],cfg.x,0)
end)
