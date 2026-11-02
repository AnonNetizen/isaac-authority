"""Read-only Game/Level memory sampler for a room-transition experiment.

At a fixed interval it reads the Game singleton, Level pointer and Level's first
0x8000 bytes, recording `room_index` from `Game+0x18304`, `previous_room_index` from
`Game+0x18308`, the duplicate at `Game+0x1B850`, entity count/base, and a hash of the
Level window. It never writes target memory and never injects code. The resulting JSONL
is diffed offline to observe room changes and entity-list churn.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample_game_stacks as stacks

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def read_u32(handle, address):
    data = stacks.read_memory(handle, address, 4)
    return struct.unpack("<I", data)[0] if len(data) == 4 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-id", type=int, required=True)
    parser.add_argument("--seconds", type=float, default=90.0)
    parser.add_argument("--interval-ms", type=float, default=200.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    handle = kernel32.OpenProcess(stacks.PROCESS_QUERY_INFORMATION | stacks.PROCESS_VM_READ, False, args.process_id)
    if not handle:
        print("OpenProcess failed", file=sys.stderr)
        return 2
    try:
        base, _ = stacks.find_game_module(handle)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + args.seconds
        count = 0
        with args.output.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps({"kind": "header", "pid": args.process_id, "module_base": base}) + "\n")
            while time.monotonic() < deadline:
                game = read_u32(handle, base + 0x871678)
                level = read_u32(handle, game + 0x18300) if game else None
                data = stacks.read_memory(handle, level, 0x8000) if level else b""
                record = {
                    "kind": "sample",
                    "time": time.time(),
                    "game": game,
                    "level": level,
                    "room_index": read_u32(handle, game + 0x18304) if game else None,
                    "previous_room_index": read_u32(handle, game + 0x18308) if game else None,
                    "room_index_copy": read_u32(handle, game + 0x1B850) if game else None,
                    "entity_count": read_u32(handle, level + 0x1264) if level else None,
                    "entity_base": read_u32(handle, level + 0x125C) if level else None,
                    "level_sha256": hashlib.sha256(data).hexdigest() if data else None,
                }
                stream.write(json.dumps(record) + "\n")
                stream.flush()
                count += 1
                time.sleep(args.interval_ms / 1000.0)
        print(json.dumps({"samples": count, "output": str(args.output)}))
        return 0
    finally:
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
