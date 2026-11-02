#include "guest_apply.hpp"
#include <cstdint>
#include <cstring>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

namespace {
using namespace ia;

constexpr uint32_t kGame = 0x10000000u;
constexpr uint32_t kLevel = 0x20000000u;
constexpr uint32_t kPlayerVector = 0x30000000u;
constexpr uint32_t kEntityArray = 0x31000000u;
constexpr uint32_t kPlayer = 0x40000000u;
constexpr uint32_t kMonster = 0x40001000u;
constexpr uint32_t kOther = 0x40002000u;
constexpr uint32_t kStray = 0x40003000u;
constexpr uint32_t kPlayerSeed = 0x11111111u;
constexpr uint32_t kMonsterSeed = 0x01020304u;

class SimMemory : public GuestMemory {
public:
    std::map<uint32_t, uint8_t> bytes;
    mutable int reads{0};
    int writes{0};
    std::vector<int> fail_on;

    bool read(uint32_t address, void* dest, size_t size) const override {
        ++reads;
        if (dest == nullptr || !mapped(address, size)) return false;
        auto* out = static_cast<uint8_t*>(dest);
        for (size_t i = 0; i < size; ++i) out[i] = bytes.at(static_cast<uint32_t>(static_cast<uint64_t>(address) + i));
        return true;
    }
    bool write(uint32_t address, const void* src, size_t size) override {
        ++writes;
        for (int index : fail_on)
            if (index == writes) return false;
        if (src == nullptr || !mapped(address, size)) return false;
        const auto* in = static_cast<const uint8_t*>(src);
        for (size_t i = 0; i < size; ++i)
            bytes[static_cast<uint32_t>(static_cast<uint64_t>(address) + i)] = in[i];
        return true;
    }
    bool mapped(uint32_t address, size_t size) const {
        if (size == 0 || static_cast<uint64_t>(address) + size > 0x100000000ull) return false;
        for (size_t i = 0; i < size; ++i)
            if (!bytes.count(static_cast<uint32_t>(static_cast<uint64_t>(address) + i))) return false;
        return true;
    }
    void fill(uint32_t address, uint32_t size, uint8_t value) {
        for (uint32_t i = 0; i < size; ++i) {
            const uint64_t at = static_cast<uint64_t>(address) + i;
            if (at > 0xffffffffull) return;
            bytes[static_cast<uint32_t>(at)] = value;
        }
    }
    void put_u32(uint32_t address, uint32_t value) {
        for (int i = 0; i < 4; ++i) bytes[address + static_cast<uint32_t>(i)] = static_cast<uint8_t>(value >> (8 * i));
    }
    uint32_t get_u32(uint32_t address) const {
        uint32_t value = 0;
        for (int i = 0; i < 4; ++i) value |= static_cast<uint32_t>(bytes.at(address + static_cast<uint32_t>(i))) << (8 * i);
        return value;
    }
    void put_f32(uint32_t address, float value) {
        uint32_t bits = 0;
        std::memcpy(&bits, &value, 4);
        put_u32(address, bits);
    }
    bool f32_is(uint32_t address, float want) const {
        uint32_t bits = 0;
        std::memcpy(&bits, &want, 4);
        return get_u32(address) == bits;
    }
    std::map<uint32_t, uint8_t> image() const { return bytes; }
};

struct Pose {
    float x, y, vx, vy, size;
};

void plant(SimMemory& memory, uint32_t address, uint32_t type, uint32_t variant, uint32_t seed, Pose pose) {
    memory.fill(address, 0x400, 0xA5);
    memory.put_u32(address + J460GuestLayout::entity_type, type);
    memory.put_u32(address + J460GuestLayout::entity_variant, variant);
    memory.put_u32(address + 0x3DC, 0xEEEEEEEEu);
    memory.put_u32(address + J460GuestLayout::entity_init_seed, seed);
    memory.put_f32(address + J460GuestLayout::entity_position, pose.x);
    memory.put_f32(address + J460GuestLayout::entity_position + 4, pose.y);
    memory.put_f32(address + J460GuestLayout::entity_velocity, pose.vx);
    memory.put_f32(address + J460GuestLayout::entity_velocity + 4, pose.vy);
    memory.put_f32(address + J460GuestLayout::entity_size, pose.size);
    memory.put_f32(address + J460GuestLayout::entity_position_lag, pose.x + 50.f);
    memory.put_f32(address + J460GuestLayout::entity_position_lag + 4, pose.y + 60.f);
}

bool pose_is(const SimMemory& memory, uint32_t address, Pose pose) {
    return memory.f32_is(address + J460GuestLayout::entity_position, pose.x) &&
           memory.f32_is(address + J460GuestLayout::entity_position + 4, pose.y) &&
           memory.f32_is(address + J460GuestLayout::entity_velocity, pose.vx) &&
           memory.f32_is(address + J460GuestLayout::entity_velocity + 4, pose.vy) &&
           memory.f32_is(address + J460GuestLayout::entity_size, pose.size);
}

bool preserved_neighbors(const SimMemory& memory, uint32_t address, Pose original) {
    return memory.bytes.at(address + J460GuestLayout::entity_position + 8) == 0xA5 &&
           memory.bytes.at(address + J460GuestLayout::entity_velocity + 8) == 0xA5 &&
           memory.bytes.at(address + J460GuestLayout::entity_size + 4) == 0xA5 &&
           memory.get_u32(address + 0x3DC) == 0xEEEEEEEEu &&
           memory.f32_is(address + J460GuestLayout::entity_position_lag, original.x + 50.f) &&
           memory.f32_is(address + J460GuestLayout::entity_position_lag + 4, original.y + 60.f);
}

void map_world(SimMemory& memory, uint32_t player_count, uint32_t entity_count, uint32_t entity_slots) {
    memory.put_u32(kGame + J460GuestLayout::game_level, kLevel);
    memory.put_u32(kGame + J460GuestLayout::game_room, 0x11111111u);
    memory.put_u32(kGame + J460GuestLayout::game_previous_room, 0x22222222u);
    memory.put_u32(kGame + J460GuestLayout::game_frame, 999);
    memory.put_u32(kGame + J460GuestLayout::game_players_begin, player_count == 0 ? 0 : kPlayerVector);
    memory.put_u32(kGame + J460GuestLayout::game_players_end, player_count == 0 ? 0 : kPlayerVector + player_count * 4);
    if (player_count != 0) memory.fill(kPlayerVector, player_count * 4, 0);
    memory.put_u32(kLevel + J460GuestLayout::level_entities, entity_slots == 0 ? 0 : kEntityArray);
    memory.put_u32(kLevel + J460GuestLayout::level_entity_capacity_bytes, entity_slots * 4);
    memory.put_u32(kLevel + J460GuestLayout::level_entity_count, entity_count);
    if (entity_slots != 0) memory.fill(kEntityArray, entity_slots * 4, 0);
}

void set_slot(SimMemory& memory, uint32_t array, uint32_t index, uint32_t pointer) {
    memory.put_u32(array + index * 4, pointer);
}

struct Hash {
    uint8_t bytes[32];
};

Hash measured_hash() {
    Hash hash{};
    std::memcpy(hash.bytes, kMeasuredJ460ExeSha256, 32);
    return hash;
}

GuestApplyReport apply_measured(GuestView& guest, SimMemory& memory, uint32_t game = kGame) {
    const Hash hash = measured_hash();
    return apply_guest_view(guest, memory, game, hash.bytes);
}

const NetEntity* by_seed(const WorldSnapshot& world, uint32_t seed) {
    for (const auto& entity : world.entities)
        if (entity.init_seed == seed) return &entity;
    return nullptr;
}

bool accept_publish(GuestView& guest, const PublishResult& published) {
    return published.error == ModelError::ok &&
           guest.accept(published.bytes.data(), published.bytes.size()) == ModelError::ok && guest.snapshot() != nullptr;
}

bool headers_unchanged(const SimMemory& memory, uint32_t entity_count) {
    return memory.get_u32(kGame + J460GuestLayout::game_room) == 0x11111111u &&
           memory.get_u32(kGame + J460GuestLayout::game_previous_room) == 0x22222222u &&
           memory.get_u32(kGame + J460GuestLayout::game_frame) == 999 &&
           memory.get_u32(kLevel + J460GuestLayout::level_entity_count) == entity_count;
}

NativeCapture capture_pair(uint32_t frame, float player_x, float monster_x, bool monster = true) {
    NativeCapture capture;
    capture.frame = frame;
    capture.room_index = 71;
    capture.previous_room = 84;
    capture.players.push_back(NativePlayer{kPlayer, player_x, 380.f, 1.5f, -0.5f, 11.f});
    capture.entities.push_back(NativeEntity{kPlayer, 1, 0, kPlayerSeed, player_x, 380.f, 1.5f, -0.5f, 11.f});
    if (monster)
        capture.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, monster_x, 200.f, 0.25f, 0.5f, 8.f});
    return capture;
}

Pose player_pose(float x) { return Pose{x, 380.f, 1.5f, -0.5f, 11.f}; }
Pose monster_pose(float x) { return Pose{x, 200.f, 0.25f, 0.5f, 8.f}; }

bool bind_player_77(GuestView& guest) {
    HostPublisher publisher;
    if (!accept_publish(guest, publisher.publish(capture_pair(10, 77.f, 0.f, false)))) return false;
    const auto* player = by_seed(*guest.snapshot(), kPlayerSeed);
    return player != nullptr && guest.bind(player->id, kPlayer);
}

void plant_live_player(SimMemory& memory) {
    memory.fill(kPlayerVector, 4, 0);
    memory.fill(kEntityArray, 4, 0);
    set_slot(memory, kPlayerVector, 0, kPlayer);
    set_slot(memory, kEntityArray, 0, kPlayer);
    plant(memory, kPlayer, 1, 0, kPlayerSeed, player_pose(1.f));
}

// "21\0" sits in the last three bytes of a readable page. The next page is
// inaccessible, so a parser that loads the byte after the terminator faults.
bool short_hex_stops_at_terminator() {
    uint8_t out[32];
    std::memset(out, 0x5A, sizeof(out));
#if defined(_WIN32)
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    const size_t page = info.dwPageSize;
    if (page < 4) return false;
    auto* region = static_cast<uint8_t*>(VirtualAlloc(nullptr, page * 2, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (region == nullptr) return false;
    DWORD previous = 0;
    if (VirtualProtect(region + page, page, PAGE_NOACCESS, &previous) == 0) {
        VirtualFree(region, 0, MEM_RELEASE);
        return false;
    }
    char* hex = reinterpret_cast<char*>(region + page - 3);
    hex[0] = '2';
    hex[1] = '1';
    hex[2] = '\0';
    const bool rejected = !guest_exe_sha256_from_hex(hex, out);
    VirtualFree(region, 0, MEM_RELEASE);
    return rejected;
#else
    const long page = sysconf(_SC_PAGESIZE);
    if (page < 4) return false;
    void* region = mmap(nullptr, static_cast<size_t>(page) * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (region == MAP_FAILED) return false;
    auto* bytes = static_cast<uint8_t*>(region);
    if (mprotect(bytes + page, static_cast<size_t>(page), PROT_NONE) != 0) {
        munmap(region, static_cast<size_t>(page) * 2);
        return false;
    }
    char* hex = reinterpret_cast<char*>(bytes + page - 3);
    hex[0] = '2';
    hex[1] = '1';
    hex[2] = '\0';
    const bool rejected = !guest_exe_sha256_from_hex(hex, out);
    munmap(region, static_cast<size_t>(page) * 2);
    return rejected;
#endif
}
}

unsigned run_guest_apply_tests() {
    unsigned passed = 0;
    auto expect = [&](bool ok, const char* name) {
        if (!ok) throw std::runtime_error(std::string("guest apply: ") + name);
        ++passed;
    };
    auto expect_error = [&](GuestApplyError got, GuestApplyError want, const char* name) {
        if (got != want) throw std::runtime_error(std::string("guest apply: ") + name + " got " + guest_apply_error_name(got));
        ++passed;
    };

    expect(J460GuestLayout::entity_type == 0x28u && J460GuestLayout::entity_variant == 0x2Cu &&
               J460GuestLayout::entity_init_seed == 0x3ECu && J460GuestLayout::entity_position == 0x33Cu &&
               J460GuestLayout::entity_velocity == 0x360u && J460GuestLayout::entity_size == 0x370u &&
               J460GuestLayout::entity_position_lag == 0x38Cu,
           "entity field offsets");
    expect(J460GuestLayout::game_level == 0x18300u && J460GuestLayout::game_players_begin == 0x1BAA8u &&
               J460GuestLayout::game_players_end == 0x1BAACu && J460GuestLayout::level_entities == 0x125Cu &&
               J460GuestLayout::level_entity_capacity_bytes == 0x1260u && J460GuestLayout::level_entity_count == 0x1264u &&
               J460GuestLayout::game_frame == 0x264F8u,
           "game and level offsets");
    uint8_t parsed[32]{};
    uint8_t backup[32]{};
    expect(guest_exe_sha256_from_hex("210cade2a1de98550cef52d012174108189d1a0d3926a22c3a1ec12fb3ae4831", parsed) &&
               std::memcmp(parsed, kMeasuredJ460ExeSha256, 32) == 0 && guest_build_accepted(parsed),
           "measured J460 hash is the only write permit");
    expect(guest_exe_sha256_from_hex("7122ac28779925b24e23e2416f231322b1470388bd25e2c08665ad8d53b3ea4f", backup) &&
               !guest_build_accepted(backup) && !guest_build_accepted(nullptr),
           "unverified backup hash is rejected");
    expect(!guest_exe_sha256_from_hex("21", parsed) && !guest_exe_sha256_from_hex("", parsed) &&
               !guest_exe_sha256_from_hex("210", parsed) && !guest_exe_sha256_from_hex(nullptr, parsed) &&
               !guest_exe_sha256_from_hex("210cade2a1de98550cef52d012174108189d1a0d3926a22c3a1ec12fb3ae483", parsed) &&
               !guest_exe_sha256_from_hex("210cade2a1de98550cef52d012174108189d1a0d3926a22c3a1ec12fb3ae4831a", parsed),
           "short, odd, and overlong hex is rejected");
    expect(short_hex_stops_at_terminator(), "short hex does not read past the terminator");
    parsed[31] ^= 0x01;
    expect(!guest_build_accepted(parsed), "flipped hash is rejected");

    GuestView empty;
    SimMemory unused;
    auto missing = apply_measured(empty, unused);
    expect_error(missing.error, GuestApplyError::no_snapshot, "no snapshot");
    expect(!missing.pose_committed && !missing.complete && !missing.playable && !missing.in_game && unused.writes == 0,
           "no snapshot writes nothing");

    {
        SimMemory memory;
        map_world(memory, 1, 2, 4);
        set_slot(memory, kPlayerVector, 0, kPlayer);
        set_slot(memory, kEntityArray, 0, kPlayer);
        set_slot(memory, kEntityArray, 1, kMonster);
        const Pose old_player = player_pose(1.f);
        const Pose old_monster = monster_pose(2.f);
        plant(memory, kPlayer, 1, 0, kPlayerSeed, old_player);
        plant(memory, kMonster, 1000, 1, kMonsterSeed, old_monster);
        plant(memory, kOther, 1000, 1, kMonsterSeed, monster_pose(3.f));
        HostPublisher publisher;
        GuestView guest;
        auto first = publisher.publish(capture_pair(10, 320.f, 100.f));
        expect(accept_publish(guest, first), "happy path accepts keyframe");
        const auto* player = by_seed(*guest.snapshot(), kPlayerSeed);
        const auto* monster = by_seed(*guest.snapshot(), kMonsterSeed);
        expect(player != nullptr && monster != nullptr && guest.bind(player->id, kPlayer) && guest.bind(monster->id, kMonster),
               "happy path binds both entities");
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::ok, "happy path apply");
        expect(report.pose_committed && report.complete && report.entities_written == 2 &&
                   report.lifecycle == GuestLifecycle::none_requested && report.spawns_not_performed == 0 &&
                   report.despawns_not_performed == 0 && !report.lifecycle_performed && !report.playable && !report.in_game,
               "happy path commits both poses and nothing else");
        expect(pose_is(memory, kPlayer, player_pose(320.f)) && pose_is(memory, kMonster, monster_pose(100.f)) &&
                   pose_is(memory, kOther, monster_pose(3.f)),
               "writes land on the bound entities only");
        expect(preserved_neighbors(memory, kPlayer, old_player) && preserved_neighbors(memory, kMonster, old_monster) &&
                   headers_unchanged(memory, 2) && memory.get_u32(kEntityArray) == kPlayer &&
                   memory.get_u32(kEntityArray + 4) == kMonster,
               "lagging position, room, frame, and array slots stay put");
        const auto once = memory.image();
        auto again = apply_measured(guest, memory);
        expect_error(again.error, GuestApplyError::ok, "second apply");
        expect(again.complete && again.entities_written == 2 && memory.image() == once, "same snapshot is idempotent");

        auto moved = publisher.publish(capture_pair(11, 330.f, 140.f));
        expect(accept_publish(guest, moved), "move delta");
        auto moved_report = apply_measured(guest, memory);
        expect(moved_report.complete && pose_is(memory, kPlayer, player_pose(330.f)) &&
                   pose_is(memory, kMonster, monster_pose(140.f)) && preserved_neighbors(memory, kPlayer, old_player),
               "a later snapshot replaces the pose");
        const auto moved_image = memory.image();
        expect(apply_measured(guest, memory).complete && memory.image() == moved_image, "the later snapshot is also idempotent");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        set_slot(memory, kEntityArray, 0, kMonster);
        plant(memory, kMonster, 1000, 1, kMonsterSeed, monster_pose(2.f));
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 71;
        capture.previous_room = 84;
        capture.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)), "spawn-only keyframe");
        const auto before = memory.image();
        const int reads = memory.reads;
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::ok, "spawn-only has no pose error");
        expect(!report.complete && report.pose_committed && report.entities_written == 0 && report.spawns_not_performed == 1 &&
                   report.despawns_not_performed == 0 && report.lifecycle == GuestLifecycle::not_performed &&
                   !report.lifecycle_performed && memory.image() == before && memory.writes == 0 && memory.reads == reads,
               "spawn is reported and does not create an entity");
        uint8_t bad[32]{};
        auto rejected = apply_guest_view(guest, memory, kGame, bad);
        expect_error(rejected.error, GuestApplyError::unknown_build, "unknown build");
        expect(!rejected.complete && rejected.spawns_not_performed == 1 && memory.image() == before && memory.writes == 0,
               "unknown build reports the spawn and writes nothing");
        auto null_game = apply_measured(guest, memory, 0);
        expect(memory.image() == before && memory.writes == 0, "null game is not touched when there is no pose");
        expect_error(null_game.error, GuestApplyError::ok, "spawn-only does not need Game*");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 3, 4);
        set_slot(memory, kEntityArray, 0, kMonster);
        set_slot(memory, kEntityArray, 1, kOther);
        set_slot(memory, kEntityArray, 2, kStray);
        plant(memory, kMonster, 40, 1, 0x101u, monster_pose(2.f));
        plant(memory, kOther, 41, 1, 0x102u, monster_pose(3.f));
        plant(memory, kStray, 42, 1, 0x103u, monster_pose(4.f));
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 4;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{kMonster, 40, 1, 0x101u, 30.f, 200.f, 0.25f, 0.5f, 8.f});
        capture.entities.push_back(NativeEntity{kOther, 41, 1, 0x102u, 31.f, 200.f, 0.25f, 0.5f, 8.f});
        capture.entities.push_back(NativeEntity{kStray, 42, 1, 0x103u, 32.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)), "three entity keyframe");
        const auto* bound = by_seed(*guest.snapshot(), 0x102u);
        expect(bound != nullptr && guest.bind(bound->id, kOther), "bind the middle entity");
        auto report = apply_measured(guest, memory);
        expect(report.error == GuestApplyError::ok && !report.complete && report.spawns_not_performed == 2 &&
                   report.entities_written == 1 && pose_is(memory, kOther, Pose{31.f, 200.f, 0.25f, 0.5f, 8.f}) &&
                   pose_is(memory, kMonster, monster_pose(2.f)) && pose_is(memory, kStray, monster_pose(4.f)),
               "an unbound network id is not written onto some other entity");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 2, 2);
        set_slot(memory, kEntityArray, 0, kMonster);
        set_slot(memory, kEntityArray, 1, kOther);
        plant(memory, kMonster, 40, 2, 0x777u, monster_pose(2.f));
        plant(memory, kOther, 40, 2, 0x777u, monster_pose(3.f));
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 4;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{kMonster, 40, 2, 0x777u, 30.f, 200.f, 0.25f, 0.5f, 8.f});
        capture.entities.push_back(NativeEntity{kOther, 40, 2, 0x777u, 80.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)), "same triple keyframe");
        expect(guest.snapshot()->entities.size() == 2 && guest.snapshot()->entities[0].id != guest.snapshot()->entities[1].id,
               "same triple still has two network ids");
        const auto before = memory.image();
        auto unbound = apply_measured(guest, memory);
        expect(!unbound.complete && unbound.spawns_not_performed == 2 && unbound.entities_written == 0 && memory.image() == before,
               "a shared triple is not used to search for a local entity");
        const uint64_t first_id = guest.snapshot()->entities[0].id;
        expect(guest.snapshot()->entities[0].id != guest.snapshot()->entities[1].id, "the two rows stay distinct");
        expect(guest.bind(first_id, kOther), "bind the first id to the other pointer");
        auto followed = apply_measured(guest, memory);
        const Pose first_pose = Pose{guest.snapshot()->entities[0].x, 200.f, 0.25f, 0.5f, 8.f};
        expect(followed.error == GuestApplyError::ok && !followed.complete && pose_is(memory, kOther, first_pose) &&
                   pose_is(memory, kMonster, monster_pose(2.f)),
               "the executor follows the bound token and does not correct it");
        guest.unbind(first_id);
        plant(memory, kMonster, 40, 2, 0x999u, monster_pose(2.f));
        plant(memory, kOther, 40, 2, 0x777u, monster_pose(3.f));
        expect(guest.bind(first_id, kMonster), "bind the first id to the mismatched object");
        const auto mismatched_before = memory.image();
        const int writes = memory.writes;
        auto mismatched = apply_measured(guest, memory);
        expect_error(mismatched.error, GuestApplyError::identity_mismatch, "identity mismatch");
        expect(!mismatched.pose_committed && !mismatched.complete && mismatched.failed_network_ids.size() == 1 &&
                   mismatched.failed_network_ids[0] == first_id && memory.image() == mismatched_before && memory.writes == writes,
               "identity mismatch does not fall through to the entity whose triple matches");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        set_slot(memory, kEntityArray, 0, kOther);
        plant(memory, kOther, 9, 9, 0x9u, monster_pose(3.f));
        plant(memory, kStray, 1000, 1, kMonsterSeed, monster_pose(4.f));
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 4;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{kStray, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)), "stray keyframe");
        const auto* monster = by_seed(*guest.snapshot(), kMonsterSeed);
        expect(monster != nullptr && guest.bind(monster->id, kStray), "bind a pointer that is not in the array");
        const auto before = memory.image();
        const int writes = memory.writes;
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::not_in_array, "token missing from the entity array");
        expect(!report.pose_committed && report.failed_network_ids.size() == 1 && report.failed_network_ids[0] == monster->id &&
                   memory.image() == before && memory.writes == writes,
               "a matching stray object is not written");
        guest.unbind(monster->id);
        expect(guest.bind(monster->id, 0), "bind a null token");
        set_slot(memory, kEntityArray, 1, 0);
        memory.put_u32(kLevel + J460GuestLayout::level_entity_count, 2);
        const auto null_before = memory.image();
        const int null_writes = memory.writes;
        auto null_token = apply_measured(guest, memory);
        expect_error(null_token.error, GuestApplyError::null_pointer, "null token");
        expect(memory.image() == null_before && memory.writes == null_writes, "a null array slot is not the target of token 0");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        set_slot(memory, kEntityArray, 0, kOther);
        set_slot(memory, kEntityArray, 1, kMonster);
        plant(memory, kMonster, 1000, 1, kMonsterSeed, monster_pose(2.f));
        plant(memory, kOther, 1, 0, 1, monster_pose(3.f));
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 4;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)) && guest.bind(by_seed(*guest.snapshot(), kMonsterSeed)->id, kMonster),
               "pointer past count");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::not_in_array, "past the live count");
        expect(memory.image() == before && memory.writes == 0, "capacity past count is not a live entity");
    }

    {
        SimMemory memory;
        map_world(memory, 1, 2, 4);
        set_slot(memory, kPlayerVector, 0, 0);
        set_slot(memory, kEntityArray, 0, kPlayer);
        set_slot(memory, kEntityArray, 1, kMonster);
        plant(memory, kPlayer, 1, 0, kPlayerSeed, player_pose(1.f));
        plant(memory, kMonster, 1000, 1, kMonsterSeed, monster_pose(2.f));
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture_pair(3, 320.f, 100.f))), "null player slot keyframe");
        expect(guest.bind(by_seed(*guest.snapshot(), kMonsterSeed)->id, kMonster), "bind monster beside a null player");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::null_pointer, "null player pointer");
        expect(!report.pose_committed && memory.image() == before && memory.writes == 0, "a failed player slot writes no monster either");
        const auto* player = by_seed(*guest.snapshot(), kPlayerSeed);
        expect(player != nullptr && report.failed_network_ids.size() == 1 && report.failed_network_ids[0] == player->id,
               "the failed player id is recorded");
    }

    {
        SimMemory memory;
        map_world(memory, 1, 1, 2);
        set_slot(memory, kPlayerVector, 0, kPlayer);
        set_slot(memory, kEntityArray, 0, kMonster);
        plant(memory, kPlayer, 1, 0, kPlayerSeed, player_pose(1.f));
        plant(memory, kMonster, 1000, 1, kMonsterSeed, monster_pose(2.f));
        NativeCapture capture;
        capture.frame = 4;
        capture.room_index = 71;
        capture.previous_room = 84;
        capture.players.push_back(NativePlayer{kPlayer, 320.f, 380.f, 1.5f, -0.5f, 11.f});
        capture.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)) && guest.bind(by_seed(*guest.snapshot(), kMonsterSeed)->id, kMonster),
               "player without an alias entity");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::unmapped, "player slot without a snapshot triple");
        expect(memory.image() == before && memory.writes == 0, "missing player identity blocks the bound monster");
    }

    {
        SimMemory memory;
        map_world(memory, 1, 1, 2);
        set_slot(memory, kPlayerVector, 0, kPlayer);
        set_slot(memory, kEntityArray, 0, kPlayer);
        plant(memory, kPlayer, 1, 0, kPlayerSeed, player_pose(1.f));
        NativeCapture capture;
        capture.frame = 5;
        capture.room_index = 71;
        capture.previous_room = 84;
        capture.players.push_back(NativePlayer{kPlayer, 10.f, 380.f, 0.f, 0.f, 11.f});
        capture.entities.push_back(NativeEntity{kPlayer, 1, 0, kPlayerSeed, 99.f, 380.f, 1.5f, -0.5f, 11.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)), "conflicting poses keyframe");
        const auto* player = by_seed(*guest.snapshot(), kPlayerSeed);
        expect(player != nullptr && guest.bind(player->id, kPlayer), "bind the conflicting player");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::conflict, "player slot and entity pose disagree");
        expect(memory.image() == before && memory.writes == 0 && !report.pose_committed, "a pose conflict writes neither value");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        set_slot(memory, kEntityArray, 0, kMonster);
        const Pose planted = monster_pose(2.f);
        plant(memory, kMonster, 1000, 1, kMonsterSeed, planted);
        NativeCapture present;
        present.frame = 1;
        present.room_index = 8;
        present.previous_room = 0;
        present.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(present)), "despawn setup");
        const auto* monster = by_seed(*guest.snapshot(), kMonsterSeed);
        expect(monster != nullptr && guest.bind(monster->id, kMonster), "bind the soon-despawned monster");
        const uint64_t id = monster->id;
        bool held = true;
        for (uint32_t frame = 2; frame <= 4; ++frame) {
            NativeCapture gap;
            gap.frame = frame;
            gap.room_index = 8;
            gap.previous_room = 0;
            auto published = publisher.publish(gap);
            held = held && accept_publish(guest, published) && by_seed(*guest.snapshot(), kMonsterSeed) != nullptr;
        }
        expect(held && guest.plan().despawn_ids.empty(), "three misses stay bound");
        auto held_report = apply_measured(guest, memory);
        expect(held_report.error == GuestApplyError::ok && held_report.despawns_not_performed == 0 &&
                   pose_is(memory, kMonster, monster_pose(100.f)) && preserved_neighbors(memory, kMonster, planted),
               "a grace hold still writes the last pose");
        NativeCapture gone;
        gone.frame = 5;
        gone.room_index = 8;
        gone.previous_room = 0;
        expect(accept_publish(guest, publisher.publish(gone)), "fourth miss");
        auto plan = guest.plan();
        expect(plan.despawn_ids.size() == 1 && plan.despawn_ids[0] == id && plan.bound_entities.empty(), "plan lists one despawn");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        auto after = guest.plan();
        expect_error(report.error, GuestApplyError::ok, "despawn apply has no pose error");
        expect(!report.complete && report.lifecycle == GuestLifecycle::not_performed && !report.lifecycle_performed &&
                   report.despawns_not_performed == 1 && report.spawns_not_performed == 0 && report.entities_written == 0 &&
                   memory.image() == before && after.despawn_ids.size() == 1 && after.despawn_ids[0] == id &&
                   memory.get_u32(kEntityArray) == kMonster && headers_unchanged(memory, 1),
               "despawn is reported, the entity stays, and the binding is left alone");
        expect(apply_measured(guest, memory).despawns_not_performed == 1 && memory.image() == before,
               "reporting the same despawn twice is idempotent");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        set_slot(memory, kEntityArray, 0, kMonster);
        const Pose planted = Pose{2.f, 40.f, 4.f, 6.f, 7.f};
        plant(memory, kMonster, 1000, 1, kMonsterSeed, planted);
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 8;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)) && guest.bind(by_seed(*guest.snapshot(), kMonsterSeed)->id, kMonster),
               "rollback setup");
        const auto before = memory.image();
        memory.fail_on.push_back(3);
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::write_failed, "size write fails");
        expect(report.rolled_back && !report.rollback_failed && report.dirty_addresses.empty() && !report.pose_committed &&
                   report.entities_written == 0 && memory.image() == before,
               "a failed pose write restores the earlier fields");
        memory.fail_on = {1};
        memory.writes = 0;
        auto first = apply_measured(guest, memory);
        expect_error(first.error, GuestApplyError::write_failed, "first field write fails");
        expect(first.rolled_back && memory.image() == before && memory.writes == 1, "the first failure writes no field");
        memory.fail_on = {3, 5};
        memory.writes = 0;
        auto dirty = apply_measured(guest, memory);
        expect_error(dirty.error, GuestApplyError::rollback_failed, "rollback fails");
        expect(dirty.rollback_failed && !dirty.pose_committed && dirty.dirty_addresses.size() == 1 &&
                   dirty.dirty_addresses[0] == kMonster + J460GuestLayout::entity_position &&
                   memory.f32_is(kMonster + J460GuestLayout::entity_position, 100.f) &&
                   memory.f32_is(kMonster + J460GuestLayout::entity_position + 4, 200.f) &&
                   memory.f32_is(kMonster + J460GuestLayout::entity_velocity, planted.vx) &&
                   memory.f32_is(kMonster + J460GuestLayout::entity_velocity + 4, planted.vy) &&
                   memory.f32_is(kMonster + J460GuestLayout::entity_size, planted.size) &&
                   memory.get_u32(kMonster + J460GuestLayout::entity_init_seed) == kMonsterSeed &&
                   preserved_neighbors(memory, kMonster, planted),
               "a failed restore names the address left at the new pose");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        constexpr uint32_t high = 0xFFFFFC20u;
        set_slot(memory, kEntityArray, 0, high);
        memory.put_u32(high + J460GuestLayout::entity_type, 1000);
        memory.put_u32(high + J460GuestLayout::entity_variant, 1);
        memory.fill(high + J460GuestLayout::entity_position, 8, 0xA5);
        memory.put_u32(static_cast<uint32_t>(static_cast<uint64_t>(high) + J460GuestLayout::entity_init_seed), kMonsterSeed);
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 8;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{high, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)) && guest.bind(by_seed(*guest.snapshot(), kMonsterSeed)->id, high),
               "high address keyframe");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::out_of_bounds, "InitSeed offset past the address space");
        expect(memory.image() == before && memory.writes == 0, "a wrapping field is not written");
    }

    {
        SimMemory memory;
        map_world(memory, 0, 1, 2);
        set_slot(memory, kEntityArray, 0, kMonster);
        memory.fill(kMonster, 0x100, 0xA5);
        memory.put_u32(kMonster + J460GuestLayout::entity_type, 1000);
        memory.put_u32(kMonster + J460GuestLayout::entity_variant, 1);
        NativeCapture capture;
        capture.frame = 1;
        capture.room_index = 8;
        capture.previous_room = 0;
        capture.entities.push_back(NativeEntity{kMonster, 1000, 1, kMonsterSeed, 100.f, 200.f, 0.25f, 0.5f, 8.f});
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture)) && guest.bind(by_seed(*guest.snapshot(), kMonsterSeed)->id, kMonster),
               "short entity keyframe");
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::out_of_bounds, "unmapped InitSeed");
        expect(memory.image() == before && memory.writes == 0, "a short entity is not partially posed");
    }

    {
        SimMemory memory;
        map_world(memory, 1, 1, 2);
        set_slot(memory, kPlayerVector, 0, kPlayer);
        set_slot(memory, kEntityArray, 0, kPlayer);
        plant(memory, kPlayer, 1, 0, kPlayerSeed, player_pose(1.f));
        HostPublisher publisher;
        GuestView guest;
        expect(accept_publish(guest, publisher.publish(capture_pair(6, 320.f, 100.f))), "header rejection setup");
        memory.put_u32(kLevel + J460GuestLayout::level_entity_count, 5);
        const auto before = memory.image();
        auto report = apply_measured(guest, memory);
        expect_error(report.error, GuestApplyError::out_of_bounds, "entity count above capacity");
        expect(memory.image() == before && memory.writes == 0, "a corrupt entity count writes nothing");
        memory.put_u32(kLevel + J460GuestLayout::level_entity_count, 1);
        memory.put_u32(kGame + J460GuestLayout::game_players_end, kPlayerVector - 4);
        const auto backwards_before = memory.image();
        auto backwards = apply_measured(guest, memory);
        expect_error(backwards.error, GuestApplyError::out_of_bounds, "player vector runs backwards");
        expect(memory.image() == backwards_before && memory.writes == 0, "a backwards player vector writes nothing");
        memory.put_u32(kGame + J460GuestLayout::game_players_end, kPlayerVector + 4);
        memory.put_u32(kGame + J460GuestLayout::game_level, 0);
        const auto level_before = memory.image();
        auto null_level = apply_measured(guest, memory);
        expect_error(null_level.error, GuestApplyError::null_pointer, "null level");
        expect(memory.image() == level_before && memory.writes == 0, "a null level writes nothing");
        const int reads = memory.reads;
        auto null_game = apply_measured(guest, memory, 0);
        expect_error(null_game.error, GuestApplyError::null_pointer, "null Game*");
        expect(memory.reads == reads && memory.writes == 0 && !null_game.playable && !null_game.in_game, "null Game* is refused before any read");
    }

    // uint32 base+offset wraps into the low addresses planted below. The old
    // apply treated that as a live header and wrote the player x to 77.
    auto expect_wrap_rejected = [&](SimMemory& memory, GuestView& guest, uint32_t game, const char* name) {
        const auto before = memory.image();
        auto report = apply_measured(guest, memory, game);
        expect_error(report.error, GuestApplyError::out_of_bounds, name);
        expect(!report.pose_committed && report.entities_written == 0 && memory.writes == 0 && memory.image() == before &&
                   pose_is(memory, kPlayer, player_pose(1.f)) && !report.playable && !report.in_game,
               name);
    };
    {
        SimMemory memory;
        constexpr uint32_t game = 0xFFFFF000u;
        memory.put_u32(game + J460GuestLayout::game_level, kLevel);
        memory.put_u32(game + J460GuestLayout::game_players_begin, kPlayerVector);
        memory.put_u32(game + J460GuestLayout::game_players_end, kPlayerVector + 4);
        memory.put_u32(kLevel + J460GuestLayout::level_entities, kEntityArray);
        memory.put_u32(kLevel + J460GuestLayout::level_entity_capacity_bytes, 4);
        memory.put_u32(kLevel + J460GuestLayout::level_entity_count, 1);
        plant_live_player(memory);
        GuestView guest;
        expect(bind_player_77(guest), "Game* near 4GB setup");
        expect_wrap_rejected(memory, guest, game, "Game* near 4GB is out of bounds");
    }
    {
        SimMemory memory;
        constexpr uint32_t game = 0xFFFE5000u;
        memory.put_u32(game + J460GuestLayout::game_level, kLevel);
        memory.put_u32(game + J460GuestLayout::game_players_begin, kPlayerVector);
        memory.put_u32(game + J460GuestLayout::game_players_end, kPlayerVector + 4);
        memory.put_u32(kLevel + J460GuestLayout::level_entities, kEntityArray);
        memory.put_u32(kLevel + J460GuestLayout::level_entity_capacity_bytes, 4);
        memory.put_u32(kLevel + J460GuestLayout::level_entity_count, 1);
        plant_live_player(memory);
        GuestView guest;
        expect(bind_player_77(guest), "player vector near 4GB setup");
        expect_wrap_rejected(memory, guest, game, "player vector near 4GB is out of bounds");
    }
    {
        SimMemory memory;
        constexpr uint32_t level = 0xFFFFF000u;
        memory.put_u32(kGame + J460GuestLayout::game_level, level);
        memory.put_u32(kGame + J460GuestLayout::game_players_begin, kPlayerVector);
        memory.put_u32(kGame + J460GuestLayout::game_players_end, kPlayerVector + 4);
        memory.put_u32(level + J460GuestLayout::level_entities, kEntityArray);
        memory.put_u32(level + J460GuestLayout::level_entity_capacity_bytes, 4);
        memory.put_u32(level + J460GuestLayout::level_entity_count, 1);
        plant_live_player(memory);
        GuestView guest;
        expect(bind_player_77(guest), "Level* near 4GB setup");
        expect_wrap_rejected(memory, guest, kGame, "Level* near 4GB is out of bounds");
    }
    {
        // The entity-array pointer itself still fits. Capacity and count do not.
        SimMemory memory;
        constexpr uint32_t level = 0xFFFFEDA0u;
        memory.put_u32(kGame + J460GuestLayout::game_level, level);
        memory.put_u32(kGame + J460GuestLayout::game_players_begin, kPlayerVector);
        memory.put_u32(kGame + J460GuestLayout::game_players_end, kPlayerVector + 4);
        memory.put_u32(level + J460GuestLayout::level_entities, kEntityArray);
        memory.put_u32(level + J460GuestLayout::level_entity_capacity_bytes, 4);
        memory.put_u32(level + J460GuestLayout::level_entity_count, 1);
        plant_live_player(memory);
        GuestView guest;
        expect(bind_player_77(guest), "level capacity near 4GB setup");
        expect_wrap_rejected(memory, guest, kGame, "level capacity near 4GB is out of bounds");
    }

    return passed;
}
