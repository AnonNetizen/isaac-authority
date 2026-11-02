"""Back up Isaac progress/configuration, then restore our verified laser patch."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parents[2]

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(game: Path, documents: Path, steam: Path, output: Path) -> dict:
    helper = WORKSPACE / "patch_watch_out_laser.py"
    if not helper.is_file(): helper = Path(__file__).resolve().parent / "legacy" / "patch_watch_out_laser.py"
    spec = importlib.util.spec_from_file_location("laser_patch", helper)
    patch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch)
    patch.ensure_game_closed()
    source = patch.validate_mod(game / "mods" / "watch_out_laser!_2887926286")
    before = patch.inspect(source)
    if before["status"] not in ("original_supported", "patched_verified", "patched_v1_verified"):
        raise ValueError("Laser mod does not match the verified original/patch; refusing to restore.")
    # Exclusive directory creation keeps older backups intact.
    output.mkdir(parents=True, exist_ok=False)
    candidates = []
    candidates += [("documents", p, documents) for p in documents.glob("*")
                   if p.is_file() and p.suffix.lower() in (".dat", ".ini")]
    candidates += [("mod-data", p, game / "data") for p in (game / "data").rglob("*") if p.is_file()]
    for remote in (steam / "userdata").glob("*/250900/remote"):
        candidates += [("steam", p, steam / "userdata") for p in remote.rglob("*") if p.is_file()]
        cache = remote.parent / "remotecache.vdf"
        if cache.is_file(): candidates.append(("steam", cache, steam / "userdata"))
    candidates += [("laser", source, source.parent)]
    for name in (patch.BACKUP_NAME, patch.MANIFEST_NAME):
        path = source.with_name(name)
        if path.is_file(): candidates.append(("laser", path, source.parent))
    records = []
    for kind, path, root in candidates:
        if path.is_symlink(): raise ValueError(f"Refusing symlink in backup: {path}")
        relative = Path(kind) / path.relative_to(root)
        dest = output / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        original_hash = digest(path)
        shutil.copy2(path, dest)
        if digest(dest) != original_hash or digest(path) != original_hash:
            raise ValueError(f"Backup verification failed: {path}")
        records.append({"source": str(path), "backup": str(relative), "sha256": original_hash,
                        "bytes": dest.stat().st_size})
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "files": records,
                "laser_before": before, "automatic_save_restore": False}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    patch.ensure_game_closed()
    manifest["laser_after"] = patch.restore(source)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"backup": str(output), "files_verified": len(records), "laser_status": manifest["laser_after"]["status"]}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--steam", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.game.resolve(), args.documents.resolve(), args.steam.resolve(), args.output.resolve()), indent=2))
