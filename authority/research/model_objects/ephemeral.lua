local m=RegisterMod('Ephemeral Object',1)
m:AddCallback(2,function()local s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',false);Isaac.RenderText(s:GetDefaultAnimationName(),0,0)end)
