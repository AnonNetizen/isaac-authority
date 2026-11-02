#pragma once
// Offline executor for a GuestView render plan.
//
// apply_guest_view() writes position (+0x33C), velocity (+0x360), and size
// (+0x370) through GuestMemory. It does not spawn or despawn entities, does not
// write the lagging position at +0x38C, and does not change room, stage, or the
// frame counter. Spawn and despawn entries are counted and left undone.
//
// The probe DLL does not call this. There is no launcher switch. It has never
// run inside isaac-ng, and it does not skip 0x554cd0 (ret 4), 0x2f7ac0 (ret 8),
// or 0x2fadc0 (ret). playable stays false. A passing test here is not guest render.
#include "state_model.hpp"
#include <cstdint>
#include <vector>

namespace ia {

// Little-endian SHA-256 of the J460 exe whose entity layout was measured.
// The launcher also accepts an unverified backup hash. This writer does not.
inline constexpr uint8_t kMeasuredJ460ExeSha256[32] = {
    0x21, 0x0c, 0xad, 0xe2, 0xa1, 0xde, 0x98, 0x55, 0x0c, 0xef, 0x52, 0xd0, 0x12, 0x17, 0x41, 0x08,
    0x18, 0x9d, 0x1a, 0x0d, 0x39, 0x26, 0xa2, 0x2c, 0x3a, 0x1e, 0xc1, 0x2f, 0xb3, 0xae, 0x48, 0x31};

// Confirmed J460 offsets. Entity slots are pointers, not inline objects.
// kGuestApplyMax* values are executor guards, not measured engine limits.
struct J460GuestLayout {
    static constexpr uint32_t game_level = 0x18300;
    static constexpr uint32_t game_room = 0x18304;
    static constexpr uint32_t game_previous_room = 0x18308;
    static constexpr uint32_t game_frame = 0x264F8;
    static constexpr uint32_t game_players_begin = 0x1BAA8;
    static constexpr uint32_t game_players_end = 0x1BAAC;
    static constexpr uint32_t level_entities = 0x125C;
    static constexpr uint32_t level_entity_capacity_bytes = 0x1260;
    static constexpr uint32_t level_entity_count = 0x1264;
    static constexpr uint32_t entity_type = 0x28;
    static constexpr uint32_t entity_variant = 0x2C;
    static constexpr uint32_t entity_position = GuestWriteOffsets::position;
    static constexpr uint32_t entity_velocity = GuestWriteOffsets::velocity;
    static constexpr uint32_t entity_size = GuestWriteOffsets::size;
    static constexpr uint32_t entity_position_lag = 0x38C;
    static constexpr uint32_t entity_init_seed = 0x3EC;
    static constexpr uint32_t pointer_bytes = 4;
    static constexpr uint32_t max_entity_slots = 4096;
    static constexpr uint32_t max_player_slots = 64;
};

enum class GuestApplyError {
    ok,
    no_snapshot,
    unknown_build,
    null_pointer,
    out_of_bounds,
    not_in_array,
    unmapped,
    identity_mismatch,
    nonfinite,
    conflict,
    write_failed,
    rollback_failed
};

// not_performed means the plan asked for a spawn or despawn and this step did
// not do it. none_requested means the plan had neither.
enum class GuestLifecycle { none_requested, not_performed };

struct GuestApplyReport {
    GuestApplyError error{GuestApplyError::ok};
    GuestLifecycle lifecycle{GuestLifecycle::none_requested};
    bool pose_committed{false};
    bool complete{false};
    bool rolled_back{false};
    bool rollback_failed{false};
    // Always false. This step cannot create or destroy entities.
    bool lifecycle_performed{false};
    // Always false. No call has been made in isaac-ng.
    bool in_game{false};
    bool playable{false};
    uint32_t entities_written{0};
    uint32_t spawns_not_performed{0};
    uint32_t despawns_not_performed{0};
    std::vector<uint64_t> failed_network_ids;
    // Addresses left at the new value because restoring the previous bytes failed.
    std::vector<uint32_t> dirty_addresses;
};

// Byte-addressed guest memory. A false write must leave that range unchanged.
// Reads and writes are little-endian, matching the x86 game, regardless of host.
class GuestMemory {
public:
    virtual ~GuestMemory() = default;
    virtual bool read(uint32_t address, void* dest, size_t size) const = 0;
    virtual bool write(uint32_t address, const void* src, size_t size) = 0;
};

const char* guest_apply_error_name(GuestApplyError error);
bool guest_build_accepted(const uint8_t sha256[32]);
bool guest_exe_sha256_from_hex(const char* hex, uint8_t out[32]);

// `game` is the guest Game*. `exe_sha256` is the 32-byte exe hash the caller
// observed. A null hash, the unverified backup hash, or any other value is
// unknown_build and writes nothing.
//
// `game` and the Level* loaded from it are 32-bit addresses. A field offset
// that does not fit above that base is out_of_bounds, and the apply writes nothing.
//
// Bound entities are written only at their local token, and only when that
// token is a non-null pointer in the live entity array and the memory triple
// Type +0x28 / Variant +0x2C / InitSeed +0x3EC matches the snapshot. A missing
// token is not replaced with another entity that happens to share the triple.
// Player slots use the player vector. One failed pose rejects the whole apply.
// Earlier pose writes are restored, or listed in dirty_addresses.
GuestApplyReport apply_guest_view(const GuestView& guest, GuestMemory& memory, uint32_t game, const uint8_t exe_sha256[32]);

}
