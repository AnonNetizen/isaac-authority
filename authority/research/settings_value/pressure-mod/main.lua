PressureMod=RegisterMod('Native Pressure Contract Fixture',1)
local cfg=require('json').decode(PressureMod:LoadData())
PressureHeld=Vector(17,23)
PressureFinalized=0
PressureMod:AddCallback(471,function()
    collectgarbage('stop')
    PressureFinalized=0
    local victim=setmetatable({}, {__gc=function()PressureFinalized=PressureFinalized+1 end})
    PressureWeak=setmetatable({held=PressureHeld,dead=Vector(9,9)},{__mode='v'})
    victim=nil
    if not cfg.stop then collectgarbage('restart')end
end)
PressureMod:AddCallback(472,function()
    local mt=getmetatable(PressureHeld)
    local old=mt.__gc
    pcall(function()
        mt.__gc=function()PressureFinalized=PressureFinalized+100 end
        mt.__gc=old
    end)
end)
