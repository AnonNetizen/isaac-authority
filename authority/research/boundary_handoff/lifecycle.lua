local mod = RegisterMod('Callback Lifecycle', 1)
local value = 1
local old
local function make()
    return function() Isaac.RenderText('value=' .. value, 1, 0) end
end
old = make()
mod:AddCallback(2, old)
mod:AddCallback(3, function()
    mod:RemoveCallback(2, old)
    old = nil
    collectgarbage('collect')
    value = value + 1
    mod:AddCallback(2, make())
end)
