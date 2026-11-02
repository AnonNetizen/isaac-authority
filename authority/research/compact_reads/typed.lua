local mod=RegisterMod('Compact Typed Keys',1)
local cfg={[1]='integer',['1']='string',['nul\0key']=3,['甲']=4}
mod:AddCallback(2,function()
    Isaac.RenderText(cfg[1]..'|'..cfg['1']..'|'..cfg['nul\0key']..'|'..cfg['甲'],0,0)
end)
mod:AddCallback(3,function()rawset(cfg,1.0,cfg[1])end)
