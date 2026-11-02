"""Verify cleanup candidates; deletion is performed by cleanup_artifacts.ps1.

Only byte-identical package copies and explicit compiler/Python caches qualify.
Unique results, archives, binaries, generated sources and dependencies are kept.
All hashing and ZIP reads are streamed. No game or research suite is launched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import sys
from datetime import datetime, timezone
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "authority"
PAIRS = (
    ("reports/slice2-portable-final", "isaac-authority-slice2-0.1.0-final.zip"),
    ("reports/slice3-portable-final", "isaac-authority-slice3-0.1.0-final.zip"),
    ("reports/slice3-portable-verified", "isaac-authority-slice3-0.1.0-verified.zip"),
    ("reports/slice3-ui-portable-verified", "isaac-authority-slice3-ui-0.1.0.zip"),
    ("reports/ui-bounded-extracted", "isaac-authority-ui-bounded-0.1.0.zip"),
    ("reports/ui-incremental-extracted", "isaac-authority-ui-incremental-0.1.1.zip"),
    ("reports/ui-incremental-optimization-reproduction/unpacked", "isaac-authority-ui-incremental-0.1.4.zip"),
    ("reports/ui-incremental-reproduction/unpacked", "isaac-authority-ui-incremental-0.1.2.zip"),
    ("reports/ui-incremental-reproduction-final/unpacked", "isaac-authority-ui-incremental-0.1.3.zip"),
    ("artifacts/slice-final-portable-verification", "isaac-authority-slice-0.1.0-final.zip"),
    ("artifacts/trace-final-portable-verification", "isaac-authority-trace-0.1.0-final.zip"),
    ("artifacts/trace-portable-verification", "isaac-authority-trace-0.1.0.zip"),
)
CACHE_SUFFIXES = {".obj", ".pch", ".ipch", ".idb", ".ilk", ".tlog", ".lastbuildstate"}
ENTRY_FILES = (
    "build-ui-incremental-encoded-v3-release/Release/authority-ui-incremental-research.exe",
    "build-ui-incremental-encoded-v3-release/Release/authority-trace-research.exe",
    "build-ui-incremental-encoded-v3-release/Release/ia_lua533_ui_incremental.dll",
    "build-ui-incremental-encoded-v3-release/Release/ia_lua533_reference.dll",
    "build-ui-bounded-release/Release/ia_lua533_ui_bounded.dll",
    "build-slice3-release/Release/ia_lua533_trace.dll",
    "build-slice3-release/Release/ia_lua533_slice.dll",
    "build-slice3-release/Release/ia_lua533_slice2.dll",
    "build-slice3-release/Release/ia_lua533_slice3.dll",
    "build-ui-incremental-encoded/Release/authority_core.lib",
    "build-ui-incremental-encoded/Release/authority_lua_bridge.lib",
    "build-ui-incremental-encoded/resource_catalog.hpp",
    "build-ui-incremental-factored/incremental_ui_runtime/generated-lua/lvm.c",
    "build-ui-incremental-10m/incremental_ui_runtime/generated-lua/lvm.c",
)


def emit(stage, **values):
    print(json.dumps({"stage": stage, **values}, ensure_ascii=False), flush=True)


def sha(stream):
    h = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        h.update(chunk)
    return h.hexdigest()


def digest(path):
    with path.open("rb") as stream:
        return sha(stream)


def checked(path):
    path = Path(os.path.abspath(path))
    if path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError("Target must be inside the workspace: " + str(path))
    for item in (path, *path.parents):
        if item == ROOT.parent:
            break
        if item.exists() and item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Reparse point is not a cleanup target: " + str(item))
    return path


def files(base):
    checked(base if base != ROOT else base / "authority")
    pending = [base]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in sorted(entries, key=lambda e: e.name):
                attrs = entry.stat(follow_symlinks=False).st_file_attributes
                if attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError("Refusing to traverse reparse point: " + entry.path)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)


def archive_members(archive):
    expected = archive.with_suffix(".zip.sha256").read_text(encoding="ascii").split()[0].lower()
    if digest(archive) != expected:
        raise ValueError("Archive SHA256 mismatch: " + str(archive))
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        names = [entry.filename for entry in entries if not entry.is_dir()]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("Duplicate ZIP member")
        for entry in entries:
            p = PurePosixPath(entry.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in entry.filename or ":" in entry.filename:
                raise ValueError("Unsafe ZIP member: " + entry.filename)
        prefixes = {name.split("/", 1)[0] for name in names}
        if len(prefixes) != 1:
            raise ValueError("Expected one package root")
        prefix = next(iter(prefixes)) + "/"
        if prefix + "FILES.json" in names:
            index_name = prefix + "FILES.json"
            definition = json.loads(z.read(index_name))
            declarations = definition["files"]
            expected_sizes = {}
        else:
            index_name = prefix + "bundle-manifest.json"
            definition = json.loads(z.read(index_name))
            declarations = {row["path"]: row["sha256"] for row in definition["files"]}
            expected_sizes = {row["path"]: row["bytes"] for row in definition["files"]}
            if len(declarations) != len(definition["files"]):
                raise ValueError("Duplicate manifest record")
        if set(names) != {index_name, *(prefix + name for name in declarations)}:
            raise ValueError("ZIP file set does not match its manifest")
        members = {}
        for entry in entries:
            if entry.is_dir():
                continue
            with z.open(entry) as stream:
                actual = sha(stream)  # EOF also verifies the member CRC.
            relative = entry.filename[len(prefix):]
            if entry.filename != index_name:
                if actual != declarations[relative]:
                    raise ValueError("ZIP member hash mismatch: " + entry.filename)
                if relative in expected_sizes and entry.file_size != expected_sizes[relative]:
                    raise ValueError("ZIP member size mismatch: " + entry.filename)
            members[entry.filename] = {"bytes": entry.file_size, "sha256": actual}
    return expected, members


def cache_reason(path):
    relative = path.relative_to(ROOT)
    parts = relative.parts
    # Installed tools, backups and frozen inputs are never cache targets.
    if parts[0] in (".tools", "artifacts"):
        return None
    if path.suffix.lower() == ".pyc" and "__pycache__" in parts:
        return "python_cache"
    if len(parts) > 2 and parts[0] == "authority" and (parts[1] == "build" or parts[1].startswith("build-")):
        if path.suffix.lower() in CACHE_SUFFIXES:
            return "compiler_cache"
    return None


def entry_dependencies():
    records = []
    for relative in ENTRY_FILES:
        p = AUTHORITY / relative
        checked(p)
        row = {"path": p.relative_to(ROOT).as_posix(), "exists": p.is_file()}
        if p.is_file():
            row["sha256"] = digest(p)
            if p.suffix.lower() in (".exe", ".dll"):
                with p.open("rb") as stream:
                    header = stream.read(64)
                    stream.seek(struct.unpack_from("<I", header, 60)[0])
                    signature = stream.read(6)
                row["x86_pe"] = signature == b"PE\0\0\x4c\x01"
        records.append(row)
    if not all(row["exists"] and row.get("x86_pe", True) for row in records):
        raise ValueError("Command-line dependency is missing or not x86: " + repr(records))
    return records


def save_audit():
    from audit_baseline import audit
    value = audit(ROOT / "artifacts/authority-baseline-20261009")
    return {"files": value["files"], "backups_verified": value["backups_verified"],
            "current_files_changed_or_missing": value["current_files_changed_or_missing"]}


def write_report(path, report):
    # A single durable report; atomically replace only our own previous version.
    temp = path.with_suffix(".writing")
    checked(temp)
    with temp.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    os.replace(temp, path)


def prepare(report_path):
    checked(report_path)
    if report_path.exists() or report_path.with_suffix(".deleted.jsonl").exists():
        raise ValueError("Use a fresh report path; existing audit is preserved")
    report = {"schema": "isaac-verified-cleanup-1", "workspace": str(ROOT),
              "started_utc": datetime.now(timezone.utc).isoformat(), "status": "prepared",
              "game_started": False, "large_suites_executed": False,
              "free_bytes_before": shutil.disk_usage(ROOT).free,
              "archives": [], "candidates": [], "preserved_extraction_files": []}
    candidates = {}
    for relative, archive_name in PAIRS:
        base = AUTHORITY / relative
        if not base.exists():
            continue
        archive = checked(AUTHORITY / "artifacts" / archive_name)
        emit("archive_verifying", archive=archive_name)
        archive_sha, members = archive_members(archive)
        matched = 0
        for p in files(base):
            member = p.relative_to(base).as_posix()
            info = members.get(member)
            key = p.relative_to(ROOT).as_posix()
            if info and p.stat().st_size == info["bytes"] and digest(p) == info["sha256"]:
                candidates[key] = {"path": key, "reason": "verified_package_duplicate", **info,
                                   "archive": archive.relative_to(ROOT).as_posix(), "member": member}
                matched += info["bytes"]
            else:
                report["preserved_extraction_files"].append({"path": key, "reason": "extra_or_different_from_archive"})
        report["archives"].append({"path": archive.relative_to(ROOT).as_posix(), "sha256": archive_sha,
                                   "files_verified": len(members), "extraction": base.relative_to(ROOT).as_posix(),
                                   "duplicate_bytes": matched})
        emit("archive_verified", archive=archive_name, duplicate_gib=round(matched / 2**30, 3))
    all_files = list(files(ROOT))
    for p in all_files:
        reason = cache_reason(p)
        key = p.relative_to(ROOT).as_posix()
        if reason and key not in candidates:
            candidates[key] = {"path": key, "reason": reason, "bytes": p.stat().st_size, "sha256": digest(p)}
    report["candidates"] = [candidates[key] for key in sorted(candidates)]
    report["protected"] = {}
    read_bytes = 0
    next_progress = 0
    for p in all_files:
        key = p.relative_to(ROOT).as_posix()
        if key not in candidates:
            size = p.stat().st_size
            report["protected"][key] = {"bytes": size, "sha256": digest(p)}
            read_bytes += size
            if read_bytes >= next_progress:
                emit("protected_snapshot", files=len(report["protected"]), gib=round(read_bytes / 2**30, 2))
                next_progress = read_bytes + 2**30
    report["entry_dependencies_before"] = entry_dependencies()
    report["save_audit_before"] = save_audit()
    report["candidate_bytes"] = sum(c["bytes"] for c in candidates.values())
    report["candidate_count"] = len(candidates)
    write_report(report_path, report)
    emit("ready", report=str(report_path), candidates=len(candidates), gib=round(report["candidate_bytes"] / 2**30, 3),
         protected_files=len(report["protected"]))


def finish(report_path):
    checked(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["workspace"] != str(ROOT) or report["schema"] != "isaac-verified-cleanup-1":
        raise ValueError("Unexpected cleanup report")
    journal = report_path.with_suffix(".deleted.jsonl")
    operations = []
    if journal.exists():
        with journal.open(encoding="utf-8-sig") as stream:
            operations = [json.loads(line) for line in stream if line.strip()]
    by_path = {op["path"]: op for op in operations if op["operation"] == "delete_file"}
    failures = []
    deleted = 0
    for row in report["candidates"]:
        p = checked(ROOT / row["path"])
        op = by_path.get(row["path"])
        row["deleted"] = bool(op and not p.exists() and op["sha256"] == row["sha256"])
        if row["deleted"]:
            deleted += row["bytes"]
        else:
            failures.append({"path": row["path"], "reason": "candidate_not_confirmed_deleted"})
    verified = 0
    read_bytes = 0
    next_progress = 0
    for relative, info in report["protected"].items():
        p = checked(ROOT / relative)
        if not p.is_file() or p.stat().st_size != info["bytes"] or digest(p) != info["sha256"]:
            failures.append({"path": relative, "reason": "protected_file_changed_or_missing"})
        else:
            verified += 1
        read_bytes += info["bytes"]
        if read_bytes >= next_progress:
            emit("protected_verified", files=verified, gib=round(read_bytes / 2**30, 2))
            next_progress = read_bytes + 2**30
    report["entry_dependencies_after"] = entry_dependencies()
    report["save_audit_after"] = save_audit()
    if report["entry_dependencies_after"] != report["entry_dependencies_before"]:
        failures.append({"reason": "command_line_dependencies_changed"})
    if report["save_audit_after"] != report["save_audit_before"]:
        failures.append({"reason": "save_or_backup_audit_changed"})
    report["extraction_differences"] = report.pop("preserved_extraction_files")
    for row in report["extraction_differences"]:
        row["preserved"] = checked(ROOT / row["path"]).is_file()
        if not row["preserved"]:
            row["removed_as"] = next((c["reason"] for c in report["candidates"] if c["path"] == row["path"]), "unconfirmed")
    report.update(status="completed" if not failures else "incomplete", failures=failures,
                  protected_files_verified=verified, deleted_logical_bytes=deleted,
                  deleted_file_count=sum(row["deleted"] for row in report["candidates"]),
                  empty_directories_removed=[op["path"] for op in operations if op["operation"] == "delete_empty_directory"],
                  finished_utc=datetime.now(timezone.utc).isoformat(), free_bytes_after=shutil.disk_usage(ROOT).free)
    report["observed_free_space_increase_bytes"] = report["free_bytes_after"] - report["free_bytes_before"]
    write_report(report_path, report)
    if not failures:
        journal.unlink()  # Its contents are now retained in the verified final report.
    emit("finished", status=report["status"], deleted_files=report["deleted_file_count"],
         deleted_gib=round(deleted / 2**30, 3), protected_files=verified,
         removed_empty_directories=len(report["empty_directories_removed"]), failures=len(failures))
    if failures:
        raise ValueError("Cleanup verification failed; see durable report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "finish"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    {"prepare": prepare, "finish": finish}[args.action](args.report.resolve())
