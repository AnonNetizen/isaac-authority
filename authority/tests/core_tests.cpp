#include "core.hpp"
#include <iostream>
#include <stdexcept>
namespace {
using namespace ia;
unsigned passed{};
void test(bool ok, const char* name) { if (!ok) throw std::runtime_error(name); ++passed; }
template<class F> void rejects(F fn, const char* name) { bool threw = false; try { fn(); } catch (...) { threw = true; } test(threw, name); }
Packet packet(std::string kind, uint64_t sequence, Json body, uint64_t frame = 10) {
    const bool from_preview = kind == "input" || body.value("role", "") == "preview";
    return {std::move(kind), "test-session", std::string(64, 'a'), sequence, frame, std::move(body), from_preview ? 1U : 0U};
}
Json world() {
    return {{"entities", Json::array({{{"id", uint64_t(1)}, {"type", 1}, {"x", 10.5}, {"y", 20}, {"vx", 0}, {"vy", 0}},
                                      {{"id", uint64_t(2)}, {"type", 2}, {"x", 11}, {"y", 20}, {"vx", 1}, {"vy", 0}, {"parent", uint64_t(1)}}})}};
}
}
int main() {
    try {
        EntityIds ids;
        auto first = ids.acquire(100), second = ids.acquire(200);
        test(first != second && ids.acquire(100) == first, "stable ids");
        test(ids.finish_frame({200}) == std::vector<uint64_t>{first}, "entity deletion");
        test(ids.acquire(100) > second, "reused local address gets new network identity after deletion");
        auto w = world(); validate_world(w); ++passed;
        auto bytes = encode(packet("world", 2, w)); auto decoded = decode(bytes.data(), bytes.size());
        test(decoded.body == w && decoded.frame == 10, "CBOR roundtrip");
        rejects([&] { decode(bytes.data(), bytes.size() - 1); }, "truncated CBOR");
        rejects([&] { decode(nullptr, 0); }, "zero packet");
        rejects([&] { decode(bytes.data(), kMaxPacket + 1); }, "packet size limit");
        auto bad = w; bad["entities"][1]["id"] = uint64_t(1);
        rejects([&] { validate_world(bad); }, "duplicate entity ids");
        bad = w; bad["entities"][1]["parent"] = uint64_t(999);
        rejects([&] { validate_world(bad); }, "dangling entity relations");
        bad = w; bad["entities"][0]["x"] = std::numeric_limits<double>::infinity();
        rejects([&] { validate_world(bad); }, "nonfinite coordinates");
        rejects([&] { encode(packet("world", 2, {{"huge", std::string(65537, 'a')}})); }, "oversized field");
        const auto text_command = Json{{"op", "text"}, {"text_hex", "70726976617465203437"}, {"x", 12}, {"y", 13},
            {"color", {{"r", 1}, {"g", 1}, {"b", 1}, {"a", 1}}}};
        auto draws = Json{{"commands", Json::array({text_command})}};
        validate_draws(draws); ++passed;
        auto font_command = text_command; font_command["op"] = "font"; font_command["asset"] = "font/test.fnt";
        font_command["method"] = "DrawString"; font_command["sx"] = 1; font_command["sy"] = 1;
        rejects([&] { auto c = font_command; c["asset"] = "../secret"; validate_draws({{"commands", Json::array({c})}}); }, "path traversal");
        rejects([&] { auto c = font_command; c["asset"] = "C:/secret"; validate_draws({{"commands", Json::array({c})}}); }, "absolute asset path");
        rejects([&] { auto c = text_command; c["color"].erase("r"); validate_draws({{"commands", Json::array({c})}}); }, "missing render color refused before native replay");
        rejects([&] { auto c = text_command; c["text_hex"] = "fg"; validate_draws({{"commands", Json::array({c})}}); }, "invalid text bytes");
        rejects([&] { auto c = font_command; c["method"] = "Load"; validate_draws({{"commands", Json::array({c})}}); }, "unexpected replay method");
        Session guest(Role::preview, "test-session", std::string(64, 'a'));
        test(!guest.receive(packet("world", 2, w), 0), "world before handshake refused");
        test(guest.receive(packet("hello", 1, {{"role", "capture"}, {"research_only", true}}), 0), "role handshake");
        test(guest.receive(decoded, 100) && guest.world == w, "authority full state accepted");
        test(!guest.receive(decoded, 101), "duplicate sequence ignored");
        test(guest.receive(packet("draw", 3, draws), 102) && guest.draws == draws, "draw/world alignment");
        test(guest.receive(packet("draw", 4, draws, 9), 103) && guest.draws == draws, "old draw not applied");
        test(!guest.gameplay_allowed(), "guest never owns gameplay");
        guest.tick(4000); test(guest.state == LinkState::paused, "deadline pauses logical link");
        auto restored = w; restored["entities"][0]["x"] = 99.0;
        test(guest.receive(packet("world", 5, restored, 11), 4001) && guest.world == restored && guest.draws.is_null(), "full state resumes without room rollback");
        auto progress = Json{{"event_id", "run-1:unlock-47"}, {"unlock", 47}};
        guest.receive(packet("progress", 6, progress), 4002); guest.receive(packet("progress", 7, progress), 4003);
        test(guest.pending_progress.size() == 1, "progress event journal idempotent");
        test(!guest.native_progress_commit_available(), "unmapped native progression is never committed");
        Session host(Role::capture, "test-session", std::string(64, 'a'));
        host.receive(packet("hello", 1, {{"role", "preview"}, {"research_only", true}}), 0);
        rejects([&] { auto forged = packet("world", 2, w); forged.player = 1; host.receive(forged, 1); }, "guest cannot write host world");
        test(host.receive(packet("input", 2, {{"left", true}}), 1), "guest input accepted as input only");
        auto mismatch = packet("hello", 1, {{"role", "capture"}, {"research_only", true}}); mismatch.manifest[0] = 'b';
        Session incompatible(Role::preview, "test-session", std::string(64, 'a'));
        test(!incompatible.receive(mismatch, 0) && incompatible.state == LinkState::incompatible, "incompatible build locked out");
        test(!incompatible.receive(packet("hello", 2, {{"role", "capture"}, {"research_only", true}}), 1), "mismatch cannot be silently cleared");
        Session other(Role::preview, "test-session", std::string(64, 'a'));
        auto foreign = packet("hello", 1, {{"role", "capture"}, {"research_only", true}}); foreign.session = "wrong-session";
        test(!other.receive(foreign, 0), "foreign session refused");
        auto wrong_player = packet("hello", 1, {{"role", "capture"}, {"research_only", true}}); wrong_player.player = 1;
        test(!other.receive(wrong_player, 0), "foreign player slot refused");
        rejects([&] { other.receive(packet("hello", 1, {{"role", "capture"}, {"research_only", false}}), 0); }, "false playable advertisement refused");
        Coverage coverage; coverage.lua_observer = coverage.world_capture = coverage.draw_capture = coverage.steam_interface = true;
        test(!coverage.playable() && !coverage.report().at("playable").get<bool>(), "observation coverage is not playable coverage");
        // Accelerated transport simulation, explicitly not a real 30-minute game test.
        Session sim(Role::preview, "test-session", std::string(64, 'a'));
        sim.receive(packet("hello", 1, {{"role", "capture"}, {"research_only", true}}), 0);
        uint64_t seq = 2;
        for (uint64_t frame = 1; frame <= 54000; ++frame) {
            if (frame % 33 == 0) continue; // ~3% deliberately dropped observations.
            auto full = w; full["entities"][0]["x"] = double(frame);
            auto p = packet("world", seq++, full, frame);
            sim.receive(p, frame * 33 + 100);
            if (frame % 97 == 0) sim.receive(p, frame * 33 + 120); // duplicate arrival
        }
        test(sim.world.at("entities")[0].at("x").get<double>() == 54000, "accelerated drop/duplicate simulation converges to full frame");
        std::cout << Json({{"passed", passed}, {"live_game_test", false}, {"two_machine_test", false}}).dump(2) << '\n'; return 0;
    } catch (const std::exception& e) { std::cerr << "FAILED: " << e.what() << '\n'; return 1; }
}
