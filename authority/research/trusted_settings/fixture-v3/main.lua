-- A test mod using the real, unchanged MCM API. No runtime purpose markers.
IdentityMod = RegisterMod('Trusted Settings Fixture', 1)
local json = require('json')
local cfg = json.decode(IdentityMod:LoadData())
AuditMode = cfg.mode or 'normal'
AuditValue, AuditChanges, AuditArgs, AuditInfo = cfg.amount, 0, '', 0
local function shown()
    if AuditMode == 'error' then error('settings-callback-injected') end
    if AuditMode == 'error-after-effects' then
        AuditValue, cfg.amount = 999, 999
        IdentityMod:SaveData(json.encode(cfg))
        Isaac.RenderText('discarded-setting-draw', 11, 22)
        error('settings-effects-injected')
    end
    if AuditMode == 'none' then return end
    if AuditMode == 'false-nil' then return false, nil, 7 end
    if AuditMode == 'nested-draw' then Isaac.RenderText('nested-personal', 11, 22) end
    return 'amount=' .. AuditValue
end
local cached = shown
local function display(a, b, p)
    AuditArgs = type(a) .. '|' .. type(b) .. '|' .. tostring(p.X)
    return cached()
end
AuditSetting = ModConfigMenu.AddSetting('Identity Probe', {
    Type = ModConfigMenu.OptionType.NUMBER,
    Minimum = 0, Maximum = 20,
    CurrentSetting = function() return AuditValue end,
    OnChange = function(v)
        AuditValue, AuditChanges = v, AuditChanges + 1
        cfg.amount = v
        IdentityMod:SaveData(json.encode(cfg))
        return false, nil
    end,
    Display = display,
    Info = function()
        AuditInfo = AuditInfo + 1
        if AuditMode == 'table-info' then return {'info-first', 'info-second'} end
        return 'personal-info'
    end,
})
AuditTranslated = function() return 'translated=' .. AuditValue end
IdentityMod:AddCallback(401, function()
    local v = display(false, false, Vector(3, 4))
    Isaac.RenderText(tostring(v), 0, 0)
end)
IdentityMod:AddCallback(402, function()
    local ok = pcall(ModConfigMenu.PostRender)
    Isaac.RenderText(tostring(ok), 0, 0)
end)
IdentityMod:AddCallback(403, function()
    SpoofPostRender()
end)
include('scripts/modconfig')
