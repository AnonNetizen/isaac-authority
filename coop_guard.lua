-- ISAAC_COOP_STABILITY_V2_BEGIN
-- Keep cosmetic entities out of network simulation. Do not bypass desync checks.
local isaacCoopStabilityVersion = 2
local isaacCoopStabilityBlocked = false
local isaacCoopStabilityDecided = false

local function isaacCoopStabilityLog(message)
    pcall(function()
        if Isaac and Isaac.DebugString then
            local frame = -1
            if Isaac.GetFrameCount then
                local okFrame, value = pcall(function()
                    return Isaac.GetFrameCount()
                end)
                if okFrame and type(value) == "number" then
                    frame = value
                end
            end
            Isaac.DebugString(
                "[ISAAC-STABILITY] v" .. tostring(isaacCoopStabilityVersion)
                .. " frame=" .. tostring(frame) .. " " .. tostring(message)
            )
        end
    end)
end

-- Count distinct main players (Jacob/Esau and other sub-forms share one owner).
local function isaacCoopStabilityOwners(count)
    local owners = {}
    local ownerCount = 0
    local remotePlayer = false
    local localityKnown = true
    for index = 0, count - 1 do
        local player = Isaac.GetPlayer(index)
        if player then
            local subPlayer = false
            if type(player.IsSubPlayer) == "function" then
                local ok, value = pcall(function()
                    return player:IsSubPlayer()
                end)
                if ok then
                    subPlayer = value == true
                end
            end
            if not subPlayer then
                local owner = player
                if type(player.GetMainTwin) == "function" then
                    local ok, value = pcall(function()
                        return player:GetMainTwin()
                    end)
                    if ok and value then
                        owner = value
                    end
                end
                local key = GetPtrHash(owner)
                if not owners[key] then
                    owners[key] = true
                    ownerCount = ownerCount + 1
                    if type(owner.IsLocalPlayer) == "function" then
                        local ok, isLocal = pcall(function()
                            return owner:IsLocalPlayer()
                        end)
                        if ok and type(isLocal) == "boolean" then
                            if not isLocal then
                                remotePlayer = true
                            end
                        else
                            localityKnown = false
                        end
                    else
                        localityKnown = false
                    end
                end
            end
        end
    end
    return ownerCount, remotePlayer, localityKnown
end

local function isaacCoopStabilityDetect()
    if not REPENTANCE_PLUS then
        return false, "older_game", 0
    end

    local okGame, count = pcall(function()
        return Game():GetNumPlayers()
    end)
    if not okGame or type(count) ~= "number" then
        return false, "detection_unavailable", 0
    end
    if count < 2 then
        return false, "single_player", count
    end

    local okOwners, ownerCount, remotePlayer, localityKnown = pcall(isaacCoopStabilityOwners, count)
    if not okOwners then
        return true, "coop_fallback", count
    end
    if ownerCount <= 1 then
        return false, "single_owner", count
    end
    if localityKnown then
        if remotePlayer then
            return true, "remote_player", count
        end
        return false, "local_coop", count
    end
    -- Vanilla Lua exposes no reliable online flag: protect every multi-player
    -- co-op conservatively, including local co-op on builds without the API.
    return true, "coop_fallback", count
end

local function isaacCoopStabilityShouldSkip()
    if isaacCoopStabilityBlocked then
        return true
    end

    local ok, shouldBlock, reason, count = pcall(isaacCoopStabilityDetect)
    if not ok then
        if not isaacCoopStabilityDecided then
            isaacCoopStabilityDecided = true
            isaacCoopStabilityLog("detection_error " .. tostring(shouldBlock) .. " indicators=kept")
        end
        return false
    end

    if not isaacCoopStabilityDecided then
        isaacCoopStabilityDecided = true
        isaacCoopStabilityLog(
            "active reason=" .. tostring(reason)
            .. " players=" .. tostring(count)
            .. " indicators=" .. (shouldBlock and "disabled" or "kept")
        )
    end

    if shouldBlock then
        -- Stay disabled until a new run, including when a peer leaves mid-run.
        isaacCoopStabilityBlocked = true
        isaacCoopStabilityLog(
            "blocked reason=" .. tostring(reason)
            .. " players=" .. tostring(count) .. " indicators=disabled"
        )
    end
    return isaacCoopStabilityBlocked
end
-- ISAAC_COOP_STABILITY_V2_END
