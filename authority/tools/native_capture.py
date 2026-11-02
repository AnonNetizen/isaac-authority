"""Byte layout of the J460 native capture blob written by probe.cpp.

This is the host-local recording, pointers included. It is not the guest wire
format. A synthetic fixture is not an in-game recording.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path


def encode_capture(document: dict) -> bytes:
    players = document["players"]
    entities = document["entities"]
    if len(players) > 8 or len(entities) > 128:
        raise ValueError("capture exceeds the probe caps")
    out = struct.pack("<IIII", document["frame"], document["room_index"], document["previous_room"], len(players))
    for player in players:
        out += struct.pack("<Ifffff", _u32(player["pointer"]), player["x"], player["y"], player["vx"], player["vy"], player["size"])
    out += struct.pack("<I", len(entities))
    for entity in entities:
        out += struct.pack(
            "<IIIIfffff",
            _u32(entity["pointer"]),
            entity["type"],
            entity["variant"],
            _u32(entity["init_seed"]),
            entity["x"],
            entity["y"],
            entity["vx"],
            entity["vy"],
            entity["size"],
        )
    return out


def decode_capture(blob: bytes) -> dict:
    if len(blob) < 16:
        raise ValueError("truncated capture")
    frame, room, previous, player_count = struct.unpack_from("<IIII", blob, 0)
    if player_count > 8:
        raise ValueError("too many players")
    offset = 16
    players = []
    for _ in range(player_count):
        if offset + 24 > len(blob):
            raise ValueError("truncated player")
        pointer, x, y, vx, vy, size = struct.unpack_from("<Ifffff", blob, offset)
        players.append({"pointer": pointer, "x": x, "y": y, "vx": vx, "vy": vy, "size": size})
        offset += 24
    if offset + 4 > len(blob):
        raise ValueError("truncated entity count")
    (entity_count,) = struct.unpack_from("<I", blob, offset)
    offset += 4
    if entity_count > 128:
        raise ValueError("too many entities")
    entities = []
    for _ in range(entity_count):
        if offset + 36 > len(blob):
            raise ValueError("truncated entity")
        pointer, kind, variant, seed, x, y, vx, vy, size = struct.unpack_from("<IIIIfffff", blob, offset)
        entities.append({
            "pointer": pointer, "type": kind, "variant": variant, "init_seed": seed,
            "x": x, "y": y, "vx": vx, "vy": vy, "size": size,
        })
        offset += 36
    if offset != len(blob):
        raise ValueError("trailing capture bytes")
    return {
        "frame": frame,
        "room_index": room,
        "previous_room": previous,
        "players": players,
        "entities": entities,
    }


def _u32(value) -> int:
    if isinstance(value, str):
        return int(value, 16)
    return int(value)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
