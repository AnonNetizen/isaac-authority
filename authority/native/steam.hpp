#pragma once
#include "platform.hpp"
#include <steam/steamnetworkingtypes.h>
namespace ia {
class SteamTransport {
    HMODULE module_{};
    void* messages_{};
    uint64_t self_{}, peer_{};
    bool owns_context_{};
    EResult (__cdecl* send_)(void*, const SteamNetworkingIdentity*, const void*, uint32, int, int){};
    int (__cdecl* receive_)(void*, int, SteamNetworkingMessage_t**, int){};
    bool (__cdecl* close_)(void*, const SteamNetworkingIdentity*, int){};
    void (__cdecl* shutdown_)(){};
public:
    bool initialize(HMODULE module, bool initialize_context);
    void set_peer(uint64_t id) { peer_ = id; }
    uint64_t self() const { return self_; }
    bool available() const { return messages_ && self_ != 0 && send_ && receive_ && close_; }
    EResult send(const Packet& packet);
    void poll(const std::function<void(const Packet&)>& callback, Log& log);
    void stop();
    ~SteamTransport() { stop(); }
};
}
