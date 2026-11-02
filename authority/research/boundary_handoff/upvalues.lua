local mod = RegisterMod('Shared Cells', 1)
local draw = Isaac.RenderText
local counter = 7
local function make()
    return function() return counter end
end
local reader = make()
mod:AddCallback(2, function()
    if Input.IsButtonTriggered('change') then counter = counter + 3 end
    draw('writer=' .. counter, 1, 0)
end)
mod:AddCallback(2, function()
    draw('reader=' .. reader() .. '|direct=' .. counter, 1, 1)
end)
