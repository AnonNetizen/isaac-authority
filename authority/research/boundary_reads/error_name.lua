local mod=RegisterMod('Error Name Reads',1)
local meta={__name='KindA'}
local named=setmetatable({},meta)
mod:AddCallback(2,function()
    local ok,err=pcall(function()return named+true end)
    assert(not ok and string.find(err,'KindA',1,true))
    Isaac.RenderText(err,0,0)
end)
mod:AddCallback(3,function()meta.__name='KindB';meta.__name='KindA' end)
