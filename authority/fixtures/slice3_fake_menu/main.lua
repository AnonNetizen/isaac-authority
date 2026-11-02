local mod=RegisterMod('Slice3 Fake Menu',1)
local config=require('json').decode(mod:LoadData())
local function label()return config.language..'|amount='..config.amount end
ModConfigMenu={}
function ModConfigMenu.Render()Isaac.RenderText(label(),config.x,10,1,1,1,1) end
mod:AddCallback(2,function()
    Isaac.GetPlayer(0):AddCoins(config.amount)
    ModConfigMenu.Render()
end)
