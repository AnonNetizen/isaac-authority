-- Deterministic CLI API backend. This is SDK code; installed mod sources stay unchanged.
local make = __authority_ui_userdata
__authority_ui_userdata = nil
local function object(kind,fields,methods)
    local aliases=kind=='KColor' and {Red='R',Green='G',Blue='B',Alpha='A'} or {}
    return make(kind,setmetatable(fields,{__index=function(_,key)
        if aliases[key] then return fields[aliases[key]] end
        if methods[key] then return methods[key] end
        return unsupported(kind..'.'..tostring(key))
    end,__newindex=function(t,key,value)if aliases[key] then rawset(t,aliases[key],value)else rawset(t,key,value)end end}))
end
local vectorMethods={}
local function binary(a,b,fn)
    local ax,ay=type(a)=='number' and a or a.X,type(a)=='number' and a or a.Y
    local bx,by=type(b)=='number' and b or b.X,type(b)=='number' and b or b.Y
    return Vector(fn(ax,bx),fn(ay,by))
end
vectorMethods.__add=function(a,b)return binary(a,b,function(x,y)return x+y end)end
vectorMethods.__sub=function(a,b)return binary(a,b,function(x,y)return x-y end)end
vectorMethods.__mul=function(a,b)return binary(a,b,function(x,y)return x*y end)end
vectorMethods.__div=function(a,b)return binary(a,b,function(x,y)return x/y end)end
vectorMethods.__unm=function(a)return Vector(-a.X,-a.Y)end
vectorMethods.__eq=function(a,b)return a.X==b.X and a.Y==b.Y end
vectorMethods.__tostring=function(a)return '('..a.X..', '..a.Y..')'end
vectorMethods.LengthSquared=function(a)return a.X*a.X+a.Y*a.Y end
vectorMethods.Length=function(a)return math.sqrt(a:LengthSquared())end
vectorMethods.Normalized=function(a)local n=a:Length();if n==0 then return Vector(0,0)end;return a/n end
vectorMethods.Resized=function(a,n)return a:Normalized()*n end
vectorMethods.Distance=function(a,b)return (a-b):Length()end
vectorMethods.Rotated=function(a,d)local r=math.rad(d);return Vector(a.X*math.cos(r)-a.Y*math.sin(r),a.X*math.sin(r)+a.Y*math.cos(r))end
Vector=setmetatable({Zero=nil},{__call=function(_,x,y)return object('Vector',{X=x or 0,Y=y or 0},vectorMethods)end})
Vector.Zero=Vector(0,0)
Vector.FromAngle=function(d)return Vector(1,0):Rotated(d)end
local colorMethods={}
colorMethods.__tostring=function(a)return a.R..','..a.G..','..a.B..','..a.A end
KColor=function(r,g,b,a)return object('KColor',{R=r,G=g,B=b,A=a},colorMethods)end
Color=setmetatable({},{__call=function(_,r,g,b,a,ro,go,bo)return object('Color',{R=r,G=g,B=b,A=a,RO=ro or 0,GO=go or 0,BO=bo or 0},colorMethods)end})
Color.Default=Color(1,1,1,1)
local fontMethods={}
fontMethods.Load=function(self,path,compat)
    if compat~=nil and compat~='' then return unsupported('Font.Load.compatibility_argument')end
    self.resource=service('ui.resource','font',path).id;self.filename=path;self.loaded=true;return true
end
fontMethods.IsLoaded=function(self)return self.loaded end
fontMethods.SetMissingCharacter=function(self,c)self.missing=c end
local function hex(text)local out={};for i=1,#text do out[i]=string.format('%02x',text:byte(i))end;return table.concat(out)end
fontMethods.GetStringWidth=function(self,text)
    if not self.loaded then return unsupported('Font.GetStringWidth.unloaded')end
    return service('ui.font.width',self.resource,hex(text),self.missing)
end
fontMethods.GetStringWidthUTF8=fontMethods.GetStringWidth
fontMethods.DrawString=function()return unsupported('Font.DrawString.capture_not_installed')end
fontMethods.DrawStringScaled=fontMethods.DrawString
fontMethods.DrawStringUTF8=fontMethods.DrawString
fontMethods.DrawStringScaledUTF8=fontMethods.DrawString
Font=function()return object('Font',{resource='',filename='',loaded=false,missing=63},fontMethods)end
local settingsMethods={SetAlignment=function(self,value)self.Alignment=value end}
FontRenderSettings=function()return object('FontRenderSettings',{Alignment=0},settingsMethods)end
local spriteMethods={}
spriteMethods.Load=function(self,path,graphics)
    local resource=service('ui.resource','sprite',path)
    self.resource=resource.id;self.filename=path;self.animations=resource.animations
    self.animation=resource.default_animation;self.frame=0;self.loaded=true;self.graphics=graphics~=false
end
spriteMethods.Play=function(self,name,force)
    if not self.animations[name] then return unsupported('Sprite.Play.animation')end
    if force or self.animation~=name then self.animation=name;self.frame=0 end
end
spriteMethods.SetFrame=function(self,name,frame)
    if frame==nil then frame=name;name=self.animation end
    if not self.animations[name] or type(frame)~='number' or frame<0 or frame>=self.animations[name] then return unsupported('Sprite.SetFrame.range')end
    self.animation=name;self.frame=frame
end
spriteMethods.GetFrame=function(self)return self.frame end
spriteMethods.GetAnimation=function(self)return self.animation end
spriteMethods.GetFilename=function(self)return self.filename end
spriteMethods.IsLoaded=function(self)return self.loaded end
spriteMethods.IsPlaying=function(self,name)return self.animation==name and self.frame<self.animations[name]-1 end
spriteMethods.IsFinished=function(self,name)return self.animation==name and self.frame==self.animations[name]-1 end
spriteMethods.Update=function(self)
    if not self.loaded then return unsupported('Sprite.Update.unloaded')end
    self.frame=(self.frame+1)%self.animations[self.animation]
end
spriteMethods.ReplaceSpritesheet=function(self,layer,path)
    service('ui.resource','image',path);self.sheets[layer]=path
end
spriteMethods.LoadGraphics=function(self)self.graphics=true end
spriteMethods.Render=function()return unsupported('Sprite.Render.capture_not_installed')end
Sprite=function()return object('Sprite',{resource='',filename='',loaded=false,graphics=false,animation='',frame=0,
    animations={},sheets={},Scale=Vector(1,1),Offset=Vector(0,0),Color=Color(1,1,1,1),Rotation=0,FlipX=false,FlipY=false,PlaybackSpeed=1},spriteMethods)end
local bitMethods={
    __band=function(a,b)return BitSet128(a.low&b.low,a.high&b.high)end,
    __bor=function(a,b)return BitSet128(a.low|b.low,a.high|b.high)end,
    __eq=function(a,b)return a.low==b.low and a.high==b.high end}
BitSet128=function(a,b)return object('BitSet128',{low=a or 0,high=b or 0},bitMethods)end
-- Initialization needs an ItemConfig handle; field queries remain explicit failures
-- until a scene has supplied matching immutable metadata.
Isaac.GetItemConfig=function()return guarded({},'ItemConfig.Config')end
ItemConfig=guarded({CHARGE_NORMAL=0,CHARGE_TIMED=1,CHARGE_SPECIAL=2,TAG_QUEST=1},'ItemConfig')

RoomDescriptor=guarded({},'RoomDescriptor')
