-- Host-side Lua context for the offline API transcript experiment, NOT the live game bootstrap.
local api, data, draw, unsupported = __api, __data, __draw, __unsupported
local jsonEncode, jsonDecode, moduleSource, budget = __json_encode, __json_decode, __module_source, __budget
local originalLoad, originalRawset, debugHook, debugInfo = load, rawset, debug.sethook, debug.getinfo
local debugTraceback = debug.traceback -- Lupa also needs this for protected exception conversion.
__api, __data, __draw, __unsupported = nil, nil, nil, nil
__json_encode, __json_decode, __module_source, __budget = nil, nil, nil, nil
python = nil
local callbacks, loaded, sealed = {}, {}, setmetatable({}, {__mode='k'})
local function guarded(t, prefix)
    return setmetatable(t, {__index=function(_, key) return unsupported(prefix..'.'..tostring(key)) end})
end
local json = {encode=function(value) return jsonEncode(value) end,
              decode=function(value) return jsonDecode(value) end}
loaded.json = json
function require(name)
    if loaded[name] ~= nil then
        if loaded[name] == '__loading__' then error('cyclic module: '..name) end
        return loaded[name]
    end
    local source, filename = moduleSource(name)
    local fn = assert(originalLoad(source, filename, 't', _G))
    loaded[name] = '__loading__'
    local result = fn()
    loaded[name] = result == nil and true or result
    return loaded[name]
end
function include(name)
    local source, filename = moduleSource(name)
    return assert(originalLoad(source, filename, 't', _G))()
end
loadfile=function() return unsupported('loadfile') end
dofile=function() return unsupported('dofile') end
load=function(source, name, mode, env)
    if type(source) ~= 'string' or (mode and mode ~= 't') then return unsupported('load.binary_or_reader') end
    return originalLoad(source, name, 't', env or _G)
end
package=guarded({loaded=loaded}, 'package')
io=guarded({}, 'io')
os=guarded({clock=function() return api('os.clock') end, time=function() return api('os.time') end}, 'os')
debug=guarded({getinfo=debugInfo,traceback=debugTraceback}, 'debug')
math.random=function(...) return api('math.random', ...) end
math.randomseed=function(seed) return api('math.randomseed', seed) end
REPENTANCE, REPENTANCE_PLUS, REPENTOGON = true, true, false
ModCallbacks={MC_POST_UPDATE=1, MC_POST_RENDER=2}
CallbackPriority={EARLY=-100, DEFAULT=0, LATE=100}
Keyboard={KEY_L=76, KEY_M=77}
for _,name in ipairs({'Font','Sprite','RNG','Vector','Color','KColor','BitSet128'}) do
    _G[name]=function() return unsupported(name..'.native_adapter') end
end

function RegisterMod(name, version)
    if version ~= 1 then return unsupported('RegisterMod.version') end
    local mod={Name=name}
    function mod:AddPriorityCallback(id, priority, fn, param)
        if type(fn) ~= 'function' or type(priority) ~= 'number' then error('invalid callback') end
        local list=callbacks[id] or {}; callbacks[id]=list
        local item={mod=self,fn=fn,priority=priority,param=param}
        local at=#list+1
        while at>1 and list[at-1].priority>priority do at=at-1 end
        table.insert(list,at,item)
    end
    function mod:AddCallback(id, fn, param) self:AddPriorityCallback(id,0,fn,param) end
    function mod:RemoveCallback(id, fn)
        local list=callbacks[id] or {}
        for i=#list,1,-1 do if list[i].fn==fn and list[i].mod==self then table.remove(list,i) end end
    end
    function mod:HasData() return data('has',name) end
    function mod:LoadData() return data('load',name) end
    function mod:SaveData(value) return data('save',name,value) end
    function mod:RemoveData() return data('remove',name) end
    return mod
end

local players={}
local function player(index)
    if index~=0 and index~=1 then return unsupported('Player.index') end
    if players[index] then return players[index] end
    local methods={ControllerIndex=index,
        AddCoins=function(self,amount) return api('Player.AddCoins',index,amount) end,
        GetNumCoins=function(self) return api('Player.GetNumCoins',index) end}
    local object=setmetatable({}, {
        __index=function(_,key)
            if methods[key]~=nil then return methods[key] end
            return unsupported('Player.'..tostring(key))
        end,
        __newindex=function(_,key) return unsupported('Player.property_write:'..tostring(key)) end})
    sealed[object]=true; players[index]=object; return object
end
rawset=function(object,key,value)
    if sealed[object] then return unsupported('Player.raw_property_write:'..tostring(key)) end
    return originalRawset(object,key,value)
end
Isaac=guarded({
    GetTime=function() return api('Isaac.GetTime') end,
    GetPlayer=player,
    RenderText=function(text,x,y,r,g,b,a) return draw(text,x,y,r,g,b,a) end,
    DebugString=function(text) return data('log',text) end}, 'Isaac')
local game=guarded({GetFrameCount=function() return api('Game.GetFrameCount') end}, 'Game')
Game=function() return game end
Input=guarded({
    IsButtonTriggered=function(key,controller) return data('triggered',key,controller) end,
    IsButtonPressed=function(key,controller) return data('pressed',key,controller) end,
    GetActionValue=function(action,controller) return data('action',action,controller) end}, 'Input')

function __execute(source, filename)
    local fn=assert(originalLoad(source,filename,'t',_G))
    debugHook(function() budget() end,'',1000)
    local ok,result=pcall(fn)
    debugHook()
    if not ok then error(tostring(result)) end
    return result
end
function __dispatch(id)
    debugHook(function() budget() end,'',1000)
    local ok,result=pcall(function()
        for _,item in ipairs(callbacks[id] or {}) do
            local value=item.fn(item.mod)
            if value~=nil then return value end
        end
    end)
    debugHook()
    if not ok then error(tostring(result)) end
    return result
end
