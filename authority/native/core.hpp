#pragma once
#include <nlohmann/json.hpp>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
namespace ia {
using Json = nlohmann::json;
inline constexpr int kProtocol = 2;
inline constexpr int kChannel = 197460;
inline constexpr size_t kMaxPacket = 512 * 1024; // Steam's maximum individual message size.
enum class Role { capture, preview };
enum class LinkState { waiting, active, paused, incompatible };
struct Packet {
    std::string kind, session, manifest;
    uint64_t sequence{}, frame{};
    Json body;
    uint32_t player{};
};
std::vector<uint8_t> encode(const Packet& packet);
Packet decode(const void* data, size_t size);
void validate_world(const Json& body);
void validate_draws(const Json& body);
class EntityIds {
    uint64_t next_{1};
    std::unordered_map<uint64_t, uint64_t> live_;
public:
    uint64_t acquire(uint64_t local_identity);
    std::vector<uint64_t> finish_frame(const std::vector<uint64_t>& observed);
};
class Session {
    Role role_;
    std::string id_, manifest_;
    uint64_t last_sequence_{}, last_world_frame_{}, last_seen_ms_{};
    bool handshake_{};
    std::unordered_set<std::string> progress_events_;
public:
    LinkState state{LinkState::waiting};
    Json world, draws, input;
    std::vector<Json> pending_progress;
    explicit Session(Role role, std::string id, std::string manifest);
    bool receive(const Packet& packet, uint64_t now_ms);
    void tick(uint64_t now_ms);
    bool gameplay_allowed() const { return role_ == Role::capture && state == LinkState::active; }
    // A research gate, intentionally distinct from simulated journal deduplication.
    bool native_progress_commit_available() const { return false; }
};
struct Coverage {
    bool lua_observer{}, world_capture{}, draw_capture{}, steam_interface{};
    bool client_simulation_isolated{}, native_world_apply{}, per_peer_ui_isolated{}, native_progress_commit{};
    bool playable() const;
    Json report() const;
};
}
