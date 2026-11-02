local cfg=require('json').decode(ModuleFixtureMod:LoadData())
return {cfg=cfg,paint=function()Isaac.RenderText('module='..cfg.amount..'|'..cfg.language,cfg.x,0)end}
