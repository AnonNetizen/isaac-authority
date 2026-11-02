#include "state_model.hpp"
#include "link.hpp"
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <string>
namespace {
using namespace ia;
unsigned passed = 0;
void expect(bool ok, const char* name) {
    if (!ok) throw std::runtime_error(name);
    ++passed;
}
void expect_model(ModelError got, ModelError want, const char* name) {
    if (got != want) throw std::runtime_error(std::string(name) + " got " + model_error_name(got));
    ++passed;
}
bool payload_has_u32(const std::vector<uint8_t>& bytes, uint32_t value) {
    if (bytes.size() < 20) return true;
    uint8_t pattern[4] = {static_cast<uint8_t>(value), static_cast<uint8_t>(value >> 8),
                          static_cast<uint8_t>(value >> 16), static_cast<uint8_t>(value >> 24)};
    for (size_t i = 16; i + 4 <= bytes.size(); ++i)
        if (std::memcmp(bytes.data() + i, pattern, 4) == 0) return true;
    return false;
}
NativeCapture make_capture(uint32_t frame, float x, uint32_t player_ptr = 0x3CE6A014u,
                            uint32_t monster_ptr = 0x3CE6B028u, uint32_t monster_seed = 0x01020304u,
                            bool monster = true, uint32_t room = 71) {
    NativeCapture capture;
    capture.frame = frame;
    capture.room_index = room;
    capture.previous_room = room == 71 ? 84 : 71;
    capture.players.push_back(NativePlayer{player_ptr, x, 380.f, 0.f, 0.f, 10.f});
    capture.entities.push_back(NativeEntity{player_ptr, 1, 0, 0x11111111u, x, 380.f, 0.f, 0.f, 10.f});
    if (monster) capture.entities.push_back(NativeEntity{monster_ptr, 1000, 1, monster_seed, 100.f, 200.f, 1.5f, -0.25f, 8.f});
    return capture;
}
std::vector<uint8_t> read_file(const char* path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error(std::string("missing fixture ") + path);
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}
LinkConfig config_for(LinkRole role, uint8_t mark) {
    LinkConfig config;
    config.role = role;
    config.session = "test-session";
    config.manifest.fill(mark);
    return config;
}
void pump(AuthorityLink& left, AuthorityLink& right, uint64_t now) {
    left.poll(now); right.poll(now); left.poll(now); right.poll(now);
}
}

int main() {
    try {
        const uint8_t digits[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
        expect(crc32_ieee(digits, 9) == 0xCBF43926u, "crc32 ieee");
        expect(GuestWriteOffsets::position == 0x33Cu && GuestWriteOffsets::velocity == 0x360u &&
               GuestWriteOffsets::size == 0x370u, "documented write offsets");

        NativeCaptureBuilder builder;
        builder.set_header(120, 71, 84);
        expect(builder.add_player(0x3CE6A014u, 320.f, 380.f, 0.f, 0.f, 10.f), "fixture player");
        expect(builder.add_entity(0x3CE6A014u, 1, 0, 0x11111111u, 320.f, 380.f, 0.f, 0.f, 10.f), "fixture player entity");
        expect(builder.add_entity(0x3CE6B028u, 1000, 1, 0x01020304u, 100.f, 200.f, 1.5f, -0.25f, 8.f), "fixture monster");
        const auto fixture_built = builder.finish();
        const auto fixture_file = read_file(IA_FIXTURE_PATH);
        expect(fixture_built == fixture_file, "synthetic fixture matches NativeCaptureBuilder");
        NativeCapture parsed;
        expect_model(parse_native_capture(fixture_file.data(), fixture_file.size(), parsed), ModelError::ok, "parse fixture");
        expect(parsed.frame == 120 && parsed.room_index == 71 && parsed.previous_room == 84, "fixture room");
        expect(parsed.players.size() == 1 && parsed.players[0].x == 320.f && parsed.players[0].y == 380.f &&
               parsed.players[0].size == 10.f, "fixture player pose");
        expect(parsed.players[0].pointer == 0x3CE6A014u && parsed.entities.size() == 2, "fixture still has host pointers");

        HostPublisher publisher;
        auto first = publisher.publish(parsed);
        expect_model(first.error, ModelError::ok, "publish fixture");
        expect(first.sent_keyframe && first.sequence == 1, "first snapshot is a keyframe");
        expect(!payload_has_u32(first.bytes, 0x3CE6A014u) && !payload_has_u32(first.bytes, 0x3CE6B028u), "wire has no host pointers");
        GuestView guest;
        expect_model(guest.accept(first.bytes.data(), first.bytes.size()), ModelError::ok, "guest accepts keyframe");
        const auto* world = guest.snapshot();
        expect(world != nullptr && world->players.size() == 1 && world->players[0].slot == 0 &&
               world->players[0].x == 320.f && world->players[0].size == 10.f, "guest player slot pose");
        expect(world->entities.size() == 2 && world->entities[0].player_alias && world->entities[0].player_slot == 0 &&
               !world->entities[1].player_alias, "player entity aliased by slot, not pointer");
        const auto stable_monster = world->entities[1].id;
        auto plan = guest.plan();
        expect(plan.has_snapshot && plan.room_index == 71 && plan.players.size() == 1 && plan.spawns.size() == 2 &&
               plan.bound_entities.empty(), "unbound entities are spawns");
        expect(guest.bind(stable_monster, 0xABCDu), "bind monster");
        expect(!guest.bind(999, 1), "unknown id is not bound");
        plan = guest.plan();
        expect(plan.bound_entities.size() == 1 && plan.bound_entities[0].local_token == 0xABCDu &&
               plan.bound_entities[0].network_id == world->entities[1].id && plan.spawns.size() == 1, "bound write uses token");

        auto moved = publisher.publish(make_capture(121, 330.f));
        expect_model(moved.error, ModelError::ok, "delta publish");
        expect(!moved.sent_keyframe, "motion stays a delta inside the interval");
        expect(moved.bytes.size() < first.bytes.size(), "delta is smaller than the keyframe");
        expect_model(guest.accept(moved.bytes.data(), moved.bytes.size()), ModelError::ok, "guest applies delta");
        expect(guest.snapshot()->players[0].x == 330.f && guest.snapshot()->entities[0].y == 380.f, "delta updates x only");
        expect(guest.snapshot()->entities[1].id == stable_monster, "monster id stable while pointer and seed live");
        plan = guest.plan();
        expect(plan.bound_entities.size() == 1 && plan.bound_entities[0].x == 100.f, "bound monster did not move");

        auto pointer_changed = publisher.publish(make_capture(122, 331.f, 0x89ABCDEFu));
        expect_model(pointer_changed.error, ModelError::ok, "player pointer change");
        expect(!payload_has_u32(pointer_changed.bytes, 0x89ABCDEFu), "new player pointer stripped");
        expect_model(guest.accept(pointer_changed.bytes.data(), pointer_changed.bytes.size()), ModelError::ok, "apply pointer change");
        expect(guest.snapshot()->players.size() == 1 && guest.snapshot()->players[0].slot == 0 &&
               guest.snapshot()->players[0].x == 331.f, "player slot survives pointer change");

        uint64_t monster_before = 0;
        for (const auto& entity : guest.snapshot()->entities) if (!entity.player_alias) monster_before = entity.id;
        expect(monster_before == stable_monster, "monster id survived the player pointer change");
        auto reseeded = publisher.publish(make_capture(123, 331.f, 0x89ABCDEFu, 0x3CE6B028u, 0x22222222u));
        expect(!reseeded.sent_keyframe, "seed change is a delta, not a reused id");
        auto reseed_view = decode_snapshot(reseeded.bytes.data(), reseeded.bytes.size());
        expect(reseed_view.error == ModelError::ok && !reseed_view.packet.keyframe, "decode reseed delta");
        expect(reseed_view.packet.delta.removed.size() == 1 && reseed_view.packet.delta.removed[0] == monster_before &&
               reseed_view.packet.delta.added.size() == 1 && reseed_view.packet.delta.added[0].id != monster_before,
               "same address with a new seed gets a new network id");
        expect_model(guest.accept(reseeded.bytes.data(), reseeded.bytes.size()), ModelError::ok, "apply reseed");
        guest.unbind(monster_before);
        const auto reseeded_monster = reseed_view.packet.delta.added[0].id;
        expect(guest.bind(reseeded_monster, 0xABCDu), "bind the new monster id");

        auto gone = publisher.publish(make_capture(124, 331.f, 0x89ABCDEFu, 0x3CE6B028u, 0x22222222u, false));
        expect_model(guest.accept(gone.bytes.data(), gone.bytes.size()), ModelError::ok, "apply removal");
        plan = guest.plan();
        expect(plan.despawn_ids.size() == 1 && plan.despawn_ids[0] == reseeded_monster &&
               plan.despawn_tokens.size() == 1 && plan.despawn_tokens[0] == 0xABCDu, "despawn keeps id and token paired");
        auto returned = publisher.publish(make_capture(125, 331.f, 0x89ABCDEFu, 0x3CE6B028u, 0x22222222u, true));
        expect_model(guest.accept(returned.bytes.data(), returned.bytes.size()), ModelError::ok, "apply return");
        bool reused = false;
        for (const auto& entity : guest.snapshot()->entities)
            if (!entity.player_alias && entity.id == reseed_view.packet.delta.added[0].id) reused = true;
        expect(!reused, "a pointer that disappeared is not the same network id when it returns");

        auto room = publisher.publish(make_capture(126, 10.f, 0x89ABCDEFu, 0x3CE6B028u, 0x22222222u, true, 72));
        expect(room.sent_keyframe, "room change forces a keyframe");
        expect_model(guest.accept(room.bytes.data(), room.bytes.size()), ModelError::ok, "apply room keyframe");
        expect(guest.snapshot()->room_index == 72 && guest.snapshot()->frame == 126, "guest room follows the keyframe");

        HostPublisher stale_pub;
        expect_model(stale_pub.publish(make_capture(5, 1.f)).error, ModelError::ok, "stale setup");
        expect_model(stale_pub.publish(make_capture(5, 2.f)).error, ModelError::stale, "same frame without force is stale");
        auto rewound = stale_pub.publish(make_capture(4, 2.f));
        expect(rewound.error == ModelError::ok && rewound.sent_keyframe && rewound.snapshot.frame == 4,
               "lower frame in the same room is a new-run keyframe");
        stale_pub.force_keyframe();
        auto refresh = stale_pub.publish(make_capture(5, 2.f));
        expect(refresh.error == ModelError::ok && refresh.sent_keyframe, "forced same-frame keyframe");
        GuestIngress resync_guest;
        expect_model(resync_guest.accept(refresh.bytes.data(), refresh.bytes.size()), ModelError::ok, "resync base");
        resync_guest.resync();
        expect(resync_guest.needs_keyframe() && resync_guest.snapshot() == nullptr, "resync waits for a keyframe");
        expect_model(resync_guest.accept(refresh.bytes.data(), refresh.bytes.size()), ModelError::ok, "resync resets the sequence window and accepts the keyframe again");
        expect(!resync_guest.needs_keyframe() && resync_guest.snapshot()->players[0].x == 2.f, "replayed keyframe restored the world");
        stale_pub.force_keyframe();
        auto refresh_again = stale_pub.publish(make_capture(5, 3.f));
        expect_model(resync_guest.accept(refresh_again.bytes.data(), refresh_again.bytes.size()), ModelError::ok, "same-frame keyframe clears the wait");
        expect(!resync_guest.needs_keyframe() && resync_guest.snapshot()->players[0].x == 3.f, "refresh applied without rollback");

        HostPublisher restart_pub;
        expect_model(restart_pub.publish(make_capture(505, 50.f)).error, ModelError::ok, "publish frame 505");
        restart_pub.force_keyframe();
        auto restarted = restart_pub.publish(make_capture(1, 11.f));
        expect(restarted.error == ModelError::ok && restarted.sent_keyframe && restarted.snapshot.frame == 1 &&
               restarted.snapshot.players[0].x == 11.f, "force_keyframe accepts a restarted frame counter");
        auto restarted_next = restart_pub.publish(make_capture(2, 12.f));
        expect(restarted_next.error == ModelError::ok && !restarted_next.sent_keyframe && restarted_next.snapshot.frame == 2,
               "motion after a restarted keyframe is a delta");
        HostPublisher same_room_restart;
        expect_model(same_room_restart.publish(make_capture(505, 50.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 84)).error,
                     ModelError::ok, "same-room frame 505");
        auto same_room_new = same_room_restart.publish(make_capture(1, 11.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 84));
        expect(same_room_new.error == ModelError::ok && same_room_new.sent_keyframe && same_room_new.snapshot.frame == 1 &&
               same_room_new.snapshot.room_index == 84 && same_room_new.snapshot.players[0].x == 11.f,
               "same-room frame rollback publishes a keyframe");
        auto same_room_next = same_room_restart.publish(make_capture(2, 12.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 84));
        expect(same_room_next.error == ModelError::ok && !same_room_next.sent_keyframe && same_room_next.snapshot.frame == 2,
               "same-room restart continues from the new frame");
        HostPublisher room_rewind;
        expect_model(room_rewind.publish(make_capture(40, 1.f)).error, ModelError::ok, "room rewind base");
        auto room_back = room_rewind.publish(make_capture(3, 2.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 80));
        expect(room_back.error == ModelError::ok && room_back.sent_keyframe && room_back.snapshot.frame == 3 &&
               room_back.snapshot.room_index == 80, "room change accepts a frame rollback");

        std::vector<std::vector<uint8_t>> old_run;
        HostPublisher old_host;
        for (uint32_t frame = 500; frame <= 505; ++frame) {
            auto published = old_host.publish(make_capture(frame, static_cast<float>(frame)));
            expect_model(published.error, ModelError::ok, "old host publish");
            old_run.push_back(std::move(published.bytes));
        }
        auto feed_old_run = [&](GuestIngress& guest) {
            for (const auto& bytes : old_run)
                expect_model(guest.accept(bytes.data(), bytes.size()), ModelError::ok, "guest follows the old host");
            expect(guest.frame() == 505, "guest reached frame 505");
            guest.resync();
            expect(guest.needs_keyframe() && guest.snapshot() == nullptr, "resync dropped the applied world");
        };
        GuestIngress frame1_guest;
        feed_old_run(frame1_guest);
        HostPublisher host_frame1;
        auto seq1_frame1 = host_frame1.publish(make_capture(1, 8.f));
        expect(seq1_frame1.sequence == 1 && seq1_frame1.sent_keyframe, "new host starts at sequence 1 frame 1");
        expect_model(frame1_guest.accept(seq1_frame1.bytes.data(), seq1_frame1.bytes.size()), ModelError::ok,
                     "resync accepts seq 1 frame 1");
        expect(frame1_guest.frame() == 1 && frame1_guest.snapshot()->players[0].x == 8.f && !frame1_guest.needs_keyframe(),
               "frame 1 keyframe replaced the old run");
        GuestIngress frame600_guest;
        feed_old_run(frame600_guest);
        HostPublisher host_frame600;
        auto seq1_frame600 = host_frame600.publish(make_capture(600, 60.f));
        expect(seq1_frame600.sequence == 1 && seq1_frame600.sent_keyframe, "new host starts at sequence 1 frame 600");
        expect_model(frame600_guest.accept(seq1_frame600.bytes.data(), seq1_frame600.bytes.size()), ModelError::ok,
                     "resync accepts seq 1 frame 600");
        expect(frame600_guest.frame() == 600 && frame600_guest.snapshot()->players[0].x == 60.f && !frame600_guest.needs_keyframe(),
               "frame 600 keyframe from a new host applied");

        HostPublisher stuck_host;
        GuestIngress stuck_guest;
        auto stuck_base = stuck_host.publish(make_capture(20, 4.f));
        expect_model(stuck_guest.accept(stuck_base.bytes.data(), stuck_base.bytes.size()), ModelError::ok, "stuck base");
        SnapshotPacket stuck_delta;
        stuck_delta.sequence = 2;
        stuck_delta.keyframe = false;
        stuck_delta.delta.base_frame = 20;
        stuck_delta.delta.frame = 21;
        stuck_delta.delta.room_index = 71;
        stuck_delta.delta.previous_room = 84;
        stuck_delta.delta.players = stuck_guest.snapshot()->players;
        stuck_delta.delta.removed.push_back(999);
        auto stuck_bytes = encode_snapshot(stuck_delta);
        expect_model(stuck_bytes.error, ModelError::ok, "encode rejected delta");
        expect_model(stuck_guest.accept(stuck_bytes.bytes.data(), stuck_bytes.bytes.size()), ModelError::needs_keyframe,
                     "unknown id asks for a keyframe");
        expect(stuck_guest.needs_keyframe() && stuck_guest.frame() == 20, "rejected delta keeps the last good frame");
        SnapshotPacket lower_key;
        lower_key.sequence = 3;
        lower_key.keyframe = true;
        lower_key.full.frame = 1;
        lower_key.full.room_index = 71;
        lower_key.full.previous_room = 84;
        lower_key.full.players = stuck_guest.snapshot()->players;
        lower_key.full.players[0].x = 9.f;
        auto lower_bytes = encode_snapshot(lower_key);
        expect_model(lower_bytes.error, ModelError::ok, "encode lower keyframe");
        expect_model(stuck_guest.accept(lower_bytes.bytes.data(), lower_bytes.bytes.size()), ModelError::ok,
                     "needs_keyframe accepts a keyframe with any frame");
        expect(stuck_guest.frame() == 1 && stuck_guest.snapshot()->players[0].x == 9.f && !stuck_guest.needs_keyframe(),
               "lower keyframe replaced the waiting world");

        HostPublisher same_frame_room;
        GuestIngress same_frame_guest;
        auto room71 = same_frame_room.publish(make_capture(10, 10.f));
        expect_model(room71.error, ModelError::ok, "frame 10 room 71");
        expect_model(same_frame_guest.accept(room71.bytes.data(), room71.bytes.size()), ModelError::ok, "guest at room 71");
        auto room72 = same_frame_room.publish(make_capture(10, 15.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 72));
        expect(room72.error == ModelError::ok && room72.sent_keyframe && room72.sequence != room71.sequence &&
               room72.snapshot.room_index == 72, "same-frame room change is a new keyframe");
        expect_model(same_frame_guest.accept(room72.bytes.data(), room72.bytes.size()), ModelError::ok,
                     "guest applies the same-frame room keyframe");
        expect(same_frame_guest.snapshot()->room_index == 72 && same_frame_guest.frame() == 10 &&
               same_frame_guest.snapshot()->players[0].x == 15.f && !same_frame_guest.needs_keyframe(),
               "room 72 replaced room 71 at frame 10");
        auto room_delta = same_frame_room.publish(make_capture(11, 16.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 72));
        expect(room_delta.error == ModelError::ok && !room_delta.sent_keyframe, "motion after the room keyframe is a delta");
        expect_model(same_frame_guest.accept(room_delta.bytes.data(), room_delta.bytes.size()), ModelError::ok,
                     "delta after the same-frame room keyframe");
        expect(same_frame_guest.frame() == 11 && same_frame_guest.snapshot()->room_index == 72 &&
               same_frame_guest.snapshot()->players[0].x == 16.f && !same_frame_guest.needs_keyframe(),
               "delta applied on room 72");

        HostPublisher late_pub;
        GuestIngress late_guest;
        auto late_seq1 = late_pub.publish(make_capture(10, 10.f));
        auto late_seq2 = late_pub.publish(make_capture(10, 15.f, 0x3CE6A014u, 0x3CE6B028u, 0x01020304u, true, 72));
        expect(late_seq1.sequence == 1 && late_seq1.sent_keyframe && late_seq1.snapshot.room_index == 71 &&
               late_seq2.sequence == 2 && late_seq2.sent_keyframe && late_seq2.snapshot.room_index == 72,
               "seq1 room 71 then seq2 room 72");
        expect_model(late_guest.accept(late_seq2.bytes.data(), late_seq2.bytes.size()), ModelError::ok, "seq2 arrives first");
        expect(late_guest.snapshot()->room_index == 72 && late_guest.frame() == 10, "guest applied room 72");
        expect_model(late_guest.accept(late_seq1.bytes.data(), late_seq1.bytes.size()), ModelError::stale,
                     "older sequence keyframe is stale");
        expect(late_guest.snapshot()->room_index == 72 && late_guest.frame() == 10 && late_guest.snapshot()->players[0].x == 15.f,
               "late seq1 does not roll the room back to 71");

        auto bad = make_capture(1, 1.f);
        bad.players[0].x = std::numeric_limits<float>::infinity();
        expect_model(HostPublisher{}.publish(bad).error, ModelError::nonfinite, "nonfinite capture rejected");
        bad = make_capture(1, 1.f); bad.players[0].pointer = 0;
        expect_model(HostPublisher{}.publish(bad).error, ModelError::bad_pointer, "null player pointer rejected");
        bad = make_capture(1, 1.f);
        bad.entities.push_back(bad.entities.back());
        expect_model(HostPublisher{}.publish(bad).error, ModelError::bad_pointer, "duplicate entity pointer rejected");
        bad = make_capture(1, 1.f);
        bad.entities.push_back(NativeEntity{0, 9, 9, 9, 1.f, 1.f, 0.f, 0.f, 1.f});
        auto skipped = HostPublisher{}.publish(bad);
        expect(skipped.error == ModelError::ok && skipped.snapshot.entities.size() == 2, "null entity pointer is omitted");

        HostPublisher interval_pub;
        int keyframes = 0;
        for (uint32_t frame = 1; frame <= 31; ++frame) {
            auto published = interval_pub.publish(make_capture(frame, static_cast<float>(frame)));
            expect_model(published.error, ModelError::ok, "interval publish");
            if (published.sent_keyframe) ++keyframes;
            if (frame == 30) expect(!published.sent_keyframe, "frame 30 is still a delta");
            if (frame == 31) expect(published.sent_keyframe, "frame 31 is the interval keyframe");
        }
        expect(keyframes == 2, "interval emits two keyframes in 31 frames");

        HostPublisher loss_pub;
        GuestIngress loss_guest;
        auto loss1 = loss_pub.publish(make_capture(1, 1.f));
        auto loss2 = loss_pub.publish(make_capture(2, 2.f));
        auto loss3 = loss_pub.publish(make_capture(3, 3.f));
        expect_model(loss_guest.accept(loss3.bytes.data(), loss3.bytes.size()), ModelError::needs_keyframe, "delta before keyframe waits");
        expect(loss_guest.snapshot() == nullptr, "early delta does not invent a world");
        expect_model(loss_guest.accept(loss1.bytes.data(), loss1.bytes.size()), ModelError::ok, "keyframe after a future delta");
        expect(loss_guest.frame() == 1, "future delta stays buffered until its base arrives");
        expect_model(loss_guest.accept(loss2.bytes.data(), loss2.bytes.size()), ModelError::ok, "reorder fills the gap");
        expect(loss_guest.frame() == 3 && loss_guest.snapshot()->players[0].x == 3.f, "reordered deltas converge");
        expect_model(loss_guest.accept(loss2.bytes.data(), loss2.bytes.size()), ModelError::duplicate, "duplicate delta ignored");
        loss_pub.force_keyframe();
        auto loss_key = loss_pub.publish(make_capture(40, 40.f));
        GuestIngress gap_guest;
        expect_model(gap_guest.accept(loss1.bytes.data(), loss1.bytes.size()), ModelError::ok, "gap base");
        expect_model(gap_guest.accept(loss3.bytes.data(), loss3.bytes.size()), ModelError::buffered, "missing delta is buffered");
        expect(gap_guest.frame() == 1, "gap does not skip ahead");
        expect_model(gap_guest.accept(loss_key.bytes.data(), loss_key.bytes.size()), ModelError::ok, "keyframe recovers the gap");
        expect(gap_guest.frame() == 40 && gap_guest.snapshot()->players[0].x == 40.f, "recovery snapshot is the keyframe");
        auto older = decode_snapshot(loss1.bytes.data(), loss1.bytes.size());
        expect(older.error == ModelError::ok, "decode older keyframe");
        SnapshotPacket stale_key = older.packet;
        stale_key.sequence = 99;
        auto stale_bytes = encode_snapshot(stale_key);
        expect_model(stale_bytes.error, ModelError::ok, "encode stale keyframe");
        expect_model(gap_guest.accept(stale_bytes.bytes.data(), stale_bytes.bytes.size()), ModelError::stale, "older keyframe does not roll the room back");
        expect(gap_guest.snapshot()->room_index == 71 && gap_guest.frame() == 40, "stale keyframe left the world alone");

        auto broken = loss3.bytes;
        broken.back() ^= 0x5au;
        GuestIngress checksum_guest;
        expect_model(checksum_guest.accept(loss1.bytes.data(), loss1.bytes.size()), ModelError::ok, "checksum base");
        expect_model(checksum_guest.accept(broken.data(), broken.size()), ModelError::bad_checksum, "flipped byte rejected");
        expect(checksum_guest.frame() == 1, "checksum failure does not apply");
        expect_model(GuestIngress{}.accept(loss1.bytes.data(), 10), ModelError::truncated, "short packet");
        auto wrong_version = loss1.bytes;
        wrong_version[4] = 9;
        expect_model(checksum_guest.accept(wrong_version.data(), wrong_version.size()), ModelError::bad_version, "version mismatch");
        expect_model(checksum_guest.accept(loss_key.bytes.data(), loss_key.bytes.size()), ModelError::incompatible, "version mismatch sticks");
        expect(checksum_guest.frame() == 1, "rejected version did not replace the world");

        SnapshotPacket bad_delta;
        bad_delta.sequence = 50;
        bad_delta.keyframe = false;
        bad_delta.delta.base_frame = 40;
        bad_delta.delta.frame = 41;
        bad_delta.delta.room_index = 71;
        bad_delta.delta.previous_room = 84;
        bad_delta.delta.players = gap_guest.snapshot()->players;
        bad_delta.delta.removed.push_back(999);
        auto bad_delta_bytes = encode_snapshot(bad_delta);
        const float before = gap_guest.snapshot()->players[0].x;
        expect_model(gap_guest.accept(bad_delta_bytes.bytes.data(), bad_delta_bytes.bytes.size()), ModelError::needs_keyframe, "unknown id rejects the whole delta");
        expect(gap_guest.snapshot()->players[0].x == before && gap_guest.frame() == 40, "rejected delta is not half-applied");

        HostPublisher crowd_pub;
        NativeCapture crowd;
        crowd.frame = 7; crowd.room_index = 3; crowd.previous_room = 2;
        crowd.players.push_back(NativePlayer{0xA1000001u, 15.f, 25.f, 0.f, 0.f, 10.f});
        crowd.entities.push_back(NativeEntity{0xA1000001u, 1, 0, 0x01010101u, 15.f, 25.f, 0.f, 0.f, 10.f});
        for (uint32_t i = 0; i < 60; ++i) {
            crowd.entities.push_back(NativeEntity{0xA1000100u + i * 0x100u, 10, 1, 0x42000000u + i,
                                                   static_cast<float>(i), 5.f, 0.f, 0.f, 4.f});
        }
        const auto started = std::chrono::steady_clock::now();
        PublishResult crowd_pub_result;
        for (int i = 0; i < 100; ++i) {
            HostPublisher once;
            crowd_pub_result = once.publish(crowd);
            if (crowd_pub_result.error != ModelError::ok) break;
        }
        const auto elapsed_us = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - started).count();
        const auto average_us = elapsed_us / 100;
        expect_model(crowd_pub_result.error, ModelError::ok, "60 entity publish");
        expect(crowd_pub_result.snapshot.entities.size() == 61, "60 monsters plus the player entity");
        expect(crowd_pub_result.bytes.size() < 8192, "60 entity keyframe stays small");
        expect(!payload_has_u32(crowd_pub_result.bytes, 0xA1000100u) && !payload_has_u32(crowd_pub_result.bytes, 0xA1000001u),
               "crowd pointers stripped");
        expect(average_us < 2000, "offline 60-entity encode is well under a frame");
        GuestIngress crowd_guest;
        expect_model(crowd_guest.accept(crowd_pub_result.bytes.data(), crowd_pub_result.bytes.size()), ModelError::ok, "guest accepts 60");
        expect(crowd_guest.snapshot()->entities.size() == 61, "guest stores 60 monsters");

        LoopbackHub hub;
        AuthorityLink host(config_for(LinkRole::capture, 7), hub.left());
        AuthorityLink preview(config_for(LinkRole::preview, 7), hub.right());
        expect(host.start(1000) && preview.start(1000), "hello sent");
        pump(host, preview, 1000);
        expect(host.phase() == LinkPhase::active && preview.phase() == LinkPhase::active, "handshake");
        expect(!host.playable() && !preview.playable() && !host.facts().playable && !host.facts().native_memory_apply &&
               !host.facts().steam_transport_wired && !host.facts().in_game_verified, "link facts stay research-only");
        auto streamed = host.publish_capture(make_capture(10, 320.f), 1000);
        expect(streamed.error == LinkError::ok && streamed.keyframe, "host streams a keyframe");
        expect(preview.publish_capture(make_capture(11, 1.f), 1000).error == LinkError::wrong_role, "guest cannot publish world");
        preview.poll(1100);
        expect(preview.snapshot() != nullptr && preview.snapshot()->players[0].x == 320.f && preview.plan().room_index == 71,
               "guest pose follows the host snapshot");
        expect(host.snapshot() == nullptr, "host link does not mirror a guest world");
        hub.inject(0, kChannelState, streamed.bytes);
        host.poll(1200);
        expect(host.snapshot() == nullptr && host.phase() == LinkPhase::active, "injected state does not write the host");

        InputFrame input;
        input.frame = 10; input.player_slot = 1; input.buttons = kInputLeft; input.aim_x = 1.f; input.aim_y = -1.f;
        expect(preview.publish_input(input, 1200) == LinkError::ok, "guest input sent");
        expect(host.publish_input(input, 1200) == LinkError::wrong_role, "host does not send remote input");
        host.poll(1200);
        expect(host.latest_input() != nullptr && host.latest_input()->buttons == kInputLeft && host.latest_input()->player_slot == 1,
               "host stores guest input only");
        input.player_slot = 0;
        expect(preview.publish_input(input, 1200) == LinkError::rejected, "slot 0 is the host's own input");
        input.player_slot = 1; input.frame = 9;
        expect(preview.publish_input(input, 1200) == LinkError::stale, "old input frame rejected");
        expect(host.latest_input()->buttons == kInputLeft, "stale input did not replace the host copy");
        input.frame = 11; input.buttons = kInputShoot;
        expect(preview.publish_input(input, 1300) == LinkError::ok, "newer input sent");
        host.poll(1300);
        expect(host.latest_input()->buttons == kInputShoot && host.latest_input()->frame == 11, "newer input replaces");

        host.tick(5000); preview.tick(5000);
        expect(host.phase() == LinkPhase::paused && preview.phase() == LinkPhase::paused, "silence pauses the link");
        expect(host.publish_capture(make_capture(12, 4.f), 4002).error == LinkError::not_active, "paused host does not stream deltas");
        expect(host.reconnect(5000) && preview.reconnect(5000), "reconnect hello");
        pump(host, preview, 5000);
        expect(host.phase() == LinkPhase::active && preview.phase() == LinkPhase::active, "reconnect restores the session");
        auto recovered = host.publish_capture(make_capture(12, 8.f), 5100);
        expect(recovered.error == LinkError::ok && recovered.keyframe, "post-reconnect snapshot is a keyframe");
        preview.poll(5100);
        expect(preview.snapshot()->frame == 12 && preview.snapshot()->players[0].x == 8.f && !preview.awaiting_keyframe(),
               "guest applies the recovery keyframe");

        LoopbackHub loss_hub;
        AuthorityLink loss_host(config_for(LinkRole::capture, 7), loss_hub.left());
        AuthorityLink loss_preview(config_for(LinkRole::preview, 7), loss_hub.right());
        loss_host.start(1); loss_preview.start(1); pump(loss_host, loss_preview, 1);
        loss_hub.drop_next(1);
        expect(loss_host.publish_capture(make_capture(1, 1.f), 1).error == LinkError::ok, "dropped send still returns");
        auto after_drop = loss_host.publish_capture(make_capture(2, 2.f), 1);
        loss_preview.poll(1);
        expect(loss_preview.snapshot() == nullptr && loss_preview.awaiting_keyframe(), "a lone delta does not start the guest");
        loss_host.force_keyframe();
        auto catchup = loss_host.publish_capture(make_capture(3, 9.f), 1);
        expect(catchup.keyframe, "forced keyframe");
        loss_preview.poll(1);
        expect(loss_preview.snapshot() != nullptr && loss_preview.snapshot()->frame == 3 && loss_preview.snapshot()->players[0].x == 9.f,
               "keyframe catch-up after loss");
        (void)after_drop;

        LoopbackHub order_hub;
        AuthorityLink order_host(config_for(LinkRole::capture, 7), order_hub.left());
        AuthorityLink order_preview(config_for(LinkRole::preview, 7), order_hub.right());
        order_host.start(1); order_preview.start(1); pump(order_host, order_preview, 1);
        order_hub.reorder_next_pair(1);
        expect(order_host.publish_capture(make_capture(1, 4.f), 1).error == LinkError::ok, "reorder first");
        expect(order_host.publish_capture(make_capture(2, 6.f), 1).error == LinkError::ok, "reorder second");
        order_preview.poll(1);
        expect(order_preview.snapshot() != nullptr && order_preview.snapshot()->frame == 2 && order_preview.snapshot()->players[0].x == 6.f,
               "reordered keyframe then delta still converges");

        LoopbackHub dup_hub;
        AuthorityLink dup_host(config_for(LinkRole::capture, 7), dup_hub.left());
        AuthorityLink dup_preview(config_for(LinkRole::preview, 7), dup_hub.right());
        dup_host.start(1); dup_preview.start(1); pump(dup_host, dup_preview, 1);
        dup_hub.duplicate_next(1);
        expect(dup_host.publish_capture(make_capture(1, 4.f), 1).error == LinkError::ok, "duplicate send");
        dup_preview.poll(1);
        expect(dup_preview.snapshot()->frame == 1 && dup_preview.phase() == LinkPhase::active, "duplicate snapshot ignored");

        LoopbackHub bad_hub;
        AuthorityLink bad_host(config_for(LinkRole::capture, 1), bad_hub.left());
        AuthorityLink bad_preview(config_for(LinkRole::preview, 2), bad_hub.right());
        bad_host.start(1); bad_preview.start(1); pump(bad_host, bad_preview, 1);
        expect(bad_host.phase() == LinkPhase::incompatible && bad_preview.phase() == LinkPhase::incompatible, "manifest mismatch locks");
        expect(!bad_host.reconnect(2) && bad_host.phase() == LinkPhase::incompatible, "mismatch cannot be cleared");

        LoopbackHub ad_hub;
        AuthorityLink ad_preview(config_for(LinkRole::preview, 7), ad_hub.right());
        HelloMessage advertisement;
        advertisement.type = 1; advertisement.role = LinkRole::capture; advertisement.research_only = 0;
        advertisement.session = "test-session"; advertisement.manifest.fill(7);
        auto ad_bytes = encode_hello(advertisement);
        expect(ad_bytes.error == ModelError::ok, "encode refused advertisement");
        ad_hub.inject(1, kChannelControl, ad_bytes.bytes);
        ad_preview.poll(1);
        expect(ad_preview.phase() == LinkPhase::incompatible, "research_only 0 locks the link");
        AuthorityLink ad_host(config_for(LinkRole::capture, 7), ad_hub.left());
        expect(ad_host.start(2), "later good hello is sent");
        ad_preview.poll(2);
        expect(ad_preview.phase() == LinkPhase::incompatible, "playable advertisement cannot be cleared");

        LoopbackHub role_hub;
        AuthorityLink role_a(config_for(LinkRole::capture, 7), role_hub.left());
        AuthorityLink role_b(config_for(LinkRole::capture, 7), role_hub.right());
        role_a.start(1); role_b.start(1); pump(role_a, role_b, 1);
        expect(role_a.phase() == LinkPhase::waiting && role_b.phase() == LinkPhase::waiting, "same role does not activate or lock");

        LoopbackHub foreign_hub;
        AuthorityLink foreign_preview(config_for(LinkRole::preview, 7), foreign_hub.right());
        HelloMessage foreign = advertisement;
        foreign.research_only = 1; foreign.session = "other-session";
        foreign_hub.inject(1, kChannelControl, encode_hello(foreign).bytes);
        foreign_preview.poll(1);
        expect(foreign_preview.phase() == LinkPhase::waiting, "foreign session ignored");
        AuthorityLink foreign_host(config_for(LinkRole::capture, 7), foreign_hub.left());
        foreign_host.start(2); foreign_preview.start(2); pump(foreign_host, foreign_preview, 2);
        expect(foreign_preview.phase() == LinkPhase::active, "matching hello still activates");

        auto poisoned = encode_hello(advertisement);
        poisoned.bytes[4] = 99;
        LoopbackHub version_hub;
        AuthorityLink version_preview(config_for(LinkRole::preview, 7), version_hub.right());
        version_hub.inject(1, kChannelControl, poisoned.bytes);
        version_preview.poll(1);
        expect(version_preview.phase() == LinkPhase::incompatible, "control version mismatch locks");

        std::cout << "{\"passed\":" << passed
                  << ",\"encode_60_us_average\":" << average_us
                  << ",\"in_game_timing\":false,\"live_game_test\":false,\"two_machine_test\":false,\"playable\":false}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAILED: " << error.what() << " after " << passed << " checks\n";
        return 1;
    }
}
