local mod=RegisterMod('Unknown Native Guard',1)
local unknown=math.randomseed
mod:AddCallback(2,function()
    local ok=pcall(unknown,460)
    if ok then error('unknown native executed') end
    Isaac.RenderText('swallowed rejection',0,0)
end)
