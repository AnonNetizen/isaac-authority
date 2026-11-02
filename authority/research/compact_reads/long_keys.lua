local mod=RegisterMod('Compact Shared Keys',1)
local cfg=require('json').decode(mod:LoadData())
local keys={}
for i=1,cfg.keys do
    local suffix=':'..i
    local key=string.rep('k',cfg.key_bytes-#suffix)..suffix
    keys[i]=key
    cfg[key]=i+cfg.amount
end
for index=1,cfg.consumers do
    mod:AddCallback(2,function()
        local sum=0
        for i=1,#keys do sum=sum+cfg[keys[i]] end
        if Input.IsButtonTriggered('fail') then
            mod:SaveData('discarded')
            Isaac.RenderText('unpublished',0,0)
            error('compact-injected')
        end
        Isaac.RenderText('sum='..sum,index,0)
    end)
end
mod:AddCallback(3,function()
    if Input.IsButtonTriggered('aba') then
        rawset(cfg,keys[1],cfg[keys[1]]+1)
        rawset(cfg,keys[1],cfg[keys[1]]-1)
    end
    if Input.IsButtonTriggered('sibling') then cfg.unread=(cfg.unread or 0)+1 end
end)
