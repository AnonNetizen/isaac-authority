#include "guest_apply.hpp"
#include <cmath>
#include <cstring>
#include <vector>

namespace ia {
namespace {

bool range_ok(uint32_t address, uint32_t size) {
    if (size == 0 || size > 8) return false;
    return static_cast<uint64_t>(address) + size <= 0x100000000ull;
}

bool read_bytes(GuestMemory& memory, uint32_t address, void* dest, uint32_t size) {
    return range_ok(address, size) && memory.read(address, dest, size);
}

bool read_u32(GuestMemory& memory, uint32_t address, uint32_t& out) {
    uint8_t bytes[4];
    if (!read_bytes(memory, address, bytes, 4)) return false;
    out = static_cast<uint32_t>(bytes[0]) | (static_cast<uint32_t>(bytes[1]) << 8) |
          (static_cast<uint32_t>(bytes[2]) << 16) | (static_cast<uint32_t>(bytes[3]) << 24);
    return true;
}

void store_f32(uint8_t* dest, float value) {
    uint32_t bits = 0;
    std::memcpy(&bits, &value, 4);
    dest[0] = static_cast<uint8_t>(bits);
    dest[1] = static_cast<uint8_t>(bits >> 8);
    dest[2] = static_cast<uint8_t>(bits >> 16);
    dest[3] = static_cast<uint8_t>(bits >> 24);
}

bool finite_pose(float x, float y, float vx, float vy, float size) {
    return std::isfinite(x) && std::isfinite(y) && std::isfinite(vx) && std::isfinite(vy) && std::isfinite(size);
}

struct Identity {
    uint32_t type{0};
    uint32_t variant{0};
    uint32_t init_seed{0};
};

struct PoseTarget {
    uint32_t address{0};
    uint64_t network_id{0};
    float x{0}, y{0}, vx{0}, vy{0}, size{0};
};

struct StagedWrite {
    uint32_t address{0};
    uint8_t size{0};
    uint8_t previous[8]{};
    uint8_t next[8]{};
};

bool ranges_overlap(uint32_t left, uint32_t left_size, uint32_t right, uint32_t right_size) {
    const uint64_t left_end = static_cast<uint64_t>(left) + left_size;
    const uint64_t right_end = static_cast<uint64_t>(right) + right_size;
    return static_cast<uint64_t>(left) < right_end && static_cast<uint64_t>(right) < left_end;
}

const NetEntity* find_id(const WorldSnapshot& world, uint64_t id) {
    for (const auto& entity : world.entities)
        if (entity.id == id) return &entity;
    return nullptr;
}

const NetEntity* find_alias(const WorldSnapshot& world, uint32_t slot) {
    for (const auto& entity : world.entities)
        if (entity.player_alias && entity.player_slot == slot) return &entity;
    return nullptr;
}

void remember_failure(GuestApplyReport& report, uint64_t network_id) {
    for (uint64_t id : report.failed_network_ids)
        if (id == network_id) return;
    if (network_id != 0) report.failed_network_ids.push_back(network_id);
}

GuestApplyReport seal(GuestApplyReport report, const RenderPlan& plan) {
    report.spawns_not_performed = plan.has_snapshot ? static_cast<uint32_t>(plan.spawns.size()) : 0;
    report.despawns_not_performed = plan.has_snapshot ? static_cast<uint32_t>(plan.despawn_ids.size()) : 0;
    report.lifecycle = (report.spawns_not_performed != 0 || report.despawns_not_performed != 0)
                           ? GuestLifecycle::not_performed
                           : GuestLifecycle::none_requested;
    report.lifecycle_performed = false;
    report.in_game = false;
    report.playable = false;
    report.complete = report.error == GuestApplyError::ok && report.pose_committed &&
                      report.lifecycle == GuestLifecycle::none_requested && !report.rollback_failed;
    if (!report.pose_committed) report.entities_written = 0;
    return report;
}

bool field_address(uint32_t base, uint32_t offset, uint32_t& out) {
    const uint64_t address = static_cast<uint64_t>(base) + offset;
    if (address > 0xffffffffull) return false;
    out = static_cast<uint32_t>(address);
    return true;
}

bool stage_bytes(std::vector<StagedWrite>& staged, GuestMemory& memory, uint32_t address, const uint8_t* data,
                 uint8_t size, GuestApplyError& error) {
    if (!range_ok(address, size)) {
        error = GuestApplyError::out_of_bounds;
        return false;
    }
    for (const StagedWrite& existing : staged) {
        if (!ranges_overlap(existing.address, existing.size, address, size)) continue;
        if (existing.address == address && existing.size == size && std::memcmp(existing.next, data, size) == 0) return true;
        error = GuestApplyError::conflict;
        return false;
    }
    StagedWrite item;
    item.address = address;
    item.size = size;
    if (!memory.read(address, item.previous, size)) {
        error = GuestApplyError::out_of_bounds;
        return false;
    }
    std::memcpy(item.next, data, size);
    staged.push_back(item);
    return true;
}

bool stage_pose(std::vector<StagedWrite>& staged, GuestMemory& memory, const PoseTarget& target, GuestApplyError& error) {
    uint8_t position[8];
    uint8_t velocity[8];
    uint8_t size[4];
    uint32_t position_at = 0;
    uint32_t velocity_at = 0;
    uint32_t size_at = 0;
    store_f32(position, target.x);
    store_f32(position + 4, target.y);
    store_f32(velocity, target.vx);
    store_f32(velocity + 4, target.vy);
    store_f32(size, target.size);
    if (!field_address(target.address, J460GuestLayout::entity_position, position_at) ||
        !field_address(target.address, J460GuestLayout::entity_velocity, velocity_at) ||
        !field_address(target.address, J460GuestLayout::entity_size, size_at)) {
        error = GuestApplyError::out_of_bounds;
        return false;
    }
    return stage_bytes(staged, memory, position_at, position, 8, error) &&
           stage_bytes(staged, memory, velocity_at, velocity, 8, error) &&
           stage_bytes(staged, memory, size_at, size, 4, error);
}

bool read_identity(GuestMemory& memory, uint32_t address, Identity& out) {
    uint32_t type_at = 0;
    uint32_t variant_at = 0;
    uint32_t seed_at = 0;
    if (!field_address(address, J460GuestLayout::entity_type, type_at) ||
        !field_address(address, J460GuestLayout::entity_variant, variant_at) ||
        !field_address(address, J460GuestLayout::entity_init_seed, seed_at)) return false;
    return read_u32(memory, type_at, out.type) && read_u32(memory, variant_at, out.variant) &&
           read_u32(memory, seed_at, out.init_seed);
}

bool identity_matches(const Identity& memory_id, const NetEntity& entity) {
    return memory_id.type == entity.type && memory_id.variant == entity.variant && memory_id.init_seed == entity.init_seed;
}

}

const char* guest_apply_error_name(GuestApplyError error) {
    switch (error) {
    case GuestApplyError::ok: return "ok";
    case GuestApplyError::no_snapshot: return "no_snapshot";
    case GuestApplyError::unknown_build: return "unknown_build";
    case GuestApplyError::null_pointer: return "null_pointer";
    case GuestApplyError::out_of_bounds: return "out_of_bounds";
    case GuestApplyError::not_in_array: return "not_in_array";
    case GuestApplyError::unmapped: return "unmapped";
    case GuestApplyError::identity_mismatch: return "identity_mismatch";
    case GuestApplyError::nonfinite: return "nonfinite";
    case GuestApplyError::conflict: return "conflict";
    case GuestApplyError::write_failed: return "write_failed";
    case GuestApplyError::rollback_failed: return "rollback_failed";
    }
    return "unknown";
}

bool guest_build_accepted(const uint8_t sha256[32]) {
    if (sha256 == nullptr) return false;
    return std::memcmp(sha256, kMeasuredJ460ExeSha256, 32) == 0;
}

bool guest_exe_sha256_from_hex(const char* hex, uint8_t out[32]) {
    if (hex == nullptr || out == nullptr) return false;
    for (int i = 0; i < 32; ++i) {
        const char high = hex[i * 2];
        const char low = hex[i * 2 + 1];
        if (high == '\0' || low == '\0') return false;
        auto nibble = [](char c) -> int {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return -1;
        };
        const int hi = nibble(high);
        const int lo = nibble(low);
        if (hi < 0 || lo < 0) return false;
        out[i] = static_cast<uint8_t>((hi << 4) | lo);
    }
    return hex[64] == '\0';
}

GuestApplyReport apply_guest_view(const GuestView& guest, GuestMemory& memory, uint32_t game, const uint8_t exe_sha256[32]) {
    GuestApplyReport report;
    const RenderPlan plan = guest.plan();
    if (!guest_build_accepted(exe_sha256)) {
        report.error = GuestApplyError::unknown_build;
        return seal(report, plan);
    }
    if (!plan.has_snapshot) {
        report.error = GuestApplyError::no_snapshot;
        return seal(report, plan);
    }
    const WorldSnapshot* world = guest.snapshot();
    if (world == nullptr) {
        report.error = GuestApplyError::no_snapshot;
        return seal(report, plan);
    }
    for (const RenderWrite& player : plan.players) {
        if (!finite_pose(player.x, player.y, player.vx, player.vy, player.size)) {
            report.error = GuestApplyError::nonfinite;
            return seal(report, plan);
        }
    }
    for (const RenderWrite& entity : plan.bound_entities) {
        if (!finite_pose(entity.x, entity.y, entity.vx, entity.vy, entity.size)) {
            report.error = GuestApplyError::nonfinite;
            return seal(report, plan);
        }
    }
    if (plan.players.empty() && plan.bound_entities.empty()) {
        report.error = GuestApplyError::ok;
        report.pose_committed = true;
        return seal(report, plan);
    }
    if (game == 0) {
        report.error = GuestApplyError::null_pointer;
        return seal(report, plan);
    }

    uint32_t level = 0;
    if (!read_u32(memory, game + J460GuestLayout::game_level, level)) {
        report.error = GuestApplyError::out_of_bounds;
        return seal(report, plan);
    }
    if (level == 0) {
        report.error = GuestApplyError::null_pointer;
        return seal(report, plan);
    }
    uint32_t entity_array = 0;
    uint32_t capacity_bytes = 0;
    uint32_t entity_count = 0;
    if (!read_u32(memory, level + J460GuestLayout::level_entities, entity_array) ||
        !read_u32(memory, level + J460GuestLayout::level_entity_capacity_bytes, capacity_bytes) ||
        !read_u32(memory, level + J460GuestLayout::level_entity_count, entity_count)) {
        report.error = GuestApplyError::out_of_bounds;
        return seal(report, plan);
    }
    if (capacity_bytes % J460GuestLayout::pointer_bytes != 0 || entity_count > J460GuestLayout::max_entity_slots ||
        entity_count > capacity_bytes / J460GuestLayout::pointer_bytes) {
        report.error = GuestApplyError::out_of_bounds;
        return seal(report, plan);
    }
    if (entity_count != 0 && entity_array == 0) {
        report.error = GuestApplyError::null_pointer;
        return seal(report, plan);
    }
    std::vector<uint32_t> entity_pointers(entity_count);
    for (uint32_t i = 0; i < entity_count; ++i) {
        const uint64_t slot = static_cast<uint64_t>(entity_array) + static_cast<uint64_t>(i) * J460GuestLayout::pointer_bytes;
        if (slot > 0xffffffffull || !read_u32(memory, static_cast<uint32_t>(slot), entity_pointers[i])) {
            report.error = GuestApplyError::out_of_bounds;
            return seal(report, plan);
        }
    }

    uint32_t players_begin = 0;
    uint32_t players_end = 0;
    if (!read_u32(memory, game + J460GuestLayout::game_players_begin, players_begin) ||
        !read_u32(memory, game + J460GuestLayout::game_players_end, players_end)) {
        report.error = GuestApplyError::out_of_bounds;
        return seal(report, plan);
    }
    if (players_end < players_begin || (players_end - players_begin) % J460GuestLayout::pointer_bytes != 0) {
        report.error = GuestApplyError::out_of_bounds;
        return seal(report, plan);
    }
    const uint32_t player_count = (players_end - players_begin) / J460GuestLayout::pointer_bytes;
    if (player_count > J460GuestLayout::max_player_slots) {
        report.error = GuestApplyError::out_of_bounds;
        return seal(report, plan);
    }
    if (player_count != 0 && players_begin == 0) {
        report.error = GuestApplyError::null_pointer;
        return seal(report, plan);
    }
    std::vector<uint32_t> player_pointers(player_count);
    for (uint32_t i = 0; i < player_count; ++i) {
        const uint64_t slot = static_cast<uint64_t>(players_begin) + static_cast<uint64_t>(i) * J460GuestLayout::pointer_bytes;
        if (slot > 0xffffffffull || !read_u32(memory, static_cast<uint32_t>(slot), player_pointers[i])) {
            report.error = GuestApplyError::out_of_bounds;
            return seal(report, plan);
        }
    }

    std::vector<PoseTarget> targets;
    bool failed = false;
    auto fail = [&](GuestApplyError error, uint64_t network_id) {
        if (!failed) report.error = error;
        failed = true;
        remember_failure(report, network_id);
    };
    for (const RenderWrite& player : plan.players) {
        const NetEntity* alias = find_alias(*world, player.player_slot);
        if (alias == nullptr) {
            fail(GuestApplyError::unmapped, 0);
            continue;
        }
        if (player.player_slot >= player_count) {
            fail(GuestApplyError::out_of_bounds, alias->id);
            continue;
        }
        const uint32_t address = player_pointers[player.player_slot];
        if (address == 0) {
            fail(GuestApplyError::null_pointer, alias->id);
            continue;
        }
        Identity identity;
        if (!read_identity(memory, address, identity)) {
            fail(GuestApplyError::out_of_bounds, alias->id);
            continue;
        }
        if (!identity_matches(identity, *alias)) {
            fail(GuestApplyError::identity_mismatch, alias->id);
            continue;
        }
        targets.push_back(PoseTarget{address, alias->id, player.x, player.y, player.vx, player.vy, player.size});
    }
    for (const RenderWrite& bound : plan.bound_entities) {
        const NetEntity* entity = find_id(*world, bound.network_id);
        if (entity == nullptr) {
            fail(GuestApplyError::unmapped, bound.network_id);
            continue;
        }
        if (bound.local_token == 0) {
            fail(GuestApplyError::null_pointer, bound.network_id);
            continue;
        }
        bool listed = false;
        for (uint32_t pointer : entity_pointers)
            if (pointer == bound.local_token) listed = true;
        if (!listed) {
            fail(GuestApplyError::not_in_array, bound.network_id);
            continue;
        }
        Identity identity;
        if (!read_identity(memory, bound.local_token, identity)) {
            fail(GuestApplyError::out_of_bounds, bound.network_id);
            continue;
        }
        if (!identity_matches(identity, *entity)) {
            fail(GuestApplyError::identity_mismatch, bound.network_id);
            continue;
        }
        targets.push_back(PoseTarget{bound.local_token, bound.network_id, bound.x, bound.y, bound.vx, bound.vy, bound.size});
    }
    if (failed) return seal(report, plan);

    std::vector<StagedWrite> staged;
    GuestApplyError stage_error = GuestApplyError::ok;
    for (const PoseTarget& target : targets) {
        if (!stage_pose(staged, memory, target, stage_error)) {
            report.error = stage_error;
            remember_failure(report, target.network_id);
            return seal(report, plan);
        }
    }

    std::vector<uint32_t> written_entities;
    for (const PoseTarget& target : targets) {
        bool seen = false;
        for (uint32_t address : written_entities)
            if (address == target.address) seen = true;
        if (!seen) written_entities.push_back(target.address);
    }
    for (size_t i = 0; i < staged.size(); ++i) {
        if (memory.write(staged[i].address, staged[i].next, staged[i].size)) continue;
        bool restored = true;
        for (size_t n = i; n-- > 0;) {
            if (memory.write(staged[n].address, staged[n].previous, staged[n].size)) continue;
            restored = false;
            report.dirty_addresses.push_back(staged[n].address);
        }
        report.rolled_back = restored;
        report.rollback_failed = !restored;
        report.pose_committed = false;
        report.entities_written = 0;
        report.error = restored ? GuestApplyError::write_failed : GuestApplyError::rollback_failed;
        return seal(report, plan);
    }
    report.error = GuestApplyError::ok;
    report.pose_committed = true;
    report.entities_written = static_cast<uint32_t>(written_entities.size());
    return seal(report, plan);
}

}
