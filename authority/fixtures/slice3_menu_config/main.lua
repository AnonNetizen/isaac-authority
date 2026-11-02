local mod=RegisterMod('Slice3 Menu Config',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local alias=config
local function label()return alias.language..'|amount='..alias.amount end
local cached=label
local setting=ModConfigMenu.AddSetting('Mixed','Settings',{
    Type=ModConfigMenu.OptionType.NUMBER,
    CurrentSetting=function()return alias.amount end,
    OnChange=function(value)alias.amount=value;mod:SaveData(json.encode(config)) end,
    Display=cached,
})
mod:AddCallback(2,function()
    if Input.IsButtonTriggered(config.key,0) then
        ModConfigMenu.Change(1,config.amount+1)
        config.x=config.x+1
    end
    Isaac.GetPlayer(0):AddCoins(config.amount)
    ModConfigMenu.Render(1,config.x)
    Isaac.RenderText(cached(),config.x,20,1,1,1,1)
    mod:SaveData(json.encode(config))
    config=json.decode(mod:LoadData());alias=config
end)
