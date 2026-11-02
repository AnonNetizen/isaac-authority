"""Find native field offsets from a state-probe snapshot.

The state probe records Lua-visible truth (player/entity position, velocity, size,
seed) together with bounded raw memory dumps of the Game object, the first player,
and the first room entity. This script searches the dumps for the exact float32/int
encodings of those truth values and reports candidate offsets. A candidate is only a
lead: the same value can appear in unrelated fields, so offsets must be re-checked on
a second capture before they are treated as a contract.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def decode(hex_text: str) -> bytes:
    return bytes.fromhex(hex_text)


def find_float(data: bytes, value: float, limit: int = 32) -> list[int]:
    target = struct.pack("<f", value)
    hits = []
    for offset in range(0, len(data) - 3, 4):
        if data[offset:offset + 4] == target:
            hits.append(offset)
            if len(hits) >= limit:
                break
    return hits


def find_pair(data: bytes, x: float, y: float, limit: int = 32) -> list[int]:
    fx = struct.pack("<f", x)
    fy = struct.pack("<f", y)
    hits = []
    for offset in range(0, len(data) - 7, 4):
        if data[offset:offset + 4] == fx and data[offset + 4:offset + 8] == fy:
            hits.append(offset)
            if len(hits) >= limit:
                break
    return hits


def find_u32(data: bytes, value: int, limit: int = 32) -> list[int]:
    target = struct.pack("<I", value & 0xFFFFFFFF)
    hits = []
    for offset in range(0, len(data) - 3, 4):
        if data[offset:offset + 4] == target:
            hits.append(offset)
            if len(hits) >= limit:
                break
    return hits


def analyze(report: dict) -> dict:
    result = {"source_scope": "read-only state probe", "candidates": {}}
    player = report.get("player") or {}
    dump = player.get("dump_0x1000_hex")
    if dump and player.get("position"):
        data = decode(dump)
        position = player["position"]
        velocity = player.get("velocity", {})
        result["candidates"]["player"] = {
            "pointer": player.get("ptr"),
            "payload_hex": player.get("payload_hex"),
            "position_offset_candidates": find_pair(data, float(position["x"]), float(position["y"])),
            "velocity_offset_candidates": find_pair(data, float(velocity.get("x", 0.0)), float(velocity.get("y", 0.0))),
            "size_offset_candidates": find_float(data, float(player.get("size", 0.0))),
            "seed_offset_candidates": find_u32(data, int(player.get("seed", 0))),
        }
    entities = report.get("entities") or ([report["entity0"]] if report.get("entity0") else [])
    entity = entities[0] if entities else {}
    dump = entity.get("dump_0x800_hex")
    if dump and entity.get("position"):
        data = decode(dump)
        position = entity["position"]
        velocity = entity.get("velocity", {})
        result["candidates"]["entity0"] = {
            "pointer": entity.get("ptr"),
            "payload_hex": entity.get("payload_hex"),
            "position_offset_candidates": find_pair(data, float(position["x"]), float(position["y"])),
            "velocity_offset_candidates": find_pair(data, float(velocity.get("x", 0.0)), float(velocity.get("y", 0.0))),
            "seed_offset_candidates": find_u32(data, int(entity.get("seed", 0))),
            "type_offset_candidates": find_u32(data, int(entity.get("type", 0))),
            "variant_offset_candidates": find_u32(data, int(entity.get("variant", 0))),
        }
    game = report.get("game") or {}
    if game.get("ptr"):
        result["candidates"]["room_index"] = {
            "game_offset": "0x18304",
            "value": game.get("room_index"),
            "previous": game.get("previous_room_index"),
            "copy": game.get("room_index_copy"),
            "lua_room": game.get("room"),
        }
        windows = {}
        for key, base_offset in (("head_0x0_hex", 0x0), ("dump_0x28000_hex", 0x0), ("head_0x18000_hex", 0x18000),
                                 ("head_0x1ba00_hex", 0x1BA00), ("head_0x26000_hex", 0x26000)):
            hex_text = game.get(key)
            if not hex_text:
                continue
            data = decode(hex_text)
            window = {"base_offset": base_offset}
            if player.get("ptr"):
                window["player_pointer_offsets"] = [base_offset + off for off in find_u32(data, int(player["ptr"], 16))]
            if entity.get("ptr"):
                window["entity_pointer_offsets"] = [base_offset + off for off in find_u32(data, int(entity["ptr"], 16))]
            window["frame_offsets"] = [base_offset + off for off in find_u32(data, int(game.get("frame", 0)))]
            window["stage_offsets"] = [base_offset + off for off in find_u32(data, int(game.get("stage", 0)))]
            window["room_offsets"] = [base_offset + off for off in find_u32(data, int(game.get("room_index", game.get("room", 0))))]
            windows[key] = window
        sub_hex = game.get("sub_0x18300_hex")
        if sub_hex:
            data = decode(sub_hex)
            window = {"base": game.get("ptr_0x18300")}
            if player.get("ptr"):
                window["player_pointer_offsets"] = find_u32(data, int(player["ptr"], 16))
            if entity.get("ptr"):
                window["entity_pointer_offsets"] = find_u32(data, int(entity["ptr"], 16))
            window["frame_offsets"] = find_u32(data, int(game.get("frame", 0)))
            window["stage_offsets"] = find_u32(data, int(game.get("stage", 0)))
            window["room_offsets"] = find_u32(data, int(game.get("room_index", game.get("room", 0))))
            windows["sub_0x18300"] = window
        level_hex = game.get("level_0x8000_hex")
        if level_hex:
            data = decode(level_hex)
            pointer_to_entity = {}
            for item in entities:
                pointer = item.get("ptr")
                if pointer:
                    pointer_to_entity[int(pointer, 16)] = item.get("index")
            entity_offsets = []
            for offset in range(0, len(data) - 3, 4):
                value = struct.unpack_from("<I", data, offset)[0]
                if value in pointer_to_entity:
                    entity_offsets.append({"offset": offset, "entity_index": pointer_to_entity[value], "value": hex(value)})
            runs = []
            for offset in range(0, len(data) - 7, 4):
                first = struct.unpack_from("<I", data, offset)[0]
                second = struct.unpack_from("<I", data, offset + 4)[0]
                if first in pointer_to_entity and second in pointer_to_entity:
                    runs.append({"offset": offset, "entities": [pointer_to_entity[first], pointer_to_entity[second]]})
            window = {
                "base": game.get("ptr_0x18300"),
                "entity_pointer_offsets": entity_offsets,
                "entity_pointer_runs": runs,
                "player_pointer_offsets": find_u32(data, int(player["ptr"], 16)) if player.get("ptr") else [],
                "stage_offsets": find_u32(data, int(game.get("stage", 0))),
                "room_offsets": find_u32(data, int(game.get("room_index", game.get("room", 0)))),
            }
            windows["level_0x8000"] = window
        level_full_hex = game.get("level_0x20000_hex")
        if level_full_hex:
            data = decode(level_full_hex)
            windows["level_0x20000"] = {
                "base": game.get("ptr_0x18300"),
                "stage_offsets": find_u32(data, int(game.get("stage", 0))),
                "room_offsets": find_u32(data, int(game.get("room_index", game.get("room", 0)))),
            }
        child_dumps = game.get("level_child_dumps") or []
        children = []
        for child in child_dumps:
            hex_text = child.get("hex")
            if not hex_text:
                continue
            data = decode(hex_text)
            children.append({
                "offset": child.get("offset"),
                "value": child.get("value"),
                "stage_offsets": find_u32(data, int(game.get("stage", 0))),
                "room_offsets": find_u32(data, int(game.get("room_index", game.get("room", 0)))),
            })
        windows["level_children"] = children
        result["candidates"]["game_windows"] = windows
    result["truth"] = {
        "game": {key: game.get(key) for key in ("ptr", "frame", "num_players", "stage", "room")},
        "player": {key: player.get(key) for key in ("ptr", "position", "velocity", "size", "seed")},
        "entities": [
            {key: item.get(key) for key in ("index", "ptr", "position", "velocity", "seed", "type", "variant")}
            for item in entities
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["candidates"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
