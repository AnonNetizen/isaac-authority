local mod=RegisterMod('Bound Observation Release',1)
local cfg=require('json').decode(mod:LoadData())
local function touch(n)
    local temporary={value=n}
    local observed=temporary.value
    return observed
end
mod:AddCallback(2,function()
    for i=1,256 do touch(i) end
    collectgarbage('collect')
    Isaac.RenderText('kept',cfg.x,0)
end)
