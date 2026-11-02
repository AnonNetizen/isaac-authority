"""Read-only PE32 candidate scan for engine virtual functions.

Locates vtables by absolute references to a known virtual function RVA (Game.Render
candidate from the REPENTOGON donor signatures) and scores every vtable slot against
the known Game.Update prologue. A unique match remains a candidate, never permission
to hook it: calling convention, object layout and lifetime still require runtime
verification on the tested binary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path


def parse_pe(data: bytes) -> dict:
    if data[:2] != b"MZ":
        raise ValueError("Not a PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Bad PE signature")
    machine, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    if machine != 0x14C:
        raise ValueError("Expected x86 PE32")
    magic = struct.unpack_from("<H", data, pe + 24)[0]
    if magic != 0x10B:
        raise ValueError("Expected PE32 optional header")
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sections = []
    table = pe + 24 + optional_size
    for index in range(section_count):
        at = table + index * 40
        name, virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<8sIIII", data, at)
        flags = struct.unpack_from("<I", data, at + 36)[0]
        sections.append({
            "name": name.rstrip(b"\0").decode("ascii", "replace"),
            "virtual_size": virtual_size,
            "virtual_address": virtual_address,
            "raw_size": raw_size,
            "raw_offset": raw_offset,
            "executable": bool(flags & 0x20000000),
            "readable": bool(flags & 0x40000000),
            "writable": bool(flags & 0x80000000),
        })
    return {"image_base": image_base, "sections": sections, "size": len(data)}


def section_for_va(pe: dict, va: int) -> dict | None:
    offset = va - pe["image_base"]
    for section in pe["sections"]:
        if section["virtual_address"] <= offset < section["virtual_address"] + max(section["virtual_size"], section["raw_size"]):
            return section
    return None


def executable_va(pe: dict, value: int) -> bool:
    section = section_for_va(pe, value)
    return bool(section and section["executable"])


def read_va(pe: dict, data: bytes, va: int, size: int) -> bytes | None:
    section = section_for_va(pe, va)
    if section is None:
        return None
    delta = va - pe["image_base"] - section["virtual_address"]
    if delta < 0 or delta + size > section["raw_size"]:
        return None
    start = section["raw_offset"] + delta
    return data[start:start + size]


def plausible_entry(pe: dict, value: int) -> bool:
    return value == 0 or executable_va(pe, value)


def find_vtables(pe: dict, data: bytes, target_va: int, max_slots: int = 120) -> list[dict]:
    pattern = struct.pack("<I", target_va)
    results = []
    seen = set()
    for section in pe["sections"]:
        if section["executable"] or not section["readable"]:
            continue
        raw = data[section["raw_offset"]:section["raw_offset"] + section["raw_size"]]
        for match in re.finditer(re.escape(pattern), raw):
            hit_offset = match.start()
            if hit_offset % 4:
                continue
            hit_va = pe["image_base"] + section["virtual_address"] + hit_offset
            if hit_va in seen:
                continue
            seen.add(hit_va)
            # Walk backwards then forwards while entries look like module code pointers.
            start = hit_va
            for _ in range(max_slots):
                previous = read_va(pe, data, start - 4, 4)
                if previous is None:
                    break
                value = struct.unpack("<I", previous)[0]
                if not plausible_entry(pe, value):
                    break
                start -= 4
            entries = []
            cursor = start
            while len(entries) < max_slots * 2:
                chunk = read_va(pe, data, cursor, 4)
                if chunk is None:
                    break
                value = struct.unpack("<I", chunk)[0]
                if not plausible_entry(pe, value):
                    break
                entries.append(value)
                cursor += 4
            if len(entries) < 5 or target_va not in entries:
                continue
            slot = entries.index(target_va)
            results.append({
                "vtable_va": start,
                "vtable_rva": start - pe["image_base"],
                "section": section["name"],
                "slots": len(entries),
                "render_slot": slot,
                "rtti_pointer": struct.unpack("<I", read_va(pe, data, start - 4, 4))[0] if start >= pe["image_base"] + 4 and read_va(pe, data, start - 4, 4) else None,
                "entries": [
                    {"slot": index, "va": value, "rva": value - pe["image_base"] if value else None,
                     "section": (section_for_va(pe, value) or {}).get("name") if value else None}
                    for index, value in enumerate(entries)
                ],
            })
    return results


def score_prefix(pe: dict, data: bytes, va: int) -> dict:
    """Compare the first bytes with the donor Game.Update SEH prologue variants."""
    code = read_va(pe, data, va, 32)
    if not code:
        return {"prefix": "", "score": 0, "matched": []}
    patterns = {
        "donor_full": "558bec6aff68????????64a1????????5083ec3c5657a1????????33c5508d45??64a3????????8bf9",
        "relaxed": "558bec6aff68????????64a1????????5083ec??5657",
        "relaxed_alt": "558bec6aff68????????64a1????????5056578d45??64a3",
    }
    best = 0
    matched = []
    for name, pattern in patterns.items():
        expression = b"".join(b"." if pattern[i:i + 2] == "??" else re.escape(bytes.fromhex(pattern[i:i + 2]))
                              for i in range(0, len(pattern), 2))
        length = len(expression)
        if re.match(expression, code, re.DOTALL):
            matched.append(name)
            best = max(best, len(pattern) // 2)
    return {"prefix": code[:24].hex(), "score": best, "matched": matched}


def scan(exe: Path, render_rva: int) -> dict:
    data = exe.read_bytes()
    pe = parse_pe(data)
    target_va = pe["image_base"] + render_rva
    vtables = find_vtables(pe, data, target_va)
    for vtable in vtables:
        slots = []
        for entry in vtable["entries"]:
            item = dict(entry)
            if entry["va"]:
                item["update"] = score_prefix(pe, data, entry["va"])
            else:
                item["update"] = {"prefix": "", "score": 0, "matched": []}
            slots.append(item)
        vtable["slots_detail"] = slots
        vtable["update_slots"] = [
            item for item in slots if item["update"]["score"] >= 16
        ]
    return {
        "game_sha256": hashlib.sha256(data).hexdigest(),
        "image_base": pe["image_base"],
        "render_candidate_rva": hex(render_rva),
        "render_candidate_va": hex(target_va),
        "vtable_candidates": vtables,
        "read_only": True,
        "candidate_is_not_verified_symbol": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--render-rva", type=lambda value: int(value, 0), default=0x406C20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.exe, args.render_rva)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "vtables": len(result["vtable_candidates"]),
        "candidates": [
            {"vtable_rva": hex(item["vtable_rva"]), "slots": item["slots"],
             "render_slot": item["render_slot"], "update_slots": len(item["update_slots"])}
            for item in result["vtable_candidates"]
        ],
    }, indent=2))
