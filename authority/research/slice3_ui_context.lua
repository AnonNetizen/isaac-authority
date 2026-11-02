-- Host-side native mod research context. World APIs below are the coin MODEL only.
local service, internalDebug = __authority_service, __authority_debug
local nativeItemConfig = __authority_item_config
__authority_service, __authority_debug = nil, nil
__authority_item_config = nil
local originalLoad, originalRawset = load, rawset
local originalDate = __authority_date
__authority_date = nil
local callbacks, loaded, sealed = {}, {}, setmetatable({}, {__mode='k'})
local function unsupported(name) return service('unsupported', name) end
local function guarded(t, name)
    return setmetatable(t, {__index=function(_,key) return unsupported(name..'.'..tostring(key)) end})
end
local function source(name, kind)
    local caller=internalDebug.getinfo(3, 'S')
    local code, filename=service('module',name,kind,caller and caller.source or '')
    if not code then error(filename,3) end
    return assert(originalLoad(code,filename,'t',_G))
end
local json={encode=function(value) return service('json.encode',value) end,
            decode=function(value) return service('json.decode',value) end}
loaded.json=json
function require(name)
    if type(name)~='string' then error('module name must be a string') end
    if loaded[name]~=nil then
        if loaded[name]=='__loading__' then error('cyclic module: '..name) end
        return loaded[name]
    end
    local fn=source(name,'require'); loaded[name]='__loading__'
    local ok,value=pcall(fn)
    if not ok then loaded[name]=nil;error(value) end
    loaded[name]=value==nil and true or value
    return loaded[name]
end
function include(name) return source(name,'require')() end
function dofile(name) return source(name,'dofile')() end
loadfile=function() return unsupported('loadfile') end
load=function(code,name,mode,env)
    if type(code)~='string' or (mode and mode~='t') then return unsupported('load.binary_or_reader') end
    return originalLoad(code,name,'t',env or _G)
end
package=guarded({loaded=loaded},'package')
io=guarded({},'io')
debug=guarded({getinfo=internalDebug.getinfo,traceback=internalDebug.traceback},'debug')
coroutine=guarded({},'coroutine')
os=guarded({clock=function() return service('world','os.clock') end,
            time=function() return service('world','os.time') end,
            date=function(format,timestamp)
                format=format or '%c'
                if type(format)~='string' or #format>256 then error('date format limit') end
                if timestamp==nil then timestamp=service('world','os.time') end
                return originalDate(format,timestamp)
            end},'os')
math.random=function(...) return service('world','math.random',...) end
math.randomseed=function(...) return service('world','math.randomseed',...) end
print=function(...) local parts={...};for i=1,#parts do parts[i]=tostring(parts[i]) end;return service('log',table.concat(parts,'\t')) end
REPENTANCE,REPENTANCE_PLUS,REPENTOGON=true,true,false
ModCallbacks=ModCallbacks or {MC_POST_UPDATE=1,MC_POST_RENDER=2}
CallbackPriority=CallbackPriority or {EARLY=-100,DEFAULT=0,LATE=100}
Keyboard=Keyboard or {KEY_L=76,KEY_M=77}

-- Match the callback table contract in J460 resources/scripts/main.lua.
-- Built-in game callback activation is deliberately not forwarded to the engine.
local callbackMeta={__matchParams=function(a,b) return not a or not b or a==-1 or b==-1 or a==b end}
local function getCallbacks(id,create)
    if create and not callbacks[id] then callbacks[id]=setmetatable({},callbackMeta) end
    return callbacks[id] or {}
end
local function runCallback(id,param,...)
    local list=callbacks[id]
    if list then
        local match=getmetatable(list).__matchParams or callbackMeta.__matchParams
        for _,item in ipairs(list) do
            if match(param,item.Param) then
                local result=item.Function(item.Mod,...)
                if result~=nil then return result end
            end
        end
    end
end
local function add(mod,id,priority,fn,param)
    if type(fn)~='function' or type(priority)~='number' then error('invalid callback') end
    local list=getCallbacks(id,true)
    local item={Mod=mod,Function=fn,Priority=priority,Param=param};local at=#list+1
    while at>1 and list[at-1].Priority>priority do at=at-1 end
    table.insert(list,at,item)
end
local function remove(mod,id,fn)
    local list=callbacks[id] or {}
    for i=#list,1,-1 do if list[i].Function==fn then table.remove(list,i) end end
end
local players={}
local function player(index)
    if index~=0 and index~=1 then return unsupported('Player.index') end
    if players[index] then return players[index] end
    local methods={ControllerIndex=index,
        AddCoins=function(_,amount) return service('world','Player.AddCoins',index,amount) end,
        GetNumCoins=function() return service('world','Player.GetNumCoins',index) end}
    local object=setmetatable({}, {
        __index=function(_,key) if methods[key]~=nil then return methods[key] end;return unsupported('Player.'..tostring(key)) end,
        __newindex=function(_,key) return unsupported('Player.property_write:'..tostring(key)) end})
    sealed[object]='Player';players[index]=object;return object
end
rawset=function(object,key,value)
    if sealed[object] then return unsupported(sealed[object]..'.raw_property_write:'..tostring(key)) end
    return originalRawset(object,key,value)
end
Isaac=guarded({
    RegisterMod=function(mod,name,version)
        if type(name)~='string' or version~=1 then return unsupported('RegisterMod.arguments') end
        mod.Name=name
    end,
    AddCallback=function(mod,id,fn,param) return add(mod,id,0,fn,param) end,
    AddPriorityCallback=add,RemoveCallback=remove,
    GetCallbacks=getCallbacks,
    RunCallback=function(id,...) return runCallback(id,nil,...) end,
    RunCallbackWithParam=runCallback,
    HasModData=function(mod) return service('data','has',mod.Name) end,
    LoadModData=function(mod) return service('data','load',mod.Name) end,
    SaveModData=function(mod,value) return service('data','save',mod.Name,value) end,
    RemoveModData=function(mod) return service('data','remove',mod.Name) end,
    GetTime=function() return service('world','Isaac.GetTime') end,
    GetPlayer=player,
    GetItemConfig=function(...)
        if not nativeItemConfig then return unsupported('Isaac.GetItemConfig') end
        return nativeItemConfig(...)
    end,
    DebugString=function(text) return service('log',text) end,
    RenderText=function(...) return service('draw.text',...) end
},'Isaac')
function RegisterMod(name,version)
    local mod={Name=name,
        AddCallback=function(self,...) return Isaac.AddCallback(self,...) end,
        AddPriorityCallback=function(self,...) return Isaac.AddPriorityCallback(self,...) end,
        RemoveCallback=function(self,...) return Isaac.RemoveCallback(self,...) end,
        HasData=function(self) return Isaac.HasModData(self) end,
        LoadData=function(self) return Isaac.LoadModData(self) end,
        SaveData=function(self,...) return Isaac.SaveModData(self,...) end,
        RemoveData=function(self) return Isaac.RemoveModData(self) end}
    Isaac.RegisterMod(mod,name,version);return mod
end
local game=guarded({GetFrameCount=function() return service('world','Game.GetFrameCount') end},'Game')
Game=function() return game end
Input=guarded({
    IsButtonTriggered=function(...) return service('input','triggered',...) end,
    IsButtonPressed=function(...) return service('input','pressed',...) end,
    IsActionTriggered=function(...) return service('input','action_triggered',...) end,
    IsActionPressed=function(...) return service('input','action_pressed',...) end,
    GetActionValue=function(...) return service('input','action',...) end
},'Input')
Options=setmetatable({}, {
    __index=function(_,key) return service('options.get',key) end,
    __newindex=function(_,key,value) return service('options.set',key,value) end,
    __metatable='private personal options'
})
sealed[Options]='Options'
for _,name in ipairs({'SFXManager','MusicManager','RNG','EntityRef','FontRenderSettings'}) do
    if _G[name]==nil then _G[name]=function() return unsupported(name..'.native_adapter') end end
end
local function execute(fn,...)
    local args=table.pack(...)
    internalDebug.sethook(function() service('budget') end,'',1000)
    local ok,value=pcall(function() return fn(table.unpack(args,1,args.n)) end)
    internalDebug.sethook()
    if not ok then error(value) end
    return value
end
function __execute(source,filename)
    return execute(assert(originalLoad(source,filename,'t',_G)))
end
function __load_entry(index)
    local code,filename=service('entry',index)
    return __execute(code,filename)
end
function __dispatch(id,param,...)
    return execute(runCallback,id,param,...)
end
function __context_summary()
    local counts={};for id,list in pairs(callbacks) do counts[tostring(id)]=#list end
    return json.encode({callbacks=counts})
end

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
