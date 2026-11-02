local mod=RegisterMod('Slice3 Lost Serialization',1)
local json=require('json')
local config=json.decode(mod:LoadData())
mod:AddCallback(2,function()
    Isaac.GetPlayer(0):AddCoins(config.amount)
    -- Identical bytes are not proof that field provenance survived concatenation.
    local text=json.encode(config)..''
    mod:SaveData(text)
    config=json.decode(mod:LoadData())
    Isaac.RenderText(config.language..'|amount='..config.amount,config.x,10,1,1,1,1)
end)
