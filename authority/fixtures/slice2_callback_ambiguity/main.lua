local mod=RegisterMod('Slice2 Callback Ambiguity',1)
local function callback()
    Isaac.GetPlayer(0):AddCoins(1)
    Isaac.RenderText('coins='..Isaac.GetPlayer(0):GetNumCoins(),124,10,1,1,1,1)
end
mod:AddCallback(2,callback)
mod:AddCallback(2,callback)
