-- ISAAC_COOP_STABILITY_V1_BEGIN
-- Keep cosmetic entities out of network simulation. Do not bypass desync checks.
local isaacCoopStabilityBlocked = false

local function isaacCoopStabilityDetect()
    if not REPENTANCE_PLUS then
        return false, "older_game"
    end

    local ok, shouldBlock, reason = pcall(function()
        local count = Game():GetNumPlayers()
        if count < 2 then
            return false, "single_player"
        end

        local owners = {}
        local ownerCount = 0
        local remotePlayer = false
        local localityAvailable = true
        for index = 0, count - 1 do
            local player = Isaac.GetPlayer(index)
            if player and not player:IsSubPlayer() then
                local owner = player:GetMainTwin() or player
                local key = GetPtrHash(owner)
                if not owners[key] then
                    owners[key] = true
                    ownerCount = ownerCount + 1
                    local supported, isLocal = pcall(function()
                        return owner:IsLocalPlayer()
                    end)
                    if supported and type(isLocal) == "boolean" then
                        remotePlayer = remotePlayer or not isLocal
                    else
                        localityAvailable = false
                    end
                end
            end
        end

        if localityAvailable then
            return remotePlayer, "remote_player"
        end
        -- Vanilla Lua lacks a reliable online flag. Protect co-op conservatively,
        -- counting main players rather than Jacob/Esau or multi-form characters.
        return ownerCount > 1, "coop_fallback"
    end)

    if not ok then
        return false, "detection_unavailable"
    end
    return shouldBlock, reason
end

local function isaacCoopStabilityShouldSkip()
    if isaacCoopStabilityBlocked then
        return true
    end
    local shouldBlock, reason = isaacCoopStabilityDetect()
    if shouldBlock then
        -- Stay disabled until a new run, including when a peer leaves mid-run.
        isaacCoopStabilityBlocked = true
        pcall(function()
            Isaac.DebugString("[ISAAC-STABILITY] v1 Watch out, laser! indicators disabled: " .. reason)
        end)
    end
    return isaacCoopStabilityBlocked
end
-- ISAAC_COOP_STABILITY_V1_END
