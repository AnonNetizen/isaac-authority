"""Fingerprint gameplay code/resources; local mod data/configuration stays separate."""
import argparse
import hashlib
import json
from pathlib import Path

def build_manifest(game: Path, binary_dir: Path):
    records = []
    for directory, prefix in [(game, "game"), (binary_dir, "extension")]:
        if prefix == "game":
            files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in (".exe", ".dll")]
            for root_name in ("mods", "resources", "resources-dlc3"):
                root = directory / root_name
                if root.is_dir(): files.extend(p for p in root.rglob("*") if p.is_file())
        else: files = [directory / "isaac_authority_probe.dll"]
        for path in sorted(files):
            if path.is_symlink(): raise ValueError(f"Symlink not supported: {path}")
            if path.name.endswith((".bak", ".backup")) or path.name in ("isaac-stability-v1.json", "isaac-stability.json"): continue
            relative = prefix + "/" + path.relative_to(directory).as_posix()
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            records.append({"path": relative, "sha256": digest, "bytes": path.stat().st_size})
    records.sort(key=lambda r: r["path"])
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return {"schema": 1, "digest": hashlib.sha256(canonical).hexdigest(), "files": records,
            "local_configuration_included": False, "loaded_native_module_inventory_verified": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--binary-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_manifest(args.game.resolve(), args.binary_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"digest": result["digest"], "files": len(result["files"])}))
