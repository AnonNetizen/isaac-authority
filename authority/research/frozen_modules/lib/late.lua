local cfg=require('json').decode(ModuleFixtureMod:LoadData());return {paint=function()Isaac.RenderText('late='..cfg.amount,cfg.x,0)end}
