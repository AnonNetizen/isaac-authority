local mod=RegisterMod('Bound Failure Restoration',1)
local cfg=require('json').decode(mod:LoadData())
local count=0
mod:AddCallback(2,function()
    count=count+1
    if Input.IsButtonTriggered('fail')then
        cfg.amount=cfg.amount+1
        mod:SaveData(require('json').encode(cfg))
        Isaac.RenderText('unpublished',cfg.x,0)
        error('bound-injected')
    end
    Isaac.RenderText('count='..count..'|amount='..cfg.amount,cfg.x,0)
end)
