-- Deliberately adversarial old-style mod. DO NOT use with a normal progression run.
-- This fixture is not installed automatically and is not patched for network support.
local mod = RegisterMod("Authority Research Legacy Chaos Fixture", 1)
local json = require("json")
local config = { language = "zh", x = 24, key = Keyboard.KEY_L }
if mod:HasData() then config = json.decode(mod:LoadData()) end
local renderCalls, decision, observedTime = 0, 0, 0
mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    observedTime = Isaac.GetTime()
    decision = math.random(0, 3) + (observedTime % 5)
    Isaac.GetPlayer(0):AddCoins(decision)
end)
mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    renderCalls = renderCalls + 1
    -- Mixed UI/gameplay callback: evaluating again for a second recipient changes the world.
    Isaac.GetPlayer(0):AddCoins(1)
    if Input.IsButtonTriggered(config.key, 0) then
        config.x = config.x + 1
        mod:SaveData(json.encode(config))
    end
    Isaac.RenderText(config.language .. "|" .. renderCalls .. "|" .. observedTime .. "|" .. decision,
                     config.x, 40, 1, 1, 1, 1)
end)
