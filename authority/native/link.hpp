#pragma once
// Session handshake, state/input channels, reconnect, and snapshot recovery.
// The transport is an interface. LoopbackHub is an in-memory test double.
// This is not wired to SteamNetworkingMessages and it never reports playable.
#include "state_model.hpp"
#include <array>
#include <cstdint>
#include <functional>
#include <string>

namespace ia {

enum class LinkRole { capture, preview };
enum class LinkPhase { waiting, active, paused, incompatible };
enum class LinkError { ok, not_active, wrong_role, rejected, incompatible, send_failed, bad_packet, stale, needs_keyframe };

inline constexpr uint16_t kLinkVersion = 1;
inline constexpr uint32_t kControlMagic = 0x314C4149u; // 'IAL1'
inline constexpr uint32_t kInputMagic = 0x314E4149u;   // 'IAI1'
inline constexpr uint8_t kHelloReconnect = 1;
inline constexpr uint16_t kInputLeft = 1;
inline constexpr uint16_t kInputRight = 2;
inline constexpr uint16_t kInputUp = 4;
inline constexpr uint16_t kInputDown = 8;
inline constexpr uint16_t kInputShoot = 16;
inline constexpr uint16_t kInputBomb = 32;
inline constexpr uint16_t kInputItem = 64;
inline constexpr uint16_t kInputDrop = 128;
inline constexpr uint64_t kLinkTimeoutMs = 3000;

struct LinkConfig {
    LinkRole role{LinkRole::preview};
    std::string session{"test-session"};
    std::array<uint8_t, 32> manifest{};
    uint32_t keyframe_interval{kDefaultKeyframeInterval};
};

struct LinkFacts {
    bool research_only{true};
    bool playable{false};
    bool native_memory_apply{false};
    bool steam_transport_wired{false};
    bool in_game_verified{false};
};

struct HelloMessage {
    uint16_t type{1};
    LinkRole role{LinkRole::capture};
    uint8_t research_only{1};
    uint8_t flags{};
    uint32_t resume_frame{};
    std::string session;
    std::array<uint8_t, 32> manifest{};
};
struct DecodedHello {
    ModelError error{ModelError::ok};
    HelloMessage hello{};
};
struct InputFrame {
    uint32_t frame{};
    uint32_t player_slot{1};
    uint16_t buttons{};
    float aim_x{}, aim_y{};
};
struct DecodedInput {
    ModelError error{ModelError::ok};
    InputFrame frame{};
};
struct SendResult {
    LinkError error{LinkError::ok};
    bool keyframe{false};
    uint32_t sequence{};
    uint32_t frame{};
    std::vector<uint8_t> bytes;
};

Encoded encode_hello(const HelloMessage& hello);
DecodedHello decode_hello(const uint8_t* data, size_t size);
Encoded encode_input(const InputFrame& frame);
DecodedInput decode_input(const uint8_t* data, size_t size);

class Transport {
public:
    virtual ~Transport() = default;
    virtual bool send(uint8_t channel, const uint8_t* data, size_t size) = 0;
    // `data` is valid only for the duration of the callback.
    virtual void poll(const std::function<void(uint8_t, const uint8_t*, size_t)>& callback) = 0;
};

class LoopbackHub {
    struct Endpoint : Transport {
        LoopbackHub* hub{};
        int id{};
        bool send(uint8_t channel, const uint8_t* data, size_t size) override;
        void poll(const std::function<void(uint8_t, const uint8_t*, size_t)>& callback) override;
    };
    struct Datagram {
        uint8_t channel{};
        std::vector<uint8_t> bytes;
    };
    Endpoint ends_[2];
    std::vector<Datagram> queues_[2];
    int drop_[2]{};
    bool duplicate_[2]{};
    bool reorder_[2]{};
    std::vector<Datagram> held_[2];
    bool enqueue(int dest, uint8_t channel, const uint8_t* data, size_t size);
public:
    LoopbackHub();
    LoopbackHub(const LoopbackHub&) = delete;
    LoopbackHub& operator=(const LoopbackHub&) = delete;
    Transport& left() { return ends_[0]; }
    Transport& right() { return ends_[1]; }
    void drop_next(int dest, int count = 1);
    void duplicate_next(int dest);
    void reorder_next_pair(int dest);
    void inject(int dest, uint8_t channel, std::vector<uint8_t> bytes);
};

class AuthorityLink {
    LinkConfig config_;
    Transport& transport_;
    LinkPhase phase_{LinkPhase::waiting};
    HostPublisher publisher_;
    GuestView guest_;
    uint64_t last_rx_{0};
    bool sent_lock_{false};
    bool have_input_{false};
    bool have_sent_input_{false};
    InputFrame latest_{};
    uint32_t last_sent_frame_{0};
    bool session_ok_{false};
    void lock();
    void handle(uint8_t channel, const uint8_t* data, size_t size, uint64_t now);
    void handle_control(const uint8_t* data, size_t size, uint64_t now);
    void handle_state(const uint8_t* data, size_t size, uint64_t now);
    void handle_input(const uint8_t* data, size_t size, uint64_t now);
    bool send_hello(uint8_t flags, uint32_t resume_frame);
public:
    AuthorityLink(LinkConfig config, Transport& transport);
    LinkPhase phase() const { return phase_; }
    bool awaiting_keyframe() const { return config_.role == LinkRole::preview && guest_.needs_keyframe(); }
    // Constants. GuestApply can stage pose writes through a test double; this link
    // still does not call it, and no live session can flip these flags.
    LinkFacts facts() const { return LinkFacts{true, false, false, false, false}; }
    bool playable() const { return false; }
    bool start(uint64_t now_ms);
    bool reconnect(uint64_t now_ms);
    void poll(uint64_t now_ms);
    void tick(uint64_t now_ms);
    SendResult publish_capture(const NativeCapture& capture, uint64_t now_ms);
    LinkError publish_input(const InputFrame& frame, uint64_t now_ms);
    const InputFrame* latest_input() const { return have_input_ ? &latest_ : nullptr; }
    const WorldSnapshot* snapshot() const { return config_.role == LinkRole::preview ? guest_.snapshot() : nullptr; }
    RenderPlan plan() const { return config_.role == LinkRole::preview ? guest_.plan() : RenderPlan{}; }
    bool bind_entity(uint64_t network_id, uint32_t local_token);
    void force_keyframe() { publisher_.force_keyframe(); }
};

}
