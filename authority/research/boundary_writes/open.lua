local mod=RegisterMod('Write Barrier Open Cells',1)
local counter=7
local cfg={amount=2,x=137}
local reader=function() return counter end
mod:AddCallback(2,function()
    if Input.IsButtonTriggered('change') then counter=counter+3 end
    if Input.IsButtonTriggered('aba') then counter=counter+1;counter=counter-1 end
    if Input.IsButtonTriggered('same') then counter=counter end
    Isaac.RenderText('counter='..counter..'|reader='..reader(),cfg.x,0)
end)
mod:AddCallback(3,function() counter=counter+1;Isaac.RenderText('shared='..counter,0,0) end)
-- Registered captures are still open. Exercise local register stores and growth.
counter=counter+1;counter=counter-1
local function deep(n)
    local a,b,c,d,e,f,g,h,i,j,k,l,m,n1,o,p,q,r,s,t=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
    if n==0 then collectgarbage('collect');return a+t end
    return deep(n-1)+a+t+b+c+d+e+f+g+h+i+j+k+l+m+n1+o+p+q+r+s
end
assert(deep(80)>0)
counter=counter+1;counter=counter-1
collectgarbage('collect')
