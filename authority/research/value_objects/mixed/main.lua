local m=RegisterMod('Mixed Userdata GC',1)
local anchor=Vector(17,42);local mt=getmetatable(anchor);local original=mt.__gc
m:AddCallback(2,function()
 mt.__gc=nil
 for i=1,128 do
  local temporary=Vector(i,-i);temporary=nil;collectgarbage('collect')
  local bits=BitSet128(i,0);local sprite=Sprite();sprite:Load('gfx/ui/modconfig/menu.anm2',false)
  assert(bits.l==i and sprite:GetLayerCount()==10)
 end
 mt.__gc=original;collectgarbage('collect');assert(anchor.X==17)
 Isaac.RenderText('mixed-ok',0,0)
end)
