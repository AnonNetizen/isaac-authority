#include "state_model.hpp"
#include <algorithm>
#include <cmath>
#include <utility>

namespace ia {
namespace {
bool finite_float(float value) { return std::isfinite(value); }

bool same_float(float a, float b) {
    uint32_t left = 0, right = 0;
    std::memcpy(&left, &a, 4);
    std::memcpy(&right, &b, 4);
    return left == right;
}

void seal_checksum(std::vector<uint8_t>& bytes) {
    bytes[12] = bytes[13] = bytes[14] = bytes[15] = 0;
    const uint32_t sum = crc32_ieee(bytes.data(), bytes.size());
    bytes[12] = static_cast<uint8_t>(sum);
    bytes[13] = static_cast<uint8_t>(sum >> 8);
    bytes[14] = static_cast<uint8_t>(sum >> 16);
    bytes[15] = static_cast<uint8_t>(sum >> 24);
}

bool checksum_ok(const uint8_t* data, size_t size) {
    if (size < 16 || data == nullptr) return false;
    std::vector<uint8_t> copy(data, data + size);
    const uint32_t expect = read_u32(data + 12);
    copy[12] = copy[13] = copy[14] = copy[15] = 0;
    return crc32_ieee(copy.data(), copy.size()) == expect;
}

ModelError check_players(const std::vector<NetPlayer>& players) {
    if (players.size() > kMaxNativePlayers) return ModelError::bad_count;
    std::unordered_set<uint32_t> slots;
    for (const auto& player : players) {
        if (player.slot >= kMaxNativePlayers || !slots.insert(player.slot).second) return ModelError::duplicate_id;
        if (!finite_float(player.x) || !finite_float(player.y) || !finite_float(player.vx) ||
            !finite_float(player.vy) || !finite_float(player.size)) return ModelError::nonfinite;
    }
    return ModelError::ok;
}

ModelError check_entities(const std::vector<NetEntity>& entities) {
    if (entities.size() > kMaxNativeEntities) return ModelError::bad_count;
    std::unordered_set<uint64_t> ids;
    std::unordered_set<uint32_t> aliases;
    for (const auto& entity : entities) {
        if (entity.id == 0 || !ids.insert(entity.id).second) return ModelError::duplicate_id;
        if (!finite_float(entity.x) || !finite_float(entity.y) || !finite_float(entity.vx) ||
            !finite_float(entity.vy) || !finite_float(entity.size)) return ModelError::nonfinite;
        if (entity.player_alias) {
            if (entity.player_slot >= kMaxNativePlayers || !aliases.insert(entity.player_slot).second)
                return ModelError::duplicate_id;
        } else if (entity.player_slot != 0) {
            return ModelError::bad_flags;
        }
    }
    return ModelError::ok;
}

void write_player(std::vector<uint8_t>& out, const NetPlayer& player) {
    put_u32(out, player.slot);
    put_f32(out, player.x); put_f32(out, player.y);
    put_f32(out, player.vx); put_f32(out, player.vy);
    put_f32(out, player.size);
}

void write_entity(std::vector<uint8_t>& out, const NetEntity& entity) {
    put_u64(out, entity.id);
    put_u32(out, entity.type); put_u32(out, entity.variant); put_u32(out, entity.init_seed);
    put_f32(out, entity.x); put_f32(out, entity.y);
    put_f32(out, entity.vx); put_f32(out, entity.vy);
    put_f32(out, entity.size);
    out.push_back(entity.player_alias ? 1 : 0);
    out.push_back(entity.player_alias ? static_cast<uint8_t>(entity.player_slot) : 0);
    out.push_back(0); out.push_back(0);
}

NetPlayer read_player(ByteReader& in) {
    NetPlayer player;
    player.slot = in.u32();
    player.x = in.f32(); player.y = in.f32();
    player.vx = in.f32(); player.vy = in.f32();
    player.size = in.f32();
    return player;
}

bool read_entity(ByteReader& in, NetEntity& entity) {
    entity.id = in.u64();
    entity.type = in.u32(); entity.variant = in.u32(); entity.init_seed = in.u32();
    entity.x = in.f32(); entity.y = in.f32();
    entity.vx = in.f32(); entity.vy = in.f32();
    entity.size = in.f32();
    const uint8_t flags = in.u8();
    const uint8_t slot = in.u8();
    const uint8_t reserved0 = in.u8();
    const uint8_t reserved1 = in.u8();
    if (!in.ok()) return false;
    if ((flags & ~1u) != 0 || reserved0 != 0 || reserved1 != 0) return false;
    entity.player_alias = (flags & 1u) != 0;
    entity.player_slot = slot;
    return true;
}

void write_change(std::vector<uint8_t>& out, const FieldChange& change) {
    put_u64(out, change.id);
    put_u32(out, change.mask);
    if (change.mask & 1u) put_u32(out, change.type);
    if (change.mask & 2u) put_u32(out, change.variant);
    if (change.mask & 4u) put_u32(out, change.init_seed);
    if (change.mask & 8u) put_f32(out, change.x);
    if (change.mask & 16u) put_f32(out, change.y);
    if (change.mask & 32u) put_f32(out, change.vx);
    if (change.mask & 64u) put_f32(out, change.vy);
    if (change.mask & 128u) put_f32(out, change.size);
}

bool read_change(ByteReader& in, FieldChange& change) {
    change.id = in.u64();
    change.mask = in.u32();
    if (!in.ok()) return false;
    if (change.mask > 0xffu) return false;
    if (change.mask & 1u) change.type = in.u32();
    if (change.mask & 2u) change.variant = in.u32();
    if (change.mask & 4u) change.init_seed = in.u32();
    if (change.mask & 8u) change.x = in.f32();
    if (change.mask & 16u) change.y = in.f32();
    if (change.mask & 32u) change.vx = in.f32();
    if (change.mask & 64u) change.vy = in.f32();
    if (change.mask & 128u) change.size = in.f32();
    return in.ok();
}

Encoded finish_packet(uint16_t flags, uint32_t sequence, const std::vector<uint8_t>& payload) {
    Encoded encoded;
    if (sequence == 0) { encoded.error = ModelError::bad_flags; return encoded; }
    encoded.bytes.reserve(16 + payload.size());
    put_u32(encoded.bytes, kSnapshotMagic);
    put_u16(encoded.bytes, kSnapshotVersion);
    put_u16(encoded.bytes, flags);
    put_u32(encoded.bytes, sequence);
    put_u32(encoded.bytes, 0);
    encoded.bytes.insert(encoded.bytes.end(), payload.begin(), payload.end());
    if (encoded.bytes.size() > kMaxSnapshotBytes) { encoded.bytes.clear(); encoded.error = ModelError::bad_count; return encoded; }
    seal_checksum(encoded.bytes);
    return encoded;
}

uint32_t diff_mask(const NetEntity& previous, const NetEntity& next) {
    uint32_t mask = 0;
    if (previous.type != next.type) mask |= 1u;
    if (previous.variant != next.variant) mask |= 2u;
    if (previous.init_seed != next.init_seed) mask |= 4u;
    if (!same_float(previous.x, next.x)) mask |= 8u;
    if (!same_float(previous.y, next.y)) mask |= 16u;
    if (!same_float(previous.vx, next.vx)) mask |= 32u;
    if (!same_float(previous.vy, next.vy)) mask |= 64u;
    if (!same_float(previous.size, next.size)) mask |= 128u;
    return mask;
}

void apply_mask(NetEntity& entity, const FieldChange& change) {
    if (change.mask & 1u) entity.type = change.type;
    if (change.mask & 2u) entity.variant = change.variant;
    if (change.mask & 4u) entity.init_seed = change.init_seed;
    if (change.mask & 8u) entity.x = change.x;
    if (change.mask & 16u) entity.y = change.y;
    if (change.mask & 32u) entity.vx = change.vx;
    if (change.mask & 64u) entity.vy = change.vy;
    if (change.mask & 128u) entity.size = change.size;
}

ModelError apply_delta(const WorldSnapshot& world, const DeltaBody& delta, WorldSnapshot& out) {
    if (delta.room_index != world.room_index) return ModelError::needs_keyframe;
    if (delta.base_frame != world.frame || delta.frame <= world.frame) return ModelError::needs_keyframe;
    if (const auto players = check_players(delta.players); players != ModelError::ok) return players;
    std::unordered_map<uint64_t, const NetEntity*> current;
    for (const auto& entity : world.entities) current.emplace(entity.id, &entity);
    std::unordered_set<uint64_t> removed;
    for (auto id : delta.removed) {
        if (id == 0 || !current.count(id) || !removed.insert(id).second) return ModelError::needs_keyframe;
    }
    std::unordered_map<uint64_t, const FieldChange*> changes;
    for (const auto& change : delta.changed) {
        if (change.id == 0 || !current.count(change.id) || removed.count(change.id) || !changes.emplace(change.id, &change).second)
            return ModelError::needs_keyframe;
        if (change.mask > 0xffu) return ModelError::bad_flags;
    }
    std::unordered_set<uint64_t> added;
    for (const auto& entity : delta.added) {
        if (entity.id == 0 || current.count(entity.id) || !added.insert(entity.id).second) return ModelError::needs_keyframe;
    }
    if (const auto added_ok = check_entities(delta.added); added_ok != ModelError::ok) return added_ok;
    WorldSnapshot next = world;
    next.frame = delta.frame;
    next.room_index = delta.room_index;
    next.previous_room = delta.previous_room;
    next.players = delta.players;
    next.entities.clear();
    for (const auto& entity : world.entities) {
        if (removed.count(entity.id)) continue;
        NetEntity copy = entity;
        if (const auto it = changes.find(entity.id); it != changes.end()) apply_mask(copy, *it->second);
        next.entities.push_back(copy);
    }
    next.entities.insert(next.entities.end(), delta.added.begin(), delta.added.end());
    std::sort(next.entities.begin(), next.entities.end(), [](const NetEntity& a, const NetEntity& b) { return a.id < b.id; });
    if (const auto entities = check_entities(next.entities); entities != ModelError::ok) return entities;
    out = std::move(next);
    return ModelError::ok;
}

ModelError precheck_capture(const NativeCapture& capture) {
    if (capture.players.size() > kMaxNativePlayers || capture.entities.size() > kMaxNativeEntities) return ModelError::bad_count;
    std::unordered_set<uint32_t> pointers;
    for (const auto& player : capture.players) {
        if (player.pointer == 0) return ModelError::bad_pointer;
        if (!pointers.insert(player.pointer).second) return ModelError::bad_pointer;
        if (!finite_float(player.x) || !finite_float(player.y) || !finite_float(player.vx) ||
            !finite_float(player.vy) || !finite_float(player.size)) return ModelError::nonfinite;
    }
    std::unordered_set<uint32_t> entities;
    for (const auto& entity : capture.entities) {
        if (!finite_float(entity.x) || !finite_float(entity.y) || !finite_float(entity.vx) ||
            !finite_float(entity.vy) || !finite_float(entity.size)) return ModelError::nonfinite;
        if (entity.pointer == 0) continue;
        if (!entities.insert(entity.pointer).second) return ModelError::bad_pointer;
    }
    return ModelError::ok;
}
}

const char* model_error_name(ModelError error) {
    switch (error) {
    case ModelError::ok: return "ok";
    case ModelError::truncated: return "truncated";
    case ModelError::bad_magic: return "bad_magic";
    case ModelError::bad_version: return "bad_version";
    case ModelError::bad_checksum: return "bad_checksum";
    case ModelError::bad_flags: return "bad_flags";
    case ModelError::bad_count: return "bad_count";
    case ModelError::bad_pointer: return "bad_pointer";
    case ModelError::duplicate_id: return "duplicate_id";
    case ModelError::nonfinite: return "nonfinite";
    case ModelError::trailing: return "trailing";
    case ModelError::stale: return "stale";
    case ModelError::duplicate: return "duplicate";
    case ModelError::needs_keyframe: return "needs_keyframe";
    case ModelError::buffered: return "buffered";
    case ModelError::incompatible: return "incompatible";
    }
    return "unknown";
}

uint32_t crc32_ieee(const uint8_t* data, size_t size) {
    uint32_t crc = 0xffffffffu;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            const uint32_t mask = 0u - (crc & 1u);
            crc = (crc >> 1) ^ (0xedb88320u & mask);
        }
    }
    return ~crc;
}

void NativeCaptureBuilder::set_header(uint32_t frame, uint32_t room_index, uint32_t previous_room) {
    frame_ = frame; room_ = room_index; previous_ = previous_room; header_ = true;
}
bool NativeCaptureBuilder::add_player(uint32_t pointer, float x, float y, float vx, float vy, float size) {
    if (players_.size() >= kMaxNativePlayers) return false;
    players_.push_back(NativePlayer{pointer, x, y, vx, vy, size});
    return true;
}
bool NativeCaptureBuilder::add_entity(uint32_t pointer, uint32_t type, uint32_t variant, uint32_t init_seed,
                                      float x, float y, float vx, float vy, float size) {
    if (entities_.size() >= kMaxNativeEntities) return false;
    entities_.push_back(NativeEntity{pointer, type, variant, init_seed, x, y, vx, vy, size});
    return true;
}
std::vector<uint8_t> NativeCaptureBuilder::finish() const {
    std::vector<uint8_t> out;
    if (!header_) return out;
    put_u32(out, frame_); put_u32(out, room_); put_u32(out, previous_);
    put_u32(out, static_cast<uint32_t>(players_.size()));
    for (const auto& player : players_) {
        put_u32(out, player.pointer);
        put_f32(out, player.x); put_f32(out, player.y);
        put_f32(out, player.vx); put_f32(out, player.vy);
        put_f32(out, player.size);
    }
    put_u32(out, static_cast<uint32_t>(entities_.size()));
    for (const auto& entity : entities_) {
        put_u32(out, entity.pointer);
        put_u32(out, entity.type); put_u32(out, entity.variant); put_u32(out, entity.init_seed);
        put_f32(out, entity.x); put_f32(out, entity.y);
        put_f32(out, entity.vx); put_f32(out, entity.vy);
        put_f32(out, entity.size);
    }
    return out;
}

ModelError parse_native_capture(const uint8_t* data, size_t size, NativeCapture& out) {
    if (data == nullptr || size < 16) return ModelError::truncated;
    ByteReader in(data, size);
    NativeCapture capture;
    capture.frame = in.u32();
    capture.room_index = in.u32();
    capture.previous_room = in.u32();
    const uint32_t player_count = in.u32();
    if (!in.ok()) return ModelError::truncated;
    if (player_count > kMaxNativePlayers) return ModelError::bad_count;
    capture.players.reserve(player_count);
    for (uint32_t i = 0; i < player_count; ++i) {
        NativePlayer player;
        player.pointer = in.u32();
        player.x = in.f32(); player.y = in.f32();
        player.vx = in.f32(); player.vy = in.f32();
        player.size = in.f32();
        capture.players.push_back(player);
    }
    const uint32_t entity_count = in.u32();
    if (!in.ok()) return ModelError::truncated;
    if (entity_count > kMaxNativeEntities) return ModelError::bad_count;
    capture.entities.reserve(entity_count);
    for (uint32_t i = 0; i < entity_count; ++i) {
        NativeEntity entity;
        entity.pointer = in.u32();
        entity.type = in.u32(); entity.variant = in.u32(); entity.init_seed = in.u32();
        entity.x = in.f32(); entity.y = in.f32();
        entity.vx = in.f32(); entity.vy = in.f32();
        entity.size = in.f32();
        capture.entities.push_back(entity);
    }
    if (!in.ok()) return ModelError::truncated;
    if (!in.finish()) return ModelError::trailing;
    out = std::move(capture);
    return ModelError::ok;
}

Encoded encode_snapshot(const SnapshotPacket& packet) {
    std::vector<uint8_t> payload;
    if (packet.keyframe) {
        if (const auto players = check_players(packet.full.players); players != ModelError::ok) return Encoded{players, {}};
        if (const auto entities = check_entities(packet.full.entities); entities != ModelError::ok) return Encoded{entities, {}};
        put_u32(payload, packet.full.frame);
        put_u32(payload, packet.full.room_index);
        put_u32(payload, packet.full.previous_room);
        put_u32(payload, static_cast<uint32_t>(packet.full.players.size()));
        for (const auto& player : packet.full.players) write_player(payload, player);
        put_u32(payload, static_cast<uint32_t>(packet.full.entities.size()));
        for (const auto& entity : packet.full.entities) write_entity(payload, entity);
        return finish_packet(kSnapshotKeyframe, packet.sequence, payload);
    }
    if (const auto players = check_players(packet.delta.players); players != ModelError::ok) return Encoded{players, {}};
    if (const auto added = check_entities(packet.delta.added); added != ModelError::ok) return Encoded{added, {}};
    put_u32(payload, packet.delta.base_frame);
    put_u32(payload, packet.delta.frame);
    put_u32(payload, packet.delta.room_index);
    put_u32(payload, packet.delta.previous_room);
    put_u32(payload, static_cast<uint32_t>(packet.delta.players.size()));
    for (const auto& player : packet.delta.players) write_player(payload, player);
    put_u32(payload, static_cast<uint32_t>(packet.delta.removed.size()));
    for (auto id : packet.delta.removed) put_u64(payload, id);
    put_u32(payload, static_cast<uint32_t>(packet.delta.added.size()));
    for (const auto& entity : packet.delta.added) write_entity(payload, entity);
    put_u32(payload, static_cast<uint32_t>(packet.delta.changed.size()));
    for (const auto& change : packet.delta.changed) {
        if (change.mask > 0xffu) return Encoded{ModelError::bad_flags, {}};
        write_change(payload, change);
    }
    return finish_packet(kSnapshotDelta, packet.sequence, payload);
}

DecodedSnapshot decode_snapshot(const uint8_t* data, size_t size) {
    DecodedSnapshot decoded;
    if (data == nullptr || size < 16) { decoded.error = ModelError::truncated; return decoded; }
    if (read_u32(data) != kSnapshotMagic) { decoded.error = ModelError::bad_magic; return decoded; }
    if (data[4] != static_cast<uint8_t>(kSnapshotVersion) || data[5] != 0) { decoded.error = ModelError::bad_version; return decoded; }
    if (!checksum_ok(data, size)) { decoded.error = ModelError::bad_checksum; return decoded; }
    ByteReader in(data + 6, size - 6);
    const uint16_t flags = in.u16();
    const uint32_t sequence = in.u32();
    (void)in.u32(); // checksum already verified
    if (sequence == 0 || (flags != kSnapshotKeyframe && flags != kSnapshotDelta)) {
        decoded.error = ModelError::bad_flags;
        return decoded;
    }
    SnapshotPacket packet;
    packet.sequence = sequence;
    packet.keyframe = flags == kSnapshotKeyframe;
    if (packet.keyframe) {
        packet.full.frame = in.u32();
        packet.full.room_index = in.u32();
        packet.full.previous_room = in.u32();
        const uint32_t players = in.u32();
        if (players > kMaxNativePlayers) { decoded.error = ModelError::bad_count; return decoded; }
        for (uint32_t i = 0; i < players; ++i) packet.full.players.push_back(read_player(in));
        const uint32_t entities = in.u32();
        if (entities > kMaxNativeEntities) { decoded.error = ModelError::bad_count; return decoded; }
        for (uint32_t i = 0; i < entities; ++i) {
            NetEntity entity;
            if (!read_entity(in, entity)) { decoded.error = in.ok() ? ModelError::bad_flags : ModelError::truncated; return decoded; }
            packet.full.entities.push_back(entity);
        }
        if (!in.ok()) { decoded.error = ModelError::truncated; return decoded; }
        if (!in.finish()) { decoded.error = ModelError::trailing; return decoded; }
        if (const auto player_ok = check_players(packet.full.players); player_ok != ModelError::ok) { decoded.error = player_ok; return decoded; }
        if (const auto entity_ok = check_entities(packet.full.entities); entity_ok != ModelError::ok) { decoded.error = entity_ok; return decoded; }
    } else {
        packet.delta.base_frame = in.u32();
        packet.delta.frame = in.u32();
        packet.delta.room_index = in.u32();
        packet.delta.previous_room = in.u32();
        const uint32_t players = in.u32();
        if (players > kMaxNativePlayers) { decoded.error = ModelError::bad_count; return decoded; }
        for (uint32_t i = 0; i < players; ++i) packet.delta.players.push_back(read_player(in));
        const uint32_t removed = in.u32();
        if (removed > kMaxNativeEntities) { decoded.error = ModelError::bad_count; return decoded; }
        for (uint32_t i = 0; i < removed; ++i) packet.delta.removed.push_back(in.u64());
        const uint32_t added = in.u32();
        if (added > kMaxNativeEntities) { decoded.error = ModelError::bad_count; return decoded; }
        for (uint32_t i = 0; i < added; ++i) {
            NetEntity entity;
            if (!read_entity(in, entity)) { decoded.error = in.ok() ? ModelError::bad_flags : ModelError::truncated; return decoded; }
            packet.delta.added.push_back(entity);
        }
        const uint32_t changed = in.u32();
        if (!in.ok()) { decoded.error = ModelError::truncated; return decoded; }
        if (changed > kMaxNativeEntities) { decoded.error = ModelError::bad_count; return decoded; }
        for (uint32_t i = 0; i < changed; ++i) {
            FieldChange change;
            if (!read_change(in, change)) { decoded.error = in.ok() ? ModelError::bad_flags : ModelError::truncated; return decoded; }
            packet.delta.changed.push_back(change);
        }
        if (!in.ok()) { decoded.error = ModelError::truncated; return decoded; }
        if (!in.finish()) { decoded.error = ModelError::trailing; return decoded; }
        if (const auto player_ok = check_players(packet.delta.players); player_ok != ModelError::ok) { decoded.error = player_ok; return decoded; }
        if (const auto added_ok = check_entities(packet.delta.added); added_ok != ModelError::ok) { decoded.error = added_ok; return decoded; }
    }
    decoded.packet = std::move(packet);
    return decoded;
}

HostPublisher::HostPublisher(uint32_t keyframe_interval) : interval_(keyframe_interval == 0 ? 1 : keyframe_interval) {}
void HostPublisher::set_keyframe_interval(uint32_t frames) { interval_ = frames == 0 ? 1 : frames; }

PublishResult HostPublisher::publish(const NativeCapture& capture) {
    PublishResult result;
    if (const auto checked = precheck_capture(capture); checked != ModelError::ok) { result.error = checked; return result; }
    if (have_ && capture.frame < previous_.frame) { result.error = ModelError::stale; return result; }
    if (have_ && capture.frame == previous_.frame && !force_ && capture.room_index == previous_.room_index) {
        result.error = ModelError::stale;
        return result;
    }
    auto map = by_pointer_;
    uint64_t next_id = next_id_;
    std::unordered_set<uint32_t> seen;
    auto identify = [&](uint32_t pointer, uint32_t seed) {
        seen.insert(pointer);
        if (const auto it = map.find(pointer); it != map.end()) {
            if (it->second.seed == seed) return it->second.id;
            map.erase(it);
        }
        const uint64_t id = next_id++;
        map.emplace(pointer, Live{id, seed});
        return id;
    };
    std::unordered_map<uint32_t, uint32_t> slot_by_pointer;
    WorldSnapshot snapshot;
    snapshot.frame = capture.frame;
    snapshot.room_index = capture.room_index;
    snapshot.previous_room = capture.previous_room;
    snapshot.players.reserve(capture.players.size());
    for (uint32_t i = 0; i < capture.players.size(); ++i) {
        const auto& player = capture.players[i];
        slot_by_pointer.emplace(player.pointer, i);
        snapshot.players.push_back(NetPlayer{i, player.x, player.y, player.vx, player.vy, player.size});
    }
    for (const auto& entity : capture.entities) {
        if (entity.pointer == 0) continue;
        NetEntity net;
        net.id = identify(entity.pointer, entity.init_seed);
        net.type = entity.type; net.variant = entity.variant; net.init_seed = entity.init_seed;
        net.x = entity.x; net.y = entity.y; net.vx = entity.vx; net.vy = entity.vy; net.size = entity.size;
        if (const auto slot = slot_by_pointer.find(entity.pointer); slot != slot_by_pointer.end()) {
            net.player_alias = true;
            net.player_slot = slot->second;
        }
        snapshot.entities.push_back(net);
    }
    for (auto it = map.begin(); it != map.end();) {
        if (!seen.count(it->first)) it = map.erase(it);
        else ++it;
    }
    std::sort(snapshot.entities.begin(), snapshot.entities.end(), [](const NetEntity& a, const NetEntity& b) { return a.id < b.id; });
    if (const auto entities = check_entities(snapshot.entities); entities != ModelError::ok) { result.error = entities; return result; }

    bool alias_changed = false;
    DeltaBody delta;
    if (have_) {
        std::unordered_map<uint64_t, const NetEntity*> previous;
        for (const auto& entity : previous_.entities) previous.emplace(entity.id, &entity);
        for (const auto& entity : snapshot.entities) {
            if (const auto it = previous.find(entity.id); it == previous.end()) delta.added.push_back(entity);
            else {
                if (it->second->player_alias != entity.player_alias || it->second->player_slot != entity.player_slot) alias_changed = true;
                if (const uint32_t mask = diff_mask(*it->second, entity)) {
                    FieldChange change;
                    change.id = entity.id; change.mask = mask;
                    change.type = entity.type; change.variant = entity.variant; change.init_seed = entity.init_seed;
                    change.x = entity.x; change.y = entity.y; change.vx = entity.vx; change.vy = entity.vy; change.size = entity.size;
                    delta.changed.push_back(change);
                }
                previous.erase(it);
            }
        }
        for (const auto& entry : previous) delta.removed.push_back(entry.first);
        std::sort(delta.removed.begin(), delta.removed.end());
        std::sort(delta.added.begin(), delta.added.end(), [](const NetEntity& a, const NetEntity& b) { return a.id < b.id; });
        std::sort(delta.changed.begin(), delta.changed.end(), [](const FieldChange& a, const FieldChange& b) { return a.id < b.id; });
    }
    const bool keyframe = force_ || !have_ || alias_changed || snapshot.room_index != previous_.room_index ||
        snapshot.frame < last_key_frame_ || snapshot.frame - last_key_frame_ >= interval_;
    SnapshotPacket packet;
    packet.sequence = next_seq_;
    packet.keyframe = keyframe;
    packet.full = snapshot;
    delta.base_frame = previous_.frame;
    delta.frame = snapshot.frame;
    delta.room_index = snapshot.room_index;
    delta.previous_room = snapshot.previous_room;
    delta.players = snapshot.players;
    packet.delta = std::move(delta);
    auto encoded = encode_snapshot(packet);
    if (encoded.error != ModelError::ok) { result.error = encoded.error; return result; }
    by_pointer_ = std::move(map);
    next_id_ = next_id;
    previous_ = snapshot;
    have_ = true;
    force_ = false;
    if (keyframe) last_key_frame_ = snapshot.frame;
    ++next_seq_;
    result.sent_keyframe = keyframe;
    result.sequence = packet.sequence;
    result.bytes = std::move(encoded.bytes);
    result.snapshot = std::move(snapshot);
    return result;
}

void GuestIngress::note_applied(uint32_t sequence) {
    applied_.insert(sequence);
    if (sequence > highest_seq_) highest_seq_ = sequence;
    if (applied_.size() > 4096) {
        for (auto it = applied_.begin(); it != applied_.end();) {
            if (*it + 4096 < highest_seq_) it = applied_.erase(it);
            else ++it;
        }
    }
}

void GuestIngress::resync() {
    buffered_.clear();
    needs_keyframe_ = true;
}

void GuestIngress::remember(const SnapshotPacket& packet) {
    if (buffered_.size() >= kIngressWindow) {
        buffered_.clear();
        needs_keyframe_ = true;
        return;
    }
    buffered_.emplace(packet.sequence, packet);
}

ModelError GuestIngress::drain() {
    bool progressed = true;
    while (progressed) {
        progressed = false;
        for (auto it = buffered_.begin(); it != buffered_.end(); ++it) {
            const auto& packet = it->second;
            if (packet.keyframe || packet.delta.base_frame != last_frame_ || packet.delta.frame <= last_frame_) continue;
            SnapshotPacket next = packet;
            buffered_.erase(it);
            const auto applied = try_apply_delta(next);
            if (applied != ModelError::ok) return applied;
            progressed = true;
            break;
        }
    }
    for (auto it = buffered_.begin(); it != buffered_.end();) {
        const auto& packet = it->second;
        const uint32_t frame = packet.keyframe ? packet.full.frame : packet.delta.frame;
        const uint32_t base = packet.keyframe ? packet.full.frame : packet.delta.base_frame;
        if (frame < last_frame_ || (!packet.keyframe && base < last_frame_)) {
            note_applied(packet.sequence);
            it = buffered_.erase(it);
        } else ++it;
    }
    return ModelError::ok;
}

ModelError GuestIngress::apply_keyframe(const SnapshotPacket& packet) {
    if (have_ && packet.full.frame < last_frame_) {
        note_applied(packet.sequence);
        return ModelError::stale;
    }
    if (have_ && packet.full.frame == last_frame_ && !needs_keyframe_) {
        note_applied(packet.sequence);
        return ModelError::duplicate;
    }
    world_ = packet.full;
    std::sort(world_.players.begin(), world_.players.end(), [](const NetPlayer& a, const NetPlayer& b) { return a.slot < b.slot; });
    std::sort(world_.entities.begin(), world_.entities.end(), [](const NetEntity& a, const NetEntity& b) { return a.id < b.id; });
    last_frame_ = world_.frame;
    have_ = true;
    needs_keyframe_ = false;
    note_applied(packet.sequence);
    return drain() == ModelError::ok ? ModelError::ok : ModelError::needs_keyframe;
}

ModelError GuestIngress::try_apply_delta(const SnapshotPacket& packet) {
    WorldSnapshot next;
    const auto applied = apply_delta(world_, packet.delta, next);
    if (applied != ModelError::ok) {
        needs_keyframe_ = true;
        buffered_.clear();
        note_applied(packet.sequence);
        return ModelError::needs_keyframe;
    }
    world_ = std::move(next);
    last_frame_ = world_.frame;
    note_applied(packet.sequence);
    return ModelError::ok;
}

ModelError GuestIngress::accept(const uint8_t* data, size_t size) {
    if (incompatible_) return ModelError::incompatible;
    const auto decoded = decode_snapshot(data, size);
    if (decoded.error == ModelError::bad_version) { incompatible_ = true; return decoded.error; }
    if (decoded.error != ModelError::ok) return decoded.error;
    const auto& packet = decoded.packet;
    if (applied_.count(packet.sequence) || buffered_.count(packet.sequence)) return ModelError::duplicate;
    if (highest_seq_ >= 4096 && packet.sequence + 4096 < highest_seq_) return ModelError::stale;
    if (packet.keyframe) return apply_keyframe(packet);
    if (!have_ || needs_keyframe_) { remember(packet); return ModelError::needs_keyframe; }
    if (packet.delta.frame < last_frame_ || packet.delta.base_frame < last_frame_) {
        note_applied(packet.sequence);
        return ModelError::stale;
    }
    if (packet.delta.base_frame == last_frame_ && packet.delta.frame > last_frame_) {
        const auto applied = try_apply_delta(packet);
        if (applied != ModelError::ok) return applied;
        const auto drained = drain();
        return drained == ModelError::ok ? ModelError::ok : drained;
    }
    remember(packet);
    return needs_keyframe_ ? ModelError::needs_keyframe : ModelError::buffered;
}

bool GuestView::bind(uint64_t network_id, uint32_t local_token) {
    const auto* world = snapshot();
    if (world == nullptr || network_id == 0) return false;
    const bool found = std::any_of(world->entities.begin(), world->entities.end(),
                                   [&](const NetEntity& entity) { return entity.id == network_id; });
    if (!found) return false;
    bindings_[network_id] = local_token;
    return true;
}

RenderPlan GuestView::plan() const {
    RenderPlan plan;
    const auto* world = snapshot();
    if (world == nullptr) return plan;
    plan.has_snapshot = true;
    plan.frame = world->frame;
    plan.room_index = world->room_index;
    plan.previous_room = world->previous_room;
    for (const auto& player : world->players) {
        plan.players.push_back(RenderWrite{0, player.slot, 0, player.x, player.y, player.vx, player.vy, player.size});
    }
    std::unordered_set<uint64_t> live;
    for (const auto& entity : world->entities) {
        live.insert(entity.id);
        if (const auto it = bindings_.find(entity.id); it != bindings_.end()) {
            plan.bound_entities.push_back(RenderWrite{entity.id, entity.player_alias ? entity.player_slot : 0xffffffffu,
                                                      it->second, entity.x, entity.y, entity.vx, entity.vy, entity.size});
        } else plan.spawns.push_back(entity);
    }
    std::vector<std::pair<uint64_t, uint32_t>> despawns;
    for (const auto& binding : bindings_) {
        if (!live.count(binding.first)) despawns.emplace_back(binding.first, binding.second);
    }
    std::sort(despawns.begin(), despawns.end());
    for (const auto& despawn : despawns) {
        plan.despawn_ids.push_back(despawn.first);
        plan.despawn_tokens.push_back(despawn.second);
    }
    return plan;
}
}
