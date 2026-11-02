-- Adversarial test mod; no special handling for these fields exists in C++.
ValuesMod=RegisterMod('Settings Serialization Fixture',1)
local json=require('json')
local cfg=json.decode(ValuesMod:LoadData())
local player=Isaac.GetPlayer(0)
local encode=json.encode
local function copy(s) return s end
local function label() return 'amount='..cfg.amount end
local function conditional() if cfg.amount==1 then return 'one' else return 'other' end end
local function changed(v)
    cfg.amount=v
    local mode=cfg.mode
    if mode=='write-divergent' then cfg.private=cfg.private+1 end
    if mode=='rawset-aba' then
        local old=cfg.private
        rawset(cfg,'private',0)
        rawset(cfg,'private',old)
    end
    local encoded=copy(encode(cfg))
    if mode=='append-space' then encoded=encoded..' ' end
    if mode=='native-rewrite' then encoded=string.gsub(encoded,'"private":%d+','"private":'..cfg.private) end
    ValuesMod:SaveData(encoded)
    if mode=='two-saves' then ValuesMod:SaveData(copy(encoded)) end
    if mode=='fail-save' then error('serialization-injected-after-save') end
    if mode=='fail-state' or mode=='fail-draw' then
        cfg.x=cfg.x+3
        if mode=='fail-draw' then Isaac.RenderText('serialization-discarded',0,0) end
        error('serialization-injected-after-effects')
    end
end
ModConfigMenu.AddSetting('Value Probe',{
    Type=ModConfigMenu.OptionType.NUMBER,Minimum=0,Maximum=20,
    CurrentSetting=function()return cfg.amount end,OnChange=changed,Display=label,Info='serialization-info',
})
ModConfigMenu.AddSetting('Value Probe',{Type=ModConfigMenu.OptionType.TEXT,Display=conditional})
ModConfigMenu.AddSetting('Value Probe',{
    Type=ModConfigMenu.OptionType.NUMBER,Minimum=0,Maximum=40,
    CurrentSetting=function()return cfg.private end,Display=function()return 'private='..cfg.private end,
    OnChange=function(v)cfg.private=v;ValuesMod:SaveData(encode(cfg))end,
})
ValuesMod:AddCallback(451,function()player:AddCoins(cfg.amount)end)
ValuesMod:AddCallback(452,function()
    if cfg.amount==1 then cfg.private=10 else cfg.private=20 end
    if cfg.details then
        if cfg.amount==1 then cfg.details.flag=10 else cfg.details.flag=20 end
    end
end)
ValuesMod:AddCallback(453,function()
    Isaac.RenderText(label(),cfg.x,0)
    Isaac.RenderText(conditional(),cfg.x,20)
    Isaac.RenderText('private='..cfg.private,cfg.x,40)
    Isaac.RenderText('coins='..player:GetNumCoins(),cfg.x,60)
end)
ValuesConfig=cfg
