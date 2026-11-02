local mod=RegisterMod('Compact Retired Keys',1)
local cfg={amount=2}
mod:AddCallback(2,function()
    local temp={retired_value=cfg.amount}
    Isaac.RenderText('temp='..temp.retired_value,0,0)
end)
