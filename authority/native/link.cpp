#include "link.hpp"
#include <cmath>
#include <utility>

namespace ia {
namespace {
bool session_length_ok(const std::string& session) { return session.size() >= 8 && session.size() <= 128; }

Encoded finish_checked(std::vector<uint8_t> bytes) {
    Encoded encoded;
    if (bytes.size() + 4 > 512) { encoded.error = ModelError::bad_count; return encoded; }
    const uint32_t sum = crc32_ieee(bytes.data(), bytes.size());
    put_u32(bytes, sum);
    encoded.bytes = std::move(bytes);
    return encoded;
}

bool prefix_checksum_ok(const uint8_t* data, size_t size) {
    if (data == nullptr || size < 4) return false;
    const uint32_t expect = read_u32(data + size - 4);
    return crc32_ieee(data, size - 4) == expect;
}
}

Encoded encode_hello(const HelloMessage& hello) {
    Encoded encoded;
    if (!session_length_ok(hello.session) || hello.session.size() > 255) { encoded.error = ModelError::bad_count; return encoded; }
    if (hello.research_only > 1 || (hello.flags & ~kHelloReconnect) != 0) { encoded.error = ModelError::bad_flags; return encoded; }
    std::vector<uint8_t> bytes;
    put_u32(bytes, kControlMagic);
    put_u16(bytes, kLinkVersion);
    put_u16(bytes, hello.type);
    bytes.push_back(hello.role == LinkRole::capture ? 1 : 2);
    bytes.push_back(hello.research_only);
    bytes.push_back(hello.flags);
    bytes.push_back(0);
    put_u32(bytes, hello.resume_frame);
    bytes.push_back(static_cast<uint8_t>(hello.session.size()));
    bytes.insert(bytes.end(), hello.session.begin(), hello.session.end());
    bytes.insert(bytes.end(), hello.manifest.begin(), hello.manifest.end());
    return finish_checked(std::move(bytes));
}

DecodedHello decode_hello(const uint8_t* data, size_t size) {
    DecodedHello decoded;
    if (data == nullptr || size < 20) { decoded.error = ModelError::truncated; return decoded; }
    if (read_u32(data) != kControlMagic) { decoded.error = ModelError::bad_magic; return decoded; }
    if (data[4] != static_cast<uint8_t>(kLinkVersion) || data[5] != 0) { decoded.error = ModelError::bad_version; return decoded; }
    if (!prefix_checksum_ok(data, size)) { decoded.error = ModelError::bad_checksum; return decoded; }
    ByteReader in(data + 6, size - 6 - 4);
    HelloMessage hello;
    hello.type = in.u16();
    const uint8_t role = in.u8();
    hello.research_only = in.u8();
    hello.flags = in.u8();
    const uint8_t reserved = in.u8();
    hello.resume_frame = in.u32();
    const uint8_t session_len = in.u8();
    if (!in.ok()) { decoded.error = ModelError::truncated; return decoded; }
    if (reserved != 0 || (hello.flags & ~kHelloReconnect) != 0 || (role != 1 && role != 2)) {
        decoded.error = ModelError::bad_flags;
        return decoded;
    }
    if (session_len < 8 || in.remaining() < static_cast<size_t>(session_len) + 32) {
        decoded.error = ModelError::truncated;
        return decoded;
    }
    hello.role = role == 1 ? LinkRole::capture : LinkRole::preview;
    hello.session.resize(session_len);
    for (uint8_t i = 0; i < session_len; ++i) hello.session[i] = static_cast<char>(in.u8());
    for (size_t i = 0; i < 32; ++i) hello.manifest[i] = in.u8();
    if (!in.ok() || !in.finish()) { decoded.error = ModelError::trailing; return decoded; }
    decoded.hello = std::move(hello);
    return decoded;
}

Encoded encode_input(const InputFrame& frame) {
    Encoded encoded;
    if (!std::isfinite(frame.aim_x) || !std::isfinite(frame.aim_y)) { encoded.error = ModelError::nonfinite; return encoded; }
    std::vector<uint8_t> bytes;
    put_u32(bytes, kInputMagic);
    put_u16(bytes, kLinkVersion);
    put_u16(bytes, frame.buttons);
    put_u32(bytes, frame.frame);
    put_u32(bytes, frame.player_slot);
    put_f32(bytes, frame.aim_x);
    put_f32(bytes, frame.aim_y);
    return finish_checked(std::move(bytes));
}

DecodedInput decode_input(const uint8_t* data, size_t size) {
    DecodedInput decoded;
    if (data == nullptr || size != 28) { decoded.error = ModelError::truncated; return decoded; }
    if (read_u32(data) != kInputMagic) { decoded.error = ModelError::bad_magic; return decoded; }
    if (data[4] != static_cast<uint8_t>(kLinkVersion) || data[5] != 0) { decoded.error = ModelError::bad_version; return decoded; }
    if (!prefix_checksum_ok(data, size)) { decoded.error = ModelError::bad_checksum; return decoded; }
    ByteReader in(data + 6, 18);
    InputFrame frame;
    frame.buttons = in.u16();
    frame.frame = in.u32();
    frame.player_slot = in.u32();
    frame.aim_x = in.f32();
    frame.aim_y = in.f32();
    if (!in.ok() || !in.finish()) { decoded.error = ModelError::truncated; return decoded; }
    if (!std::isfinite(frame.aim_x) || !std::isfinite(frame.aim_y)) { decoded.error = ModelError::nonfinite; return decoded; }
    decoded.frame = frame;
    return decoded;
}

LoopbackHub::LoopbackHub() {
    ends_[0].hub = this; ends_[0].id = 0;
    ends_[1].hub = this; ends_[1].id = 1;
}
bool LoopbackHub::enqueue(int dest, uint8_t channel, const uint8_t* data, size_t size) {
    if (dest != 0 && dest != 1) return false;
    if (data == nullptr || size == 0 || size > kMaxSnapshotBytes) return false;
    Datagram datagram{channel, std::vector<uint8_t>(data, data + size)};
    if (drop_[dest] > 0) { --drop_[dest]; return true; }
    if (reorder_[dest]) {
        held_[dest].push_back(std::move(datagram));
        if (held_[dest].size() < 2) return true;
        queues_[dest].push_back(std::move(held_[dest][1]));
        queues_[dest].push_back(std::move(held_[dest][0]));
        held_[dest].clear();
        reorder_[dest] = false;
        return true;
    }
    queues_[dest].push_back(datagram);
    if (duplicate_[dest]) { queues_[dest].push_back(queues_[dest].back()); duplicate_[dest] = false; }
    return true;
}
bool LoopbackHub::Endpoint::send(uint8_t channel, const uint8_t* data, size_t size) {
    return hub->enqueue(1 - id, channel, data, size);
}
void LoopbackHub::Endpoint::poll(const std::function<void(uint8_t, const uint8_t*, size_t)>& callback) {
    std::vector<Datagram> local;
    local.swap(hub->queues_[id]);
    for (const auto& datagram : local) callback(datagram.channel, datagram.bytes.data(), datagram.bytes.size());
}
void LoopbackHub::drop_next(int dest, int count) { if (dest == 0 || dest == 1) drop_[dest] += count; }
void LoopbackHub::duplicate_next(int dest) { if (dest == 0 || dest == 1) duplicate_[dest] = true; }
void LoopbackHub::reorder_next_pair(int dest) { if (dest == 0 || dest == 1) reorder_[dest] = true; }
void LoopbackHub::inject(int dest, uint8_t channel, std::vector<uint8_t> bytes) {
    if ((dest != 0 && dest != 1) || bytes.empty() || bytes.size() > kMaxSnapshotBytes) return;
    queues_[dest].push_back(Datagram{channel, std::move(bytes)});
}

AuthorityLink::AuthorityLink(LinkConfig config, Transport& transport)
    : config_(std::move(config)), transport_(transport), publisher_(config_.keyframe_interval) {
    session_ok_ = session_length_ok(config_.session);
}
bool AuthorityLink::send_hello(uint8_t flags, uint32_t resume_frame) {
    if (!session_ok_ || phase_ == LinkPhase::incompatible) return false;
    HelloMessage hello;
    hello.type = 1;
    hello.role = config_.role;
    hello.research_only = 1;
    hello.flags = flags;
    hello.resume_frame = resume_frame;
    hello.session = config_.session;
    hello.manifest = config_.manifest;
    const auto encoded = encode_hello(hello);
    if (encoded.error != ModelError::ok) return false;
    return transport_.send(kChannelControl, encoded.bytes.data(), encoded.bytes.size());
}
bool AuthorityLink::start(uint64_t now_ms) {
    const uint32_t resume = snapshot() ? snapshot()->frame : 0;
    if (!send_hello(0, resume)) return false;
    (void)now_ms;
    return true;
}
bool AuthorityLink::reconnect(uint64_t now_ms) {
    const uint32_t resume = snapshot() ? snapshot()->frame : 0;
    if (!send_hello(kHelloReconnect, resume)) return false;
    if (config_.role == LinkRole::capture) publisher_.force_keyframe();
    else guest_.resync();
    (void)now_ms;
    return true;
}
void AuthorityLink::lock() {
    if (phase_ == LinkPhase::incompatible) return;
    phase_ = LinkPhase::incompatible;
    if (sent_lock_) return;
    sent_lock_ = true;
    HelloMessage hello;
    hello.type = 2;
    hello.role = config_.role;
    hello.research_only = 1;
    hello.session = config_.session;
    hello.manifest = config_.manifest;
    const auto encoded = encode_hello(hello);
    if (encoded.error == ModelError::ok) transport_.send(kChannelControl, encoded.bytes.data(), encoded.bytes.size());
}
void AuthorityLink::poll(uint64_t now_ms) {
    if (phase_ == LinkPhase::incompatible) return;
    transport_.poll([&](uint8_t channel, const uint8_t* data, size_t size) { handle(channel, data, size, now_ms); });
}
void AuthorityLink::tick(uint64_t now_ms) {
    if (phase_ == LinkPhase::active && now_ms >= last_rx_ && now_ms - last_rx_ > kLinkTimeoutMs) phase_ = LinkPhase::paused;
}
void AuthorityLink::handle(uint8_t channel, const uint8_t* data, size_t size, uint64_t now) {
    if (phase_ == LinkPhase::incompatible) return;
    if (channel == kChannelControl) handle_control(data, size, now);
    else if (channel == kChannelState) handle_state(data, size, now);
    else if (channel == kChannelInput) handle_input(data, size, now);
}
void AuthorityLink::handle_control(const uint8_t* data, size_t size, uint64_t now) {
    const auto decoded = decode_hello(data, size);
    if (decoded.error == ModelError::bad_version) { lock(); return; }
    if (decoded.error != ModelError::ok) return;
    if (decoded.hello.session != config_.session) return;
    if (decoded.hello.type == 2) { lock(); return; }
    if (decoded.hello.type != 1) return;
    if (decoded.hello.research_only != 1) { lock(); return; }
    if (decoded.hello.manifest != config_.manifest) { lock(); return; }
    const LinkRole expect = config_.role == LinkRole::capture ? LinkRole::preview : LinkRole::capture;
    if (decoded.hello.role != expect) return;
    const bool resync = (decoded.hello.flags & kHelloReconnect) != 0 || phase_ == LinkPhase::paused || phase_ == LinkPhase::waiting;
    phase_ = LinkPhase::active;
    last_rx_ = now;
    if (!resync) return;
    if (config_.role == LinkRole::capture) publisher_.force_keyframe();
    else guest_.resync();
}
void AuthorityLink::handle_state(const uint8_t* data, size_t size, uint64_t now) {
    if (config_.role != LinkRole::preview || phase_ != LinkPhase::active) return;
    const auto result = guest_.accept(data, size);
    if (result == ModelError::bad_version || guest_.incompatible()) { lock(); return; }
    if (result == ModelError::ok || result == ModelError::duplicate || result == ModelError::stale ||
        result == ModelError::buffered || result == ModelError::needs_keyframe) last_rx_ = now;
}
void AuthorityLink::handle_input(const uint8_t* data, size_t size, uint64_t now) {
    if (config_.role != LinkRole::capture || phase_ != LinkPhase::active) return;
    const auto decoded = decode_input(data, size);
    if (decoded.error == ModelError::bad_version) { lock(); return; }
    if (decoded.error != ModelError::ok) return;
    last_rx_ = now;
    if (decoded.frame.player_slot != 1) return;
    if (have_input_ && decoded.frame.frame <= latest_.frame) return;
    latest_ = decoded.frame;
    have_input_ = true;
}
SendResult AuthorityLink::publish_capture(const NativeCapture& capture, uint64_t now_ms) {
    SendResult result;
    if (config_.role != LinkRole::capture) { result.error = LinkError::wrong_role; return result; }
    if (phase_ == LinkPhase::incompatible) { result.error = LinkError::incompatible; return result; }
    if (phase_ != LinkPhase::active) { result.error = LinkError::not_active; return result; }
    auto published = publisher_.publish(capture);
    if (published.error == ModelError::stale) { result.error = LinkError::stale; return result; }
    if (published.error != ModelError::ok) { result.error = LinkError::bad_packet; return result; }
    if (!transport_.send(kChannelState, published.bytes.data(), published.bytes.size())) {
        publisher_.force_keyframe();
        result.error = LinkError::send_failed;
        return result;
    }
    result.keyframe = published.sent_keyframe;
    result.sequence = published.sequence;
    result.frame = published.snapshot.frame;
    result.bytes = std::move(published.bytes);
    (void)now_ms;
    return result;
}
LinkError AuthorityLink::publish_input(const InputFrame& frame, uint64_t now_ms) {
    if (config_.role != LinkRole::preview) return LinkError::wrong_role;
    if (phase_ == LinkPhase::incompatible) return LinkError::incompatible;
    if (phase_ != LinkPhase::active) return LinkError::not_active;
    if (frame.player_slot != 1) return LinkError::rejected;
    if (have_sent_input_ && frame.frame <= last_sent_frame_) return LinkError::stale;
    const auto encoded = encode_input(frame);
    if (encoded.error != ModelError::ok) return LinkError::bad_packet;
    if (!transport_.send(kChannelInput, encoded.bytes.data(), encoded.bytes.size())) return LinkError::send_failed;
    have_sent_input_ = true;
    last_sent_frame_ = frame.frame;
    (void)now_ms;
    return LinkError::ok;
}
bool AuthorityLink::bind_entity(uint64_t network_id, uint32_t local_token) {
    if (config_.role != LinkRole::preview) return false;
    return guest_.bind(network_id, local_token);
}
}
