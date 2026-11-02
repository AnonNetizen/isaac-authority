#pragma once
// Pointer-free world snapshot model for the J460 co-op research prototype.
//
// The live probe still records host-local pointers in the native capture blob
// (see probe.cpp). HostPublisher strips those pointers and assigns stable network
// ids. Nothing in this header writes game memory, and nothing here is playable.
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace ia {

inline constexpr uint32_t kSnapshotMagic = 0x31574149u; // 'IAW1' little-endian
inline constexpr uint16_t kSnapshotVersion = 1;
inline constexpr uint16_t kSnapshotKeyframe = 1;
inline constexpr uint16_t kSnapshotDelta = 2;
inline constexpr size_t kMaxSnapshotBytes = 256 * 1024;
inline constexpr size_t kMaxNativePlayers = 8;
inline constexpr size_t kMaxNativeEntities = 128;
inline constexpr unsigned kDefaultKeyframeInterval = 30;
inline constexpr unsigned kIngressWindow = 32;
// How many published captures an entity may miss and still keep its network id.
// A capture is one successful HostPublisher::publish() in the same run and room.
// Misses of 1..kIdentityGraceCaptures stay on the wire under the last pose.
// The next miss retires the id once. This is not a wire-format field.
inline constexpr uint32_t kIdentityGraceCaptures = 3;
// Intended SteamNetworkingMessages channels once the live DLL is wired.
// SteamTransport still uses kChannel (197460) for the older JSON session only.
inline constexpr uint8_t kChannelControl = 1;
inline constexpr uint8_t kChannelState = 2;
inline constexpr uint8_t kChannelInput = 3;
inline constexpr int kSteamControlChannel = 197461;
inline constexpr int kSteamStateChannel = 197462;
inline constexpr int kSteamInputChannel = 197463;

// Offsets a future in-process guest writer would use. GuestView never writes them.
struct GuestWriteOffsets {
    static constexpr uint32_t position = 0x33C;
    static constexpr uint32_t velocity = 0x360;
    static constexpr uint32_t size = 0x370;
};

enum class ModelError {
    ok,
    truncated,
    bad_magic,
    bad_version,
    bad_checksum,
    bad_flags,
    bad_count,
    bad_pointer,
    duplicate_id,
    nonfinite,
    trailing,
    stale,
    duplicate,
    needs_keyframe,
    buffered,
    incompatible
};

const char* model_error_name(ModelError error);
uint32_t crc32_ieee(const uint8_t* data, size_t size);

inline void put_u16(std::vector<uint8_t>& out, uint16_t value) {
    out.push_back(static_cast<uint8_t>(value));
    out.push_back(static_cast<uint8_t>(value >> 8));
}
inline void put_u32(std::vector<uint8_t>& out, uint32_t value) {
    out.push_back(static_cast<uint8_t>(value));
    out.push_back(static_cast<uint8_t>(value >> 8));
    out.push_back(static_cast<uint8_t>(value >> 16));
    out.push_back(static_cast<uint8_t>(value >> 24));
}
inline void put_u64(std::vector<uint8_t>& out, uint64_t value) {
    put_u32(out, static_cast<uint32_t>(value));
    put_u32(out, static_cast<uint32_t>(value >> 32));
}
inline void put_f32(std::vector<uint8_t>& out, float value) {
    uint32_t bits = 0;
    static_assert(sizeof(float) == 4, "float is 4 bytes");
    std::memcpy(&bits, &value, 4);
    put_u32(out, bits);
}
inline uint32_t read_u32(const uint8_t* data) {
    return static_cast<uint32_t>(data[0]) | (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) | (static_cast<uint32_t>(data[3]) << 24);
}

class ByteReader {
    const uint8_t* p_;
    const uint8_t* end_;
    bool ok_{true};
public:
    ByteReader(const uint8_t* data, size_t size) : p_(data), end_(data + size) {}
    bool ok() const { return ok_; }
    size_t remaining() const { return ok_ && p_ <= end_ ? static_cast<size_t>(end_ - p_) : 0; }
    bool finish() const { return ok_ && p_ == end_; }
    uint32_t u32() {
        if (remaining() < 4) { ok_ = false; return 0; }
        const uint32_t value = read_u32(p_);
        p_ += 4;
        return value;
    }
    uint16_t u16() {
        if (remaining() < 2) { ok_ = false; return 0; }
        const uint16_t value = static_cast<uint16_t>(p_[0] | (p_[1] << 8));
        p_ += 2;
        return value;
    }
    uint64_t u64() {
        const uint32_t lo = u32();
        const uint32_t hi = u32();
        return static_cast<uint64_t>(lo) | (static_cast<uint64_t>(hi) << 32);
    }
    float f32() {
        const uint32_t bits = u32();
        float value = 0;
        std::memcpy(&value, &bits, 4);
        return value;
    }
    uint8_t u8() {
        if (remaining() < 1) { ok_ = false; return 0; }
        return *p_++;
    }
};

struct NativePlayer {
    uint32_t pointer{};
    float x{}, y{}, vx{}, vy{}, size{};
};
struct NativeEntity {
    uint32_t pointer{};
    uint32_t type{}, variant{}, init_seed{};
    float x{}, y{}, vx{}, vy{}, size{};
};
// Raw probe capture. `pointer` is host-process-local and must not be sent to a guest.
struct NativeCapture {
    uint32_t frame{}, room_index{}, previous_room{};
    std::vector<NativePlayer> players;
    std::vector<NativeEntity> entities;
};

struct NetPlayer {
    uint32_t slot{};
    float x{}, y{}, vx{}, vy{}, size{};
};
struct NetEntity {
    uint64_t id{};
    uint32_t type{}, variant{}, init_seed{};
    float x{}, y{}, vx{}, vy{}, size{};
    bool player_alias{false};
    uint32_t player_slot{};
};
struct WorldSnapshot {
    uint32_t frame{}, room_index{}, previous_room{};
    std::vector<NetPlayer> players;
    std::vector<NetEntity> entities;
};

struct FieldChange {
    uint64_t id{};
    uint32_t mask{};
    uint32_t type{}, variant{}, init_seed{};
    float x{}, y{}, vx{}, vy{}, size{};
};
struct DeltaBody {
    uint32_t base_frame{}, frame{}, room_index{}, previous_room{};
    std::vector<NetPlayer> players;
    std::vector<uint64_t> removed;
    std::vector<NetEntity> added;
    std::vector<FieldChange> changed;
};
struct SnapshotPacket {
    uint32_t sequence{};
    bool keyframe{false};
    WorldSnapshot full{};
    DeltaBody delta{};
};
struct DecodedSnapshot {
    ModelError error{ModelError::ok};
    SnapshotPacket packet{};
};
struct Encoded {
    ModelError error{ModelError::ok};
    std::vector<uint8_t> bytes;
};

// Serializes the same byte layout probe.cpp records. Pointers are included here
// on purpose; HostPublisher is what removes them.
class NativeCaptureBuilder {
    uint32_t frame_{}, room_{}, previous_{};
    bool header_{false};
    std::vector<NativePlayer> players_;
    std::vector<NativeEntity> entities_;
public:
    void set_header(uint32_t frame, uint32_t room_index, uint32_t previous_room);
    bool add_player(uint32_t pointer, float x, float y, float vx, float vy, float size);
    bool add_entity(uint32_t pointer, uint32_t type, uint32_t variant, uint32_t init_seed,
                    float x, float y, float vx, float vy, float size);
    std::vector<uint8_t> finish() const;
};

ModelError parse_native_capture(const uint8_t* data, size_t size, NativeCapture& out);
Encoded encode_snapshot(const SnapshotPacket& packet);
DecodedSnapshot decode_snapshot(const uint8_t* data, size_t size);

struct PublishResult {
    ModelError error{ModelError::ok};
    bool sent_keyframe{false};
    uint32_t sequence{};
    std::vector<uint8_t> bytes;
    WorldSnapshot snapshot{};
};

// Host-only identity map.
//
// A network id follows the captured triple Type (+0x28), Variant (+0x2C), and
// InitSeed (+0x3EC). +0x3DC is a different seed and is not part of the triple.
// The host pointer is not the identity. It is a hint used when several tracked
// rows share the triple:
//   1. a row whose hint equals the captured pointer wins that row;
//   2. otherwise the smaller network id is paired with the earlier capture row.
// New rows take the next monotonic id in capture order. Ids are not recycled.
//
// A tracked row that is absent, and whose pointer hint is not occupied by this
// capture, may miss kIdentityGraceCaptures publishes and keep its id. The
// published snapshot keeps the last pose, so the guest does not see a removal
// plus an add. The following miss drops it. A delta lists that id in `removed`
// once; a keyframe simply omits it, and the next delta does not list it again.
// If the hint address shows up on a different row, the old id is retired
// immediately and is not given to the new row. A player-alias row is retired
// immediately when its slot is already claimed by a live row. Grace rows that
// would push the snapshot past kMaxNativeEntities are dropped in that same
// publish, most misses first and then the highest id.
//
// A room change, or a new run (frame number goes backwards), clears the map
// before assignment. An interval keyframe or force_keyframe() does not.
// Player slots are still the player identity, never EntityPlayer*.
class HostPublisher {
    struct Tracked {
        uint64_t id{0};
        uint32_t type{0};
        uint32_t variant{0};
        uint32_t init_seed{0};
        uint32_t pointer_hint{0};
        uint32_t misses{0};
        NetEntity pose{};
    };
    struct Assignment {
        std::vector<NetEntity> entities;
        std::vector<Tracked> tracked;
        uint64_t next_id{1};
    };
    static Assignment assign_identities(std::vector<Tracked> tracked, uint64_t next_id, const NativeCapture& capture,
                                        const std::unordered_map<uint32_t, uint32_t>& slots);
    std::vector<Tracked> tracked_;
    uint64_t next_id_{1};
    uint32_t next_seq_{1};
    uint32_t interval_{kDefaultKeyframeInterval};
    uint32_t last_key_frame_{0};
    bool have_{false};
    bool force_{true};
    WorldSnapshot previous_{};
public:
    explicit HostPublisher(uint32_t keyframe_interval = kDefaultKeyframeInterval);
    void force_keyframe() { force_ = true; }
    void set_keyframe_interval(uint32_t frames);
    PublishResult publish(const NativeCapture& capture);
};

class GuestIngress {
    WorldSnapshot world_{};
    bool have_{false};
    bool needs_keyframe_{true};
    bool incompatible_{false};
    uint32_t last_frame_{0};
    uint32_t highest_seq_{0};
    // Sequence of the newest applied keyframe. Deltas published before it belong
    // to the previous run and must not chain once frame numbers are reused.
    uint32_t keyframe_seq_{0};
    std::unordered_map<uint32_t, SnapshotPacket> buffered_;
    std::unordered_set<uint32_t> applied_;
    void note_applied(uint32_t sequence);
    ModelError apply_keyframe(const SnapshotPacket& packet);
    ModelError try_apply_delta(const SnapshotPacket& packet);
    void remember(const SnapshotPacket& packet);
    ModelError drain();
public:
    ModelError accept(const uint8_t* data, size_t size);
    // Drops the sequence window and the applied world. The next keyframe is
    // accepted at any frame, including a host that restarted at sequence 1.
    // A same-room restart that keeps the publisher's sequence does not need this.
    void resync();
    const WorldSnapshot* snapshot() const { return have_ ? &world_ : nullptr; }
    bool needs_keyframe() const { return needs_keyframe_; }
    bool incompatible() const { return incompatible_; }
    uint32_t frame() const { return have_ ? last_frame_ : 0; }
};

struct RenderWrite {
    uint64_t network_id{};
    uint32_t player_slot{0xffffffffu};
    uint32_t local_token{};
    float x{}, y{}, vx{}, vy{}, size{};
};
struct RenderPlan {
    bool has_snapshot{false};
    uint32_t frame{}, room_index{}, previous_room{};
    std::vector<RenderWrite> players;
    std::vector<RenderWrite> bound_entities;
    std::vector<NetEntity> spawns;
    std::vector<uint64_t> despawn_ids;
    std::vector<uint32_t> despawn_tokens;
};

// Logical guest world. `local_token` stands in for a future guest-side pointer.
// plan() describes writes; it does not perform them.
class GuestView {
    GuestIngress ingress_;
    std::unordered_map<uint64_t, uint32_t> bindings_;
public:
    ModelError accept(const uint8_t* data, size_t size) { return ingress_.accept(data, size); }
    void resync() { ingress_.resync(); }
    bool bind(uint64_t network_id, uint32_t local_token);
    void unbind(uint64_t network_id) { bindings_.erase(network_id); }
    RenderPlan plan() const;
    const WorldSnapshot* snapshot() const { return ingress_.snapshot(); }
    bool needs_keyframe() const { return ingress_.needs_keyframe(); }
    bool incompatible() const { return ingress_.incompatible(); }
};

}
