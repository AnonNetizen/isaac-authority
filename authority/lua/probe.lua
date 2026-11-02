-- Observation/transport experiment. This does NOT turn the game into an authoritative client.
-- No existing mod file is changed and no persistent game data is written here.
local emitNative = IsaacAuthorityNativeEmit
local consumeNative = IsaacAuthorityNativeConsume
local role = IsaacAuthorityRole or "capture"
local json = require("json")
local probe = RegisterMod("Isaac Authority Research Observer", 1)
local stopped, replaying, collecting = false, false, false
local commands, restores = {}, {}
local nativeRenderText = Isaac.RenderText
local entityIds, nextId = {}, 1
local assets = setmetatable({}, { __mode = "k" })
local wrapped = setmetatable({}, { __mode = "k" })
local sequence, worldFrame, remote = 0, 0, nil
local previewSprites, previewFonts = {}, {}
local truncated, unsupported = 0, {}
local gameRoot = (IsaacAuthorityGameRoot or ""):gsub("\\", "/"):gsub("/+$", "")
local function assetPath(path)
    local normalized = tostring(path):gsub("\\", "/")
    if gameRoot ~= "" and normalized:sub(1, #gameRoot + 1):lower() == (gameRoot .. "/"):lower() then
        normalized = normalized:sub(#gameRoot + 2)
    end
    return normalized
end

local function emit(kind, frame, body)
    local ok, text = pcall(json.encode, { kind = kind, frame = frame, body = body })
    if ok then emitNative(text) end
end
local function tryRead(fn, fallback)
    local ok, value = pcall(fn)
    if ok and value ~= nil then return value end
    return fallback
end
local function vector(v) return { x = v.X, y = v.Y } end
local function color(c)
    -- Sprite Color and font KColor use different names in J460.
    return { r = c.R or c.Red, g = c.G or c.Green, b = c.B or c.Blue, a = c.A or c.Alpha,
             ro = c.RO or 0, go = c.GO or 0, bo = c.BO or 0 }
end
local function textBytes(text)
    return tostring(text):gsub(".", function(c) return string.format("%02x", string.byte(c)) end)
end
local function fromTextBytes(text)
    return text:gsub("..", function(pair) return string.char(tonumber(pair, 16)) end)
end
local function record(command)
    if collecting and not replaying and not stopped then
        if #commands < 8192 then commands[#commands + 1] = command else truncated = truncated + 1 end
    end
end
local function wrap(target, name, builder)
    if type(target) ~= "table" or type(target[name]) ~= "function" then return false end
    if not wrapped[target] then wrapped[target] = {} end
    if wrapped[target][name] then return true end
    local original = target[name]
    local replacement = function(...)
        if not stopped and not replaying then
            local ok, command = pcall(builder, ...)
            if ok and command then record(command) end
        end
        return original(...)
    end
    target[name] = replacement
    wrapped[target][name] = true
    restores[#restores + 1] = function()
        if target[name] == replacement then target[name] = original end
    end
    return true
end
local function metatableFor(object)
    local mt = tryRead(function()
        if IsaacAuthorityNativeMetatable then return IsaacAuthorityNativeMetatable(object) end
        if debug and debug.getmetatable then return debug.getmetatable(object) end
        return getmetatable(object)
    end, nil)
    if type(mt) ~= "table" then return nil end
    return mt
end
local function watch(object, name, builder)
    if IsaacAuthorityNativeWatch then
        return IsaacAuthorityNativeWatch(object, name, function(...)
            if stopped or replaying then return end
            local command = builder(...)
            if command then record(command) end
        end)
    end
    -- Fixture/fallback only. Never replace a native class method field: its dispatcher expects C functions.
    if object == Isaac then return wrap(Isaac, name, builder) end
    local mt = metatableFor(object)
    if not mt then return false end
    local original = tryRead(function() return object[name] end, nil)
    if type(original) ~= "function" then return false end
    local layer = wrapped[mt]
    if not layer then
        local oldIndex = mt.__index
        if type(oldIndex) ~= "function" and type(oldIndex) ~= "table" then return false end
        layer = { methods = {} }; wrapped[mt] = layer
        local index = function(self, key)
            if layer.methods[key] then return layer.methods[key] end
            if type(oldIndex) == "function" then return oldIndex(self, key) end
            return oldIndex[key]
        end
        rawset(mt, "__index", index)
        restores[#restores + 1] = function() if mt.__index == index then rawset(mt, "__index", oldIndex) end end
    end
    if layer.methods[name] then return true end
    layer.methods[name] = function(...)
        if not stopped and not replaying then
            local ok, command = pcall(builder, ...)
            if ok and command then record(command) end
        end
        return original(...)
    end
    return true
end

local textHook = watch(Isaac, "RenderText", function(text, x, y, r, g, b, a)
    return { op = "text", text_hex = textBytes(text), x = x, y = y,
             color = { r = r, g = g, b = b, a = a } }
end)

local function hookSprite()
    local object = tryRead(function() return Sprite() end, nil)
    if not object then return false end
    watch(object, "Load", function(self, filename)
        assets[self] = { asset = assetPath(filename), sheets = {} }
    end)
    watch(object, "ReplaceSpritesheet", function(self, layer, filename)
        local a = assets[self] or { asset = "", sheets = {} }; assets[self] = a
        a.sheets[tostring(layer)] = assetPath(filename)
    end)
    local function descriptor(self, position, layer, clamp1, clamp2)
        local a = assets[self]
        local filename = a and a.asset or tryRead(function() return self:GetFilename() end, "")
        return { op = "sprite", asset = assetPath(filename), sheets = a and a.sheets or {},
                 animation = self:GetAnimation(), sprite_frame = self:GetFrame(),
                 position = vector(position), scale = vector(self.Scale), offset = vector(self.Offset),
                 rotation = self.Rotation, flip_x = self.FlipX, flip_y = self.FlipY,
                 color = color(self.Color), layer = layer,
                 clamp1 = clamp1 and vector(clamp1) or nil, clamp2 = clamp2 and vector(clamp2) or nil }
    end
    local render = watch(object, "Render", function(self, position, clamp1, clamp2)
        return descriptor(self, position, nil, clamp1, clamp2)
    end)
    watch(object, "RenderLayer", function(self, layer, position, clamp1, clamp2)
        return descriptor(self, position, layer, clamp1, clamp2)
    end)
    return render
end
local function hookFont()
    local object = tryRead(function() return Font() end, nil)
    if not object then return false end
    watch(object, "Load", function(self, filename) assets[self] = { asset = assetPath(filename) } end)
    local count = 0
    for _, method in ipairs({"DrawString", "DrawStringUTF8", "DrawStringScaled", "DrawStringScaledUTF8"}) do
        -- J460's compatibility functions all call the raw C DrawString with (sx,sy,KColor,settings).
        local nativeSignature = IsaacAuthorityNativeWatch ~= nil and method == "DrawString"
        local scaled = nativeSignature or method == "DrawStringScaled" or method == "DrawStringScaledUTF8"
        if watch(object, method, function(self, text, x, y, ...)
            local args = {...}
            local sx, sy, c, width, center
            if scaled then sx, sy, c, width, center = args[1], args[2], args[3], args[4], args[5]
            else sx, sy, c, width, center = 1, 1, args[1], args[2], args[3] end
            local a = assets[self]
            if not a then unsupported.font_asset_unknown = true end
            local settings
            if nativeSignature then
                local nativeSettings = args[4]
                settings = {
                    alignment = nativeSettings:GetAlignment(),
                    line_height = nativeSettings:GetLineHeightModifier(),
                    max_characters = nativeSettings:GetMaxCharacters(),
                    missing_character = nativeSettings:GetMissingCharacterOverride(),
                    auto_wrap = nativeSettings:IsAutoWrapEnabled(),
                    truncation = nativeSettings:IsTruncationEnabled()
                }
                width, center = nil, nil
            end
            return { op = "font", method = method, asset = a and a.asset or "", text_hex = textBytes(text),
                     x = x, y = y, sx = sx, sy = sy, color = color(c), width = width, center = center,
                     native_signature = nativeSignature, settings = settings }
        end) then count = count + 1 end
    end
    return count > 0
end
local spriteHook = tryRead(hookSprite, false)
local fontHook = tryRead(hookFont, false)
emit("event", 0, { name = "capture_hooks", sprite = spriteHook, font = fontHook, text = textHook,
                   native_entry_hooks = IsaacAuthorityNativeWatch ~= nil,
                   private_lua_state_capture = false, per_peer_configuration_isolation = false })

local function idFor(entity)
    if not entity then return nil end
    local identity = tostring(GetPtrHash(entity)) .. ":" .. tostring(entity.InitSeed)
    local id = entityIds[identity]
    if not id then id = nextId; nextId = nextId + 1; entityIds[identity] = id end
    return id, identity
end
local function captureWorld()
    local game = Game()
    local entities, present, keys = {}, {}, {}
    local source = Isaac.GetRoomEntities()
    for _, entity in ipairs(source) do
        local id, key = idFor(entity); present[id] = true; keys[key] = true
    end
    for _, entity in ipairs(source) do
        local id = idFor(entity)
        local p, v = entity.Position, entity.Velocity
        local sprite = entity:GetSprite()
        local e = { id = id, type = entity.Type, variant = entity.Variant, subtype = entity.SubType,
                    x = p.X, y = p.Y, vx = v.X, vy = v.Y, seed = entity.InitSeed,
                    hp = entity.HitPoints, max_hp = entity.MaxHitPoints,
                    asset = assetPath(tryRead(function() return sprite:GetFilename() end, "")),
                    animation = sprite:GetAnimation(), sprite_frame = sprite:GetFrame() }
        local parent, spawner = idFor(entity.Parent), idFor(entity.SpawnerEntity)
        if parent and present[parent] then e.parent = parent end
        if spawner and present[spawner] then e.spawner = spawner end
        local player = entity:ToPlayer()
        if player then
            e.player = { controller = player.ControllerIndex, character = player:GetPlayerType(),
                         hearts = player:GetHearts(), soul_hearts = player:GetSoulHearts(),
                         coins = player:GetNumCoins(), bombs = player:GetNumBombs(), keys = player:GetNumKeys() }
        end
        entities[#entities + 1] = e
    end
    local removed = {}
    for key, id in pairs(entityIds) do if not keys[key] then removed[#removed + 1] = id; entityIds[key] = nil end end
    table.sort(entities, function(a, b) return a.id < b.id end)
    worldFrame = game:GetFrameCount()
    emit("world", worldFrame, { entities = entities, removed = removed,
        room = game:GetLevel():GetCurrentRoomIndex(), stage = game:GetLevel():GetStage(),
        seed = game:GetSeeds():GetStartSeed(), complete_native_snapshot = false })
end
local function stopObserver()
    if stopped then return end
    stopped, collecting = true, false
    for i = #restores, 1, -1 do pcall(restores[i]) end
    if IsaacAuthorityNativeStopped then IsaacAuthorityNativeStopped() end
    -- Keep inert callbacks until game exit. Removing a callback while its registry is being iterated is avoided.
end
probe:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if stopped then return end
    local text = consumeNative()
    remote = tryRead(function() return json.decode(text) end, nil)
    if remote and remote.stop then stopObserver(); return end
    sequence = sequence + 1
    if sequence % 3 == 0 then
        local ok, err = pcall(captureWorld)
        if not ok then emit("event", 0, { name = "world_capture_error", error = tostring(err) }) end
        local inputs = {}
        for action = 0, 15 do inputs[tostring(action)] = Input.GetActionValue(action, 0) end
        emit("input", worldFrame, { actions = inputs, native_player_input_injection = false })
    end
    commands, collecting = {}, true
end)

local function toColor(c) return Color(c.r or 1, c.g or 1, c.b or 1, c.a or 1, c.ro or 0, c.go or 0, c.bo or 0) end
local function previewDraw(command)
    local text = command.text_hex and fromTextBytes(command.text_hex) or command.text
    if command.op == "text" then
        local c = command.color
        nativeRenderText(text, command.x, command.y, c.r, c.g, c.b, c.a)
    elseif command.op == "font" and command.asset ~= "" then
        local font = previewFonts[command.asset]
        if not font then font = Font(); font:Load(command.asset); previewFonts[command.asset] = font end
        local c = command.color
        local kcolor = KColor(c.r, c.g, c.b, c.a)
        if command.native_signature then
            local settings = FontRenderSettings()
            local s = command.settings
            settings:SetAlignment(s.alignment)
            settings:SetLineHeightModifier(s.line_height)
            settings:SetMaxCharacters(s.max_characters)
            settings:SetMissingCharacterOverride(s.missing_character)
            settings:EnableAutoWrap(s.auto_wrap)
            settings:EnableTruncation(s.truncation)
            font:DrawString(text, command.x, command.y, command.sx, command.sy, kcolor, settings)
        elseif command.method == "DrawStringScaled" or command.method == "DrawStringScaledUTF8" then
            font[command.method](font, text, command.x, command.y, command.sx, command.sy, kcolor, command.width or 0, command.center or false)
        else font[command.method](font, text, command.x, command.y, kcolor, command.width or 0, command.center or false) end
    elseif command.op == "sprite" and command.asset ~= "" then
        local key = command.asset .. json.encode(command.sheets or {})
        local sprite = previewSprites[key]
        if not sprite then
            sprite = Sprite(); sprite:Load(command.asset, true)
            for layer, path in pairs(command.sheets or {}) do sprite:ReplaceSpritesheet(tonumber(layer), path) end
            sprite:LoadGraphics(); previewSprites[key] = sprite
        end
        sprite:SetFrame(command.animation, command.sprite_frame)
        sprite.Scale = Vector(command.scale.x, command.scale.y)
        sprite.Offset = Vector(command.offset.x, command.offset.y)
        sprite.Rotation, sprite.FlipX, sprite.FlipY, sprite.Color = command.rotation, command.flip_x, command.flip_y, toColor(command.color)
        local p = Vector(command.position.x, command.position.y)
        local clamp1 = command.clamp1 and Vector(command.clamp1.x, command.clamp1.y) or Vector(0, 0)
        local clamp2 = command.clamp2 and Vector(command.clamp2.x, command.clamp2.y) or Vector(0, 0)
        if command.layer ~= nil then sprite:RenderLayer(command.layer, p, clamp1, clamp2)
        else sprite:Render(p, clamp1, clamp2) end
    end
end
probe:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    if stopped then return end
    local control = tryRead(function() return json.decode(consumeNative()) end, nil)
    if control and control.stop then stopObserver(); return end
    -- Menus can render while game updates are paused; refresh remote overlay state here too.
    if control then remote = control end
    -- A cached function saved before native hook installation must also hit the native observer.
    -- Do this once on the first game render, inside a real render context.
    if not unsupported.cached_entry_test_done then
        local before = #commands
        local previousCollecting = collecting; collecting = true
        nativeRenderText("", 0, 0, 1, 1, 1, 0)
        emit("event", worldFrame, { name = "cached_native_entry_selftest", captured = #commands == before + 1 })
        collecting = previousCollecting
        unsupported.cached_entry_test_done = true
    end
    collecting = false
    if sequence % 3 == 0 then
        emit("draw", worldFrame, { commands = commands, truncated = truncated, unsupported = unsupported,
                                   complete_render_capture = false })
    end
    commands = {}
    -- Engine rendering outside these Lua bindings is not captured.
    -- A preview is an explicitly marked overlay; normal game simulation remains active.
    replaying = true
    if role == "preview" and remote and remote.draw and remote.draw.commands then
        for _, command in ipairs(remote.draw.commands) do pcall(previewDraw, command) end
    end
    nativeRenderText("AUTHORITY RESEARCH: OBSERVER / NOT PLAYABLE", 12, 12, 1, 0.4, 0.15, 1)
    replaying = false
    collecting = true
end)
