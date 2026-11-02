#include "steam.hpp"
#include <stdexcept>
namespace ia {
static_assert(sizeof(ValvePackingSentinel_t) == 32, "Steam Windows ABI requires Valve's large callback packing");
bool SteamTransport::initialize(HMODULE module, bool initialize_context) {
    if (available()) return true;
    if (!module) return false;
    module_ = module;
    // Flat interface getters may cache an invalid context if called before the game's Steam init.
    // Inspect the public handles first; the injected DLL never owns or initializes the game's SDK.
    if (!initialize_context) {
        const auto get_user = reinterpret_cast<int (__cdecl*)()>(GetProcAddress(module_, "SteamAPI_GetHSteamUser"));
        const auto get_pipe = reinterpret_cast<int (__cdecl*)()>(GetProcAddress(module_, "SteamAPI_GetHSteamPipe"));
        if (!get_user || !get_pipe || !get_user() || !get_pipe()) return false;
    }
    auto init = reinterpret_cast<bool (__cdecl*)()>(GetProcAddress(module_, "SteamAPI_InitSafe"));
    shutdown_ = reinterpret_cast<void (__cdecl*)()>(GetProcAddress(module_, "SteamAPI_Shutdown"));
    if (initialize_context) { if (!init || !init()) return false; owns_context_ = true; }
    auto messages = reinterpret_cast<void* (__cdecl*)()>(GetProcAddress(module_, "SteamAPI_SteamNetworkingMessages_SteamAPI_v002"));
    auto user = reinterpret_cast<void* (__cdecl*)()>(GetProcAddress(module_, "SteamAPI_SteamUser_v023"));
    auto id = reinterpret_cast<uint64_t (__cdecl*)(void*)>(GetProcAddress(module_, "SteamAPI_ISteamUser_GetSteamID"));
    send_ = reinterpret_cast<decltype(send_)>(GetProcAddress(module_, "SteamAPI_ISteamNetworkingMessages_SendMessageToUser"));
    receive_ = reinterpret_cast<decltype(receive_)>(GetProcAddress(module_, "SteamAPI_ISteamNetworkingMessages_ReceiveMessagesOnChannel"));
    close_ = reinterpret_cast<decltype(close_)>(GetProcAddress(module_, "SteamAPI_ISteamNetworkingMessages_CloseChannelWithUser"));
    if (messages) messages_ = messages();
    if (user && id) { if (auto* ptr = user()) self_ = id(ptr); }
    return available() && self_ != 0;
}
EResult SteamTransport::send(const Packet& p) {
    if (!available() || !peer_ || peer_ == self_) return k_EResultInvalidParam;
    SteamNetworkingIdentity identity{}; identity.SetSteamID64(peer_);
    const auto bytes = encode(p);
    // A single reliable research channel gives cross-kind ordering. High-volume optimization is not claimed.
    return send_(messages_, &identity, bytes.data(), static_cast<uint32>(bytes.size()), k_nSteamNetworkingSend_Reliable, kChannel);
}
void SteamTransport::poll(const std::function<void(const Packet&)>& callback, Log& log) {
    if (!available() || !peer_) return;
    SteamNetworkingMessage_t* messages[16]{};
    int count = receive_(messages_, kChannel, messages, 16);
    for (int i = 0; i < count; ++i) {
        auto* message = messages[i];
        try {
            if (message->m_identityPeer.GetSteamID64() == peer_) {
                auto packet = decode(message->m_pData, static_cast<size_t>(message->m_cbSize)); callback(packet);
            } else log.write("rejected_unexpected_peer");
        } catch (const std::exception& e) { log.write("rejected_packet", {{"error", e.what()}}); }
        message->Release();
    }
}
void SteamTransport::stop() {
    if (available() && peer_) { SteamNetworkingIdentity identity{}; identity.SetSteamID64(peer_); close_(messages_, &identity, kChannel); }
    messages_ = nullptr;
    if (owns_context_ && shutdown_) shutdown_();
    owns_context_ = false;
}
}
