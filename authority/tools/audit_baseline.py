"""Read-only audit of baseline copies and current originals; never restores user saves."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

def audit(baseline):
    manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
    records = []
    for record in manifest["files"]:
        relative = record["backup"]
        saved, source = baseline / relative, Path(record["source"])
        saved_hash = digest(saved) if saved.is_file() else None
        current_hash = digest(source) if source.is_file() else None
        # Exclude account IDs and absolute paths from the distributable audit.
        label = source.name if relative.startswith("steam") else relative.replace("\\", "/")
        records.append({"file": label, "baseline_sha256": record["sha256"],
                        "backup_sha256": saved_hash, "backup_verified": saved_hash == record["sha256"],
                        "current_sha256": current_hash, "current_matches_backup": current_hash == record["sha256"]})
        if label == "laser/main.lua":
            records[-1]["expected_laser_restore_verified"] = current_hash == manifest.get("laser_after", {}).get("source_sha256")
    return {"audited_utc": datetime.now(timezone.utc).isoformat(), "read_only": True,
            "automatic_restore": False, "files": records,
            "backups_verified": sum(r["backup_verified"] for r in records),
            "current_files_changed_or_missing": [r["file"] for r in records
                if not r["current_matches_backup"] and not r.get("expected_laser_restore_verified", False)]}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.baseline.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("backups_verified", "current_files_changed_or_missing")}, ensure_ascii=False))
