"""Analyze stack-sampler JSONL against the game's .text section.

Maps observed return addresses to call sites and an approximate enclosing function
start, then ranks them by how consistently they appear on each thread. All output is
module-relative; no instruction bytes are copied out of the sampled process, only the
on-disk executable is disassembled for the report.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path


def parse_pe(data: bytes) -> dict:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Bad PE signature")
    machine, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    if machine != 0x14C:
        raise ValueError("Expected x86 PE32")
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    table = pe + 24 + optional_size
    sections = []
    for index in range(section_count):
        at = table + index * 40
        name, virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<8sIIII", data, at)
        sections.append({
            "name": name.rstrip(b"\0").decode("ascii", "replace"),
            "va": virtual_address,
            "raw": raw_offset,
            "size": max(virtual_size, raw_size),
            "raw_size": raw_size,
        })
    return {"image_base": image_base, "sections": sections, "data": data}


def text_section(pe: dict) -> tuple[bytes, int, int]:
    for section in pe["sections"]:
        if section["name"] == ".text":
            code = pe["data"][section["raw"]:section["raw"] + section["raw_size"]]
            return code, section["va"], section["size"]
    raise ValueError("No .text section")


def build_call_returns(code: bytes, text_va: int) -> dict[int, int]:
    """Map every possible post-call RVA to the emitting call RVA (E8 rel32)."""
    returns = {}
    for position in range(len(code) - 5):
        if code[position] != 0xE8:
            continue
        returns[text_va + position + 5] = text_va + position
    return returns


def build_function_starts(code: bytes, text_va: int) -> list[int]:
    """Approximate function starts: byte after a run of INT3 padding, or a known prologue."""
    starts = set()
    for position in range(1, len(code) - 4):
        if code[position] == 0xCC and code[position - 1] == 0xCC and code[position + 1] != 0xCC:
            starts.add(text_va + position + 1)
        if code[position - 1] in (0xCC, 0x90) and code[position:position + 3] == b"\x55\x8b\xec":
            starts.add(text_va + position)
        if code[position:position + 4] == b"\x8b\xff\x55\x8b":
            starts.add(text_va + position)
    return sorted(starts)


def enclosing(starts: list[int], rva: int) -> int | None:
    import bisect
    index = bisect.bisect_right(starts, rva) - 1
    return starts[index] if index >= 0 else None


def analyze(samples: Path, exe: Path, top: int = 40) -> dict:
    pe = parse_pe(exe.read_bytes())
    code, text_va, text_size = text_section(pe)
    call_returns = build_call_returns(code, text_va)
    starts = build_function_starts(code, text_va)

    header = None
    per_thread: dict[int, dict[int, int]] = {}
    sample_count = 0
    with samples.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if record.get("kind") == "header":
                header = record
            elif record.get("kind") == "sample":
                sample_count += 1
                for thread in record.get("threads", []):
                    bucket = per_thread.setdefault(thread["tid"], {})
                    for rva in thread.get("stack_rvas", []):
                        bucket[rva] = bucket.get(rva, 0) + 1

    def annotate(rva: int) -> dict:
        start = enclosing(starts, rva)
        call_site = call_returns.get(rva)
        return {
            "rva": rva,
            "call_return": call_site is not None,
            "call_site_rva": call_site,
            "function_start_rva": start,
        }

    threads = []
    for tid, counts in per_thread.items():
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        threads.append({
            "tid": tid,
            "distinct_rvas": len(counts),
            "top": [dict(annotate(rva), count=count) for rva, count in ranked[:top]],
        })
    threads.sort(key=lambda item: (-item["distinct_rvas"], item["tid"]))

    overall: dict[int, int] = {}
    for counts in per_thread.values():
        for rva, count in counts.items():
            overall[rva] = overall.get(rva, 0) + 1
    ranked_overall = sorted(overall.items(), key=lambda item: (-item[1], item[0]))[:top]
    return {
        "samples": sample_count,
        "header": header,
        "threads": threads,
        "overall": [dict(annotate(rva), thread_samples=count) for rva, count in ranked_overall],
        "exe": str(exe),
        "read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()
    result = analyze(args.samples, args.exe, args.top)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "samples": result["samples"],
        "threads": [{"tid": item["tid"], "distinct": item["distinct_rvas"]} for item in result["threads"][:4]],
        "top_overall": [
            {"rva": hex(item["rva"]), "count": item["thread_samples"],
             "function_start": hex(item["function_start_rva"]) if item["function_start_rva"] is not None else None,
             "call_return": item["call_return"]}
            for item in result["overall"][:12]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
