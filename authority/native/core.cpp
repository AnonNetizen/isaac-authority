#include "core.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace ia {
namespace {
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
uint64_t integer(const Json& j, const char* field) {
    require(j.contains(field) && j.at(field).is_number_unsigned(), "Missing unsigned integer");
    return j.at(field).get<uint64_t>();
}
void finite_tree(const Json& j, int depth = 0) {
    require(depth <= 24, "State exceeds nesting limit");
    if (j.is_number_float()) require(std::isfinite(j.get<double>()), "Nonfinite state value");
    if (j.is_string()) require(j.get_ref<const std::string&>().size() <= 65536, "Oversized state string");
    if (j.is_structured()) for (const auto& item : j) finite_tree(item, depth + 1);
}
void safe_asset(const Json& value) {
    require(value.is_string(), "Non-string asset reference");
    const auto& asset = value.get_ref<const std::string&>();
    require(asset.find("..") == std::string::npos && asset.find(':') == std::string::npos &&
            (asset.empty() || (asset[0] != '/' && asset[0] != '\\')), "Unsafe asset reference");
}
void number_fields(const Json& object, std::initializer_list<const char*> names) {
    require(object.is_object(), "Invalid numeric object");
    for (auto* name : names) require(object.contains(name) && object.at(name).is_number() &&
        std::isfinite(object.at(name).get<double>()), "Missing/nonfinite numeric field");
}
}
std::vector<uint8_t> encode(const Packet& p) {
    Json j = {{"protocol", kProtocol}, {"kind", p.kind}, {"session", p.session},
              {"manifest", p.manifest}, {"sequence", p.sequence}, {"frame", p.frame}, {"body", p.body}, {"player", p.player}};
    finite_tree(j);
    auto bytes = Json::to_cbor(j);
    require(bytes.size() <= kMaxPacket, "Packet exceeds limit");
    return bytes;
}
Packet decode(const void* data, size_t size) {
    require(size > 0 && size <= kMaxPacket && data != nullptr, "Invalid packet size");
    const auto* bytes = static_cast<const uint8_t*>(data);
    const auto j = Json::from_cbor(bytes, bytes + size, true, true);
    require(j.is_object() && j.value("protocol", 0) == kProtocol, "Incompatible protocol");
    Packet p{j.at("kind").get<std::string>(), j.at("session").get<std::string>(),
             j.at("manifest").get<std::string>(), integer(j, "sequence"), integer(j, "frame"), j.at("body")};
    const auto player = integer(j, "player"); require(player <= 1, "Invalid player slot"); p.player = static_cast<uint32_t>(player);
    require(p.session.size() >= 8 && p.session.size() <= 128 && p.manifest.size() == 64, "Invalid session/manifest");
    require(p.kind == "hello" || p.kind == "world" || p.kind == "draw" || p.kind == "input" || p.kind == "progress", "Unknown packet kind");
    finite_tree(p.body);
    return p;
}
void validate_world(const Json& body) {
    require(body.is_object() && body.contains("entities") && body.at("entities").is_array(), "Invalid world");
    require(body.at("entities").size() <= 16384, "Too many entities");
    std::unordered_set<uint64_t> ids;
    for (const auto& e : body.at("entities")) {
        const auto id = integer(e, "id");
        require(id != 0 && ids.insert(id).second, "Duplicate/zero entity id");
        require(e.contains("type") && e.at("type").is_number_integer(), "Missing entity type");
        for (const char* coordinate : {"x", "y", "vx", "vy"})
            require(e.contains(coordinate) && e.at(coordinate).is_number() && std::isfinite(e.at(coordinate).get<double>()), "Invalid entity vector");
    }
    for (const auto& e : body.at("entities")) for (const char* relation : {"parent", "spawner"})
        if (e.contains(relation) && !e.at(relation).is_null()) {
            auto id = integer(e, relation);
            require(id == 0 || ids.contains(id), "Dangling entity relation");
        }
    finite_tree(body);
}
void validate_draws(const Json& body) {
    require(body.is_object() && body.contains("commands") && body.at("commands").is_array(), "Invalid draw frame");
    require(body.at("commands").size() <= 8192, "Too many draw commands");
    for (const auto& command : body.at("commands")) {
        require(command.is_object() && command.contains("op") && command.at("op").is_string(), "Invalid draw command");
        auto op = command.at("op").get<std::string>();
        require(op == "text" || op == "font" || op == "sprite", "Unknown draw command");
        number_fields(command.at("color"), {"r", "g", "b", "a"});
        if (op == "text" || op == "font") {
            number_fields(command, {"x", "y"});
            require(command.contains("text_hex") && command.at("text_hex").is_string(), "Missing raw text bytes");
            auto hex = command.at("text_hex").get<std::string>();
            require(hex.size() % 2 == 0 && hex.find_first_not_of("0123456789abcdef") == std::string::npos, "Invalid text byte encoding");
        }
        if (op == "font" || op == "sprite") safe_asset(command.at("asset"));
        if (op == "font") {
            number_fields(command, {"sx", "sy"});
            const auto method = command.at("method").get<std::string>();
            require(method == "DrawString" || method == "DrawStringUTF8" || method == "DrawStringScaled" || method == "DrawStringScaledUTF8", "Unknown font method");
            if (command.value("native_signature", false)) {
                const auto& settings = command.at("settings");
                number_fields(settings, {"alignment", "line_height", "max_characters", "missing_character"});
                require(settings.at("auto_wrap").is_boolean() && settings.at("truncation").is_boolean(), "Invalid font settings flags");
            }
        }
        if (op == "sprite") {
            number_fields(command.at("position"), {"x", "y"});
            number_fields(command.at("scale"), {"x", "y"}); number_fields(command.at("offset"), {"x", "y"});
            number_fields(command, {"rotation", "sprite_frame"});
            require(command.at("animation").is_string() && command.at("flip_x").is_boolean() && command.at("flip_y").is_boolean(), "Invalid sprite properties");
            const auto& sheets = command.at("sheets");
            require(sheets.is_object() || (sheets.is_array() && sheets.empty()), "Invalid sheet mapping");
            for (const auto& value : sheets) safe_asset(value);
            for (auto name : {"clamp1", "clamp2"}) if (command.contains(name)) number_fields(command.at(name), {"x", "y"});
        }
    }
    finite_tree(body);
}
uint64_t EntityIds::acquire(uint64_t key) {
    auto [it, inserted] = live_.try_emplace(key, next_);
    if (inserted) ++next_;
    return it->second;
}
std::vector<uint64_t> EntityIds::finish_frame(const std::vector<uint64_t>& keys) {
    const std::unordered_set<uint64_t> observed(keys.begin(), keys.end());
    std::vector<uint64_t> removed;
    for (auto it = live_.begin(); it != live_.end();) {
        if (!observed.contains(it->first)) { removed.push_back(it->second); it = live_.erase(it); }
        else ++it;
    }
    std::sort(removed.begin(), removed.end()); return removed;
}
Session::Session(Role role, std::string id, std::string manifest)
    : role_(role), id_(std::move(id)), manifest_(std::move(manifest)) {}
bool Session::receive(const Packet& p, uint64_t now) {
    if (p.session != id_) return false;
    if (p.manifest != manifest_) { state = LinkState::incompatible; handshake_ = false; return false; }
    if (p.player != (role_ == Role::preview ? 0U : 1U)) return false;
    if (state == LinkState::incompatible || p.sequence <= last_sequence_) return false;
    if (p.kind == "hello") {
        require(p.body.value("role", "") == (role_ == Role::capture ? "preview" : "capture"), "Peer role mismatch");
        require(p.body.value("research_only", false), "Peer incorrectly advertises playable mode");
        handshake_ = true;
    } else {
        if (!handshake_) return false;
        if (p.kind == "world") {
            require(role_ == Role::preview, "Client cannot write authority world");
            validate_world(p.body); world = p.body; last_world_frame_ = p.frame;
            draws = Json(); // Never combine an old HUD with a new world.
        } else if (p.kind == "draw") {
            require(role_ == Role::preview, "Client cannot send authoritative draws");
            validate_draws(p.body); if (p.frame == last_world_frame_) draws = p.body;
        } else if (p.kind == "input") {
            require(role_ == Role::capture && p.body.is_object(), "Invalid client input"); input = p.body;
        } else if (p.kind == "progress") {
            require(role_ == Role::preview && p.body.is_object(), "Invalid progress event");
            auto event = p.body.at("event_id").get<std::string>();
            require(!event.empty() && event.size() <= 128, "Invalid progress id");
            require(progress_events_.size() < 65536, "Progress journal limit");
            if (progress_events_.insert(event).second) pending_progress.push_back(p.body);
        }
    }
    last_sequence_ = p.sequence; last_seen_ms_ = now; state = LinkState::active; return true;
}
void Session::tick(uint64_t now) {
    if (state == LinkState::active && now >= last_seen_ms_ && now - last_seen_ms_ > 3000) state = LinkState::paused;
}
bool Coverage::playable() const {
    return steam_interface && client_simulation_isolated && native_world_apply && per_peer_ui_isolated && native_progress_commit;
}
Json Coverage::report() const {
    return {{"research_only", true}, {"playable", playable()}, {"lua_observer", lua_observer},
            {"world_capture", world_capture}, {"draw_capture", draw_capture}, {"steam_interface", steam_interface},
            {"client_simulation_isolated", client_simulation_isolated}, {"native_world_apply", native_world_apply},
            {"per_peer_ui_isolated", per_peer_ui_isolated}, {"native_progress_commit", native_progress_commit}};
}
}
