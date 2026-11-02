ModuleFixtureMod=RegisterMod('Frozen Module Contract',1)
local state=require('lib.state')
local function flag(k)return Input.IsButtonTriggered(k)end
ModuleFixtureMod:AddCallback(1,function()require('lib.world')end)
ModuleFixtureMod:AddCallback(2,function()
 if flag('move')then state.cfg.x=state.cfg.x+10;ModuleFixtureMod:SaveData(require('json').encode(state.cfg))end
 if flag('fail')or flag('escape')or flag('native')or flag('binary')or flag('random')then state.cfg.amount=state.cfg.amount+10;ModuleFixtureMod:SaveData(require('json').encode(state.cfg));Isaac.RenderText('unpublished',0,0)end
 if flag('fail')then require('lib.fail')end
 if flag('escape')then pcall(require,'../outside')end
 if flag('native')then pcall(package.loadlib,'outside.dll','entry')end
 if flag('binary')then pcall(require,'lib.binary')end
 if flag('random')then pcall(require,'lib.random')end
 if flag('late')then require('lib.late').paint()else state.paint()end
 if flag('cache')then for i=1,20000 do require('lib.args')end end
end)
