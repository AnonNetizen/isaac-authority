-- Research fixture using ordinary native objects and old-style callbacks. Not auto-installed.
local mod=RegisterMod('Native Private UI Fixture',1)
local json=require('json')
local config=json.decode(mod:LoadData())
local position=Vector(config.x,40)
local color=KColor(1,0.5,0.25,1)
local font=Font()
font:Load(config.font)
local measure=font.GetStringWidth
local renders=0
mod:AddCallback(ModCallbacks.MC_POST_RENDER,function()
    renders=renders+1
    if Input.IsButtonTriggered(config.key,0) then
        position.X=position.X+1
        config.x=position.X
        mod:SaveData(json.encode(config))
    end
    Isaac.GetPlayer(0):AddCoins(1)
    -- Deliberate world divergence after a native field write tests reconstruction.
    if Input.IsButtonPressed(999,0) then Isaac.GetPlayer(0):AddCoins(2) end
    Isaac.RenderText(config.language..'|'..renders..'|'..measure(font,'native bridge'),
        position.X,position.Y,color.Red,color.Green,color.Blue,color.Alpha)
end)
