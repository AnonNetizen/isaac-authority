"""Read-only PE/signature audit. A unique match is a candidate, never permission to hook it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

COMMIT = "9b84409f1c7fa0c50cef5473d7b7a883b94c1b53"
ROOT_URL = f"https://github.com/TeamREPENTOGON/REPENTOGON/blob/{COMMIT}/libzhl/functions/"
SIGNATURES = [
    ("Game.Update", "Game.zhl", "558bec6aff68????????64a1????????5083ec3c5657a1????????33c5508d45??64a3????????8bf9"),
    ("Game.Render", "Game.zhl", "538bdc83ec0883e4f883c404558b6b??896c24??8bec6aff68????????64a1????????505381ec20020000"),
    ("Game.SaveState", "Game.zhl", "558bec6aff68????????64a1????????5083ec78a1????????33c58945??535657508d45??64a3????????8bf1"),
    ("Game.RestoreState", "Game.zhl", "558bec6aff68????????64a1????????5081ecac000000a1????????33c58945??535657508d45??64a3????????8bf9"),
    ("PersistentGameData.TryUnlock", "PersistentGameData.zhl", "558bec83e4f8568bf157807e??00"),
]

def audit(exe: Path):
    data = exe.read_bytes()
    if data[:2] != b"MZ": raise ValueError("Not a PE image")
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if data[pe:pe+4] != b"PE\0\0": raise ValueError("Bad PE signature")
    machine, sections = struct.unpack_from("<HH", data, pe+4)
    optional_size = struct.unpack_from("<H", data, pe+20)[0]
    if machine != 0x14c or struct.unpack_from("<H", data, pe+24)[0] != 0x10b:
        raise ValueError("Expected x86 PE32")
    executable_sections = []
    for i in range(sections):
        at = pe+24+optional_size+i*40
        name, virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<8sIIII", data, at)
        flags = struct.unpack_from("<I", data, at+36)[0]
        if flags & 0x20000000:
            executable_sections.append((name.rstrip(b"\0").decode(), rva, raw_offset, data[raw_offset:raw_offset+raw_size]))
    records = []
    for name, source, pattern in SIGNATURES:
        expression = b"".join(b"." if pattern[i:i+2] == "??" else re.escape(bytes.fromhex(pattern[i:i+2]))
                              for i in range(0, len(pattern), 2))
        matches = []
        for section, rva, offset, code in executable_sections:
            for match in re.finditer(b"(?=" + expression + b")", code, re.DOTALL):
                matches.append({"section": section, "rva": hex(rva+match.start()), "file_offset": hex(offset+match.start())})
        records.append({"name": name, "source": ROOT_URL+source, "pattern": pattern, "matches": matches,
                        "status": "unique_candidate" if len(matches) == 1 else "missing" if not matches else "ambiguous",
                        "abi_verified_on_j460": False, "installed_by_this_audit": False})
    return {"game_sha256": hashlib.sha256(data).hexdigest(), "donor_commit": COMMIT,
            "read_only": True, "candidate_is_not_verified_symbol": True, "hooks": records}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.exe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({r["name"]: {"status": r["status"], "matches": len(r["matches"])} for r in result["hooks"]}, indent=2))
