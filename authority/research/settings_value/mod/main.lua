-- A normal test mod; the real MCM source and its callbacks are not patched.
ValuesMod=RegisterMod('Settings Value Fixture',1)
local json=require('json')
local cfg=json.decode(ValuesMod:LoadData())
local player=Isaac.GetPlayer(0)
local function label() return 'amount='..cfg.amount end
local function conditional()
    if cfg.amount==1 then return 'one' else return 'other' end
end
local function saved(v)
    cfg.amount=v
    ValuesMod:SaveData(json.encode(cfg))
end
ModConfigMenu.AddSetting('Value Probe',{
    Type=ModConfigMenu.OptionType.NUMBER,Minimum=0,Maximum=20,
    CurrentSetting=function() return cfg.amount end,
    OnChange=saved,Display=label,Info='value-info',
})
ModConfigMenu.AddSetting('Value Probe',{
    Type=ModConfigMenu.OptionType.TEXT,Display=conditional,
})
ModConfigMenu.AddSetting('Value Probe',{
    Type=ModConfigMenu.OptionType.NUMBER,Minimum=0,Maximum=40,
    CurrentSetting=function()return cfg.private end,
    OnChange=function(v)cfg.private=v;ValuesMod:SaveData(json.encode(cfg))end,
    Display=function()return 'private='..cfg.private end,
})
ValuesMod:AddCallback(451,function() player:AddCoins(cfg.amount) end)
ValuesMod:AddCallback(452,function()
    if cfg.amount==1 then cfg.private=10 else cfg.private=20 end
end)
ValuesMod:AddCallback(453,function()
    Isaac.RenderText(label(),cfg.x,0)
    Isaac.RenderText(conditional(),cfg.x,20)
    Isaac.RenderText('private='..cfg.private,cfg.x,40)
    Isaac.RenderText('coins='..player:GetNumCoins(),cfg.x,60)
end)
ValuesMod:AddCallback(454,function()
    if Input.IsButtonTriggered(70,0)then
        cfg.amount=999
        ValuesMod:SaveData(json.encode(cfg))
        Isaac.RenderText('discarded-outside',0,0)
        error('settings-frame-injected')
    end
end)
ValuesConfig=cfg
