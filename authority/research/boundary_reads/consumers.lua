local mod=RegisterMod('Consumer Read Sets',1)
local json=require('json')
local cfg=json.decode(mod:LoadData())
cfg.which='amount'
local alias=cfg
local scalar=7
local list={3,1,2}
local backing={amount=2}
local meta={__index=backing}
local proxy=setmetatable({},meta)
local held={}
local weak=setmetatable({target=held},{__mode='v'})
local player=Isaac.GetPlayer(0)
local add,get=player.AddCoins,player.GetNumCoins
local draw,raw,format=Isaac.RenderText,rawget,string.format
local function make(t) return function() return t.amount end end
local nested=make(cfg)
local eqmeta={__eq=function() return cfg.amount==2 end}
local left,right=setmetatable({},eqmeta),setmetatable({},eqmeta)
local original_eq=eqmeta.__eq
local callmeta={__call=function() return cfg.amount end}
local callable=setmetatable({},callmeta)
mod:AddCallback(1,function() add(player,1) end)
mod:AddCallback(2,function()
    local text
    if Input.IsButtonTriggered('raw') then text=tostring(raw(alias,'amount'))
    elseif Input.IsButtonTriggered('missing') then text=tostring(cfg.absent)
    elseif Input.IsButtonTriggered('length') then text=tostring(#list)
    elseif Input.IsButtonTriggered('rawlen') then text=tostring(rawlen(list))
    elseif Input.IsButtonTriggered('iter') then
        local total=0;for _,v in pairs(list) do total=total+v end;text=tostring(total)
    elseif Input.IsButtonTriggered('ipairs') then
        local total=0;for _,v in ipairs(list) do total=total+v end;text=tostring(total)
    elseif Input.IsButtonTriggered('indexed') then text=tostring(proxy.amount)
    elseif Input.IsButtonTriggered('rawproxy') then text=tostring(raw(proxy,'amount'))
    elseif Input.IsButtonTriggered('scalar') then text=tostring(scalar)
    elseif Input.IsButtonTriggered('nested') then text=format('%d',nested())
    elseif Input.IsButtonTriggered('world') then text=tostring(get(player))
    elseif Input.IsButtonTriggered('dynamic') then text=tostring(alias[cfg.which])
    elseif Input.IsButtonTriggered('repeat') then
        local total=0;for i=1,20000 do total=total+raw(cfg,'amount') end;text=tostring(total)
    elseif Input.IsButtonTriggered('weak') then text=tostring(weak.target~=nil)
    elseif Input.IsButtonTriggered('eq') then text=tostring(left==right)
    elseif Input.IsButtonTriggered('callmeta') then text=tostring(callable())
    elseif Input.IsButtonTriggered('load') then text=mod:LoadData()
    elseif Input.IsButtonTriggered('has') then text=tostring(mod:HasData())
    elseif Input.IsButtonTriggered('self') then
        local before=cfg.amount;cfg.amount=cfg.amount+1;text=before..'|'..cfg.amount
    elseif Input.IsButtonTriggered('unknown') then math.randomseed(460);text='should not execute'
    elseif Input.IsButtonTriggered('fail') then
        cfg.amount=cfg.amount+1;mod:SaveData(json.encode(cfg));draw('unpublished',0,0);error('consumer-injected')
    else text=cfg.language..'|'..alias.amount end
    draw(text,0,0)
end)
mod:AddCallback(3,function()
    if Input.IsButtonTriggered('mut_amount') then cfg.amount=cfg.amount+1;cfg.amount=cfg.amount-1 end
    if Input.IsButtonTriggered('mut_unused') then cfg.x=cfg.x+10 end
    if Input.IsButtonTriggered('mut_absent') then cfg.absent=9;cfg.absent=nil end
    if Input.IsButtonTriggered('mut_scalar') then scalar=scalar+1;scalar=scalar-1 end
    if Input.IsButtonTriggered('mut_list_value') then list[1]=3 end
    if Input.IsButtonTriggered('mut_list_shape') then list[4]=9;list[4]=nil end
    if Input.IsButtonTriggered('mut_list_far') then list[10]=9;list[10]=nil end
    if Input.IsButtonTriggered('mut_list_meta') then setmetatable(list,{__len=function()return 9 end});setmetatable(list,nil) end
    if Input.IsButtonTriggered('mut_backing') then backing.amount=3;backing.amount=2 end
    if Input.IsButtonTriggered('mut_proxy_unused') then proxy.unused=9 end
    if Input.IsButtonTriggered('mut_proxy_shadow') then proxy.amount=3;proxy.amount=nil end
    if Input.IsButtonTriggered('mut_proxy_meta') then setmetatable(proxy,{});setmetatable(proxy,meta) end
    if Input.IsButtonTriggered('mut_index') then meta.__index={amount=3};meta.__index=backing end
    if Input.IsButtonTriggered('mut_which') then cfg.which='language' end
    if Input.IsButtonTriggered('mut_eq') then eqmeta.__eq=function()return false end;eqmeta.__eq=original_eq end
    if Input.IsButtonTriggered('mut_store') then mod:SaveData('changed') end
    if Input.IsButtonTriggered('mut_weak') then held=nil;collectgarbage('collect') end
end)
mod:AddCallback(4,function() draw(tostring(cfg.amount),0,1) end)
