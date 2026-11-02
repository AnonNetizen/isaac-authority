"""Install, inspect, verify, diagnose, or restore a reversible compatibility patch for Watch out, laser!."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

VERSION = 2
TOOL_VERSION = "2.0.0"
WORKSHOP_ID = "2887926286"
ORIGINAL_SHA256 = "8651d5155e9223f800fe78332e16dbf50b452ab417a1d1080a5bcb3c8e69a25b"
KNOWN_SOURCES = {ORIGINAL_SHA256: {"mod_version": "1.1", "label": "workshop 1.1"}}
BACKUP_NAME = "main.lua.isaac-stability-v1.backup"
MANIFEST_NAME = "isaac-stability.json"
LEGACY_MANIFEST_NAME = "isaac-stability-v1.json"

MARKER_V1 = "ISAAC_COOP_STABILITY_V1_BEGIN"
MARKER_V1_END = "ISAAC_COOP_STABILITY_V1_END"
MARKER_V2 = "ISAAC_COOP_STABILITY_V2_BEGIN"
MARKER_V2_END = "ISAAC_COOP_STABILITY_V2_END"

RENDER_ANCHOR = "function postRender(self)"
START_ANCHOR = "    local function postGameStarted(self)"
POST_UPDATE_REGISTRATION = "mod:AddCallback(ModCallback.POST_UPDATE, postRender)"
POST_STARTED_REGISTRATION = "mod:AddCallback(ModCallback.POST_GAME_STARTED, postGameStarted)"
DISPATCHERS = ("IHateDelirium", "VanillaElseIfHell", "RevCompatibility")
FINGERPRINT_LENGTH = 12
HEALTHY_STATUSES = ("original_supported", "patched_verified", "patched_v1_verified")

PAYLOAD = Path(__file__).with_name("coop_guard.lua")

INSTALL_NOTE = (
    "Both players must install the same patch and start a NEW run. "
    "Run 'verify' on both machines and compare PATCH FINGERPRINT."
)
RESTORE_NOTE = "Original mod file restored; the backup is kept in the mod directory."
VERIFY_NOTE = "Both players must show the same PATCH FINGERPRINT before starting a new run."


class UnsupportedSource(ValueError):
    def __init__(self, message: str, *, source_sha256: str = "", structure_ok: bool = False, problems=None):
        super().__init__(message)
        self.source_sha256 = source_sha256
        self.structure_ok = structure_ok
        self.problems = list(problems or [])


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(digest: str) -> str:
    return digest[:FINGERPRINT_LENGTH].upper()


def _newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _payload(nl: str) -> str:
    text = PAYLOAD.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    return text.replace("\n", nl) + nl


def _structure(text: str) -> dict:
    """Check the layout invariants required by the guarded callback injection."""
    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")
    problems = []
    metrics = {"post_render_lines": 0, "spawn_functions": [], "dispatcher_call_lines": []}

    if MARKER_V1 in text or MARKER_V2 in text:
        problems.append("file already contains a stability patch marker")

    def indexes(value):
        return [i for i, line in enumerate(lines) if line == value]

    render = indexes(RENDER_ANCHOR)
    started = indexes(START_ANCHOR)
    if len(render) != 1:
        problems.append(f"expected exactly one '{RENDER_ANCHOR}' line, found {len(render)}")
    if len(started) != 1:
        problems.append(f"expected exactly one postGameStarted anchor, found {len(started)}")

    update_calls = [line for line in lines if line.strip() == POST_UPDATE_REGISTRATION and not line.strip().startswith("--")]
    started_calls = [line for line in lines if line.strip() == POST_STARTED_REGISTRATION and not line.strip().startswith("--")]
    if len(update_calls) != 1:
        problems.append(f"expected exactly one POST_UPDATE postRender registration, found {len(update_calls)}")
    if len(started_calls) != 1:
        problems.append(f"expected exactly one POST_GAME_STARTED postGameStarted registration, found {len(started_calls)}")

    definitions = []
    for index, line in enumerate(lines):
        match = re.match(r"^function ([A-Za-z_][A-Za-z0-9_]*)\(", line)
        if match:
            definitions.append((index, match.group(1)))

    post_render_body = ""
    if len(render) == 1 and len(definitions) >= 1:
        following = [index for index, _ in definitions if index > render[0]]
        end = following[0] if following else len(lines)
        body_lines = lines[render[0] + 1:end]
        post_render_body = "\n".join(body_lines)
        metrics["post_render_lines"] = len(body_lines)
        if not 5 <= len(body_lines) <= 200:
            problems.append(f"postRender body has unexpected size ({len(body_lines)} lines)")
        for expected in ("VanillaElseIfHell", "LaserIndicator", "TargetLaserIndicator"):
            if expected not in post_render_body:
                problems.append(f"postRender body no longer references {expected}")

    for position, (index, name) in enumerate(definitions):
        end = definitions[position + 1][0] if position + 1 < len(definitions) else len(lines)
        body = "\n".join(lines[index + 1:end])
        if "Isaac.Spawn(" not in body:
            continue
        if re.search(r"\b1000\b", body) and re.search(r"\b198\b", body):
            metrics["spawn_functions"].append(name)
            if post_render_body and not re.search(r"\b" + re.escape(name) + r"\b", post_render_body):
                problems.append(f"indicator spawn function {name} is not referenced from postRender")

    if not metrics["spawn_functions"]:
        problems.append("no indicator spawn function found")

    if len(render) == 1 and post_render_body:
        following = [index for index, _ in definitions if index > render[0]]
        body_start = render[0] + 1
        body_end = following[0] if following else len(lines)
        for dispatcher in DISPATCHERS:
            call_lines = [
                index for index, line in enumerate(lines)
                if re.search(r"\b" + re.escape(dispatcher) + r"\s*\(", line)
                and not line.strip().startswith("function ")
                and not line.strip().startswith("--")
            ]
            metrics["dispatcher_call_lines"].extend(call_lines)
            outside = [index for index in call_lines if not (body_start <= index < body_end)]
            if outside:
                problems.append(f"{dispatcher} is called outside postRender (lines {outside[:5]})")

    return {"ok": not problems, "problems": problems, "metrics": metrics}


def _verify_patched_text(text: str, nl: str) -> None:
    gate = "    if isaacCoopStabilityShouldSkip() then" + nl + "        return" + nl + "    end" + nl
    reset = (
        "        isaacCoopStabilityBlocked = false" + nl
        + "        isaacCoopStabilityDecided = false" + nl
    )
    checks = [
        (text.count(MARKER_V2), 1, "v2 marker"),
        (MARKER_V1 in text, False, "v1 marker"),
        (text.count(RENDER_ANCHOR + nl + gate), 1, "guard gate"),
        (text.count(START_ANCHOR + nl + reset), 1, "state reset"),
    ]
    for actual, expected, label in checks:
        if actual != expected:
            raise RuntimeError(f"internal patch verification failed: {label}")
    if MARKER_V2_END not in text:
        raise RuntimeError("internal patch verification failed: end marker missing")


def build_patch(original: bytes, *, allow_unreviewed: bool = False) -> bytes:
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedSource("main.lua is not valid UTF-8; no files were changed.") from exc
    digest = sha256(original)
    structure = _structure(text)
    if not structure["ok"]:
        raise UnsupportedSource(
            "Unexpected Watch out, laser! layout; no files were changed.",
            source_sha256=digest,
            structure_ok=False,
            problems=structure["problems"],
        )
    if digest not in KNOWN_SOURCES and not allow_unreviewed:
        raise UnsupportedSource(
            "Unsupported Watch out, laser! version; no files were changed. "
            "Run restore with the old tool, update this patch, or pass --allow-unreviewed.",
            source_sha256=digest,
            structure_ok=True,
            problems=[],
        )

    nl = _newline_for(text)
    guard = _payload(nl)
    gate = "    if isaacCoopStabilityShouldSkip() then" + nl + "        return" + nl + "    end" + nl
    reset = (
        "        isaacCoopStabilityBlocked = false" + nl
        + "        isaacCoopStabilityDecided = false" + nl
    )
    if text.count(RENDER_ANCHOR + nl) != 1 or text.count(START_ANCHOR + nl) != 1:
        raise UnsupportedSource(
            "Unexpected Watch out, laser! layout; no files were changed.",
            source_sha256=digest,
            structure_ok=False,
            problems=["anchor lines are not unique with the detected newline style"],
        )
    text = text.replace(RENDER_ANCHOR + nl, guard + RENDER_ANCHOR + nl + gate, 1)
    text = text.replace(START_ANCHOR + nl, START_ANCHOR + nl + reset, 1)
    patched = text.encode("utf-8")
    _verify_patched_text(patched.decode("utf-8"), nl)
    return patched


def revert_v1(current: bytes) -> bytes:
    """Reverse the historical v1 injection so the file can be upgraded or restored."""
    try:
        text = current.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("v1 patch is not valid UTF-8; cannot reverse it.") from exc
    parts = re.split(r"(?<=\n)", text)
    begin = next((i for i, part in enumerate(parts) if part.startswith("-- " + MARKER_V1)), None)
    end = next((i for i, part in enumerate(parts) if part.startswith("-- " + MARKER_V1_END)), None)
    if begin is None or end is None or end < begin:
        raise ValueError("v1 patch markers are missing or damaged; cannot reverse it.")
    parts = parts[:begin] + parts[end + 1:]

    signature = next((i for i, part in enumerate(parts) if part.rstrip("\r\n") == RENDER_ANCHOR), None)
    gate = [
        "    if isaacCoopStabilityShouldSkip() then",
        "        return",
        "    end",
    ]
    if signature is None or signature + 3 >= len(parts):
        raise ValueError("v1 guard gate is missing; cannot reverse it.")
    if [part.rstrip("\r\n") for part in parts[signature + 1:signature + 4]] != gate:
        raise ValueError("v1 guard gate has unexpected content; cannot reverse it.")
    parts = parts[:signature + 1] + parts[signature + 4:]

    anchor = next((i for i, part in enumerate(parts) if part.rstrip("\r\n") == START_ANCHOR), None)
    if anchor is None or anchor + 1 >= len(parts):
        raise ValueError("v1 postGameStarted reset is missing; cannot reverse it.")
    if parts[anchor + 1].rstrip("\r\n") != "        isaacCoopStabilityBlocked = false":
        raise ValueError("v1 postGameStarted reset has unexpected content; cannot reverse it.")
    parts = parts[:anchor + 1] + parts[anchor + 2:]

    reverted = "".join(parts).encode("utf-8")
    if MARKER_V1 in reverted.decode("utf-8"):
        raise ValueError("v1 patch reversal left markers behind; cannot reverse it.")
    return reverted


def discover_mod() -> Path:
    if sys.platform != "win32":
        raise ValueError("Use --mod-dir to select your installed Watch out, laser! directory.")
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except OSError as exc:
        raise ValueError("Steam was not found; use --mod-dir.") from exc
    roots = [steam]
    libraries = steam / "steamapps" / "libraryfolders.vdf"
    if libraries.is_file():
        for match in re.finditer(r'"path"\s+"([^\"]+)"', libraries.read_text(encoding="utf-8")):
            roots.append(Path(match[1].replace("\\\\", "\\")))
    found = set()
    for root in roots:
        manifest = root / "steamapps" / "appmanifest_250900.acf"
        if not manifest.is_file():
            continue
        match = re.search(r'"installdir"\s+"([^\"]+)"', manifest.read_text(encoding="utf-8"))
        if match:
            mods = root / "steamapps" / "common" / match[1] / "mods"
            if mods.is_dir():
                for directory in mods.glob("*" + WORKSHOP_ID):
                    if directory.is_dir():
                        found.add(directory.resolve())
    if len(found) != 1:
        raise ValueError(f"Found {len(found)} matching mod directories; use --mod-dir.")
    return found.pop()


def ensure_game_closed() -> None:
    if sys.platform != "win32":
        return
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq isaac-ng.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, check=True, errors="replace",
    )
    for row in csv.reader(io.StringIO(result.stdout)):
        if row and row[0].lower() == "isaac-ng.exe":
            raise ValueError("Close Isaac before installing, verifying, or restoring this patch.")


def validate_mod(directory: Path) -> Path:
    directory = directory.resolve(strict=True)
    metadata = ET.parse(directory / "metadata.xml").getroot()
    if metadata.findtext("id", "").strip() != WORKSHOP_ID:
        raise ValueError("The selected directory is not Watch out, laser! (2887926286).")
    source = directory / "main.lua"
    if source.is_symlink() or not source.is_file():
        raise ValueError("main.lua must be a regular file inside the selected mod directory.")
    return source


def read_mod_version(directory: Path) -> str:
    try:
        metadata = ET.parse(directory / "metadata.xml").getroot()
        return metadata.findtext("version", "").strip() or "unknown"
    except (OSError, ET.ParseError):
        return "unknown"


def atomic_write(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".isaac-stability-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _base_result(source: Path) -> dict:
    return {
        "status": "unsupported_version",
        "mod_dir": str(source.parent),
        "mod_id": WORKSHOP_ID,
        "mod_version": read_mod_version(source.parent),
        "guard_version": None,
        "source_sha256": sha256(source.read_bytes()),
        "original_sha256": None,
        "patched_sha256": None,
        "fingerprint": None,
        "source_basis": None,
        "unreviewed_source": False,
        "backup_present": source.with_name(BACKUP_NAME).is_file(),
        "backup_matches_original": False,
        "warnings": [],
    }


def inspect(source: Path) -> dict:
    current = source.read_bytes()
    digest = sha256(current)
    backup = source.with_name(BACKUP_NAME)
    result = _base_result(source)
    result["source_sha256"] = digest

    if digest == ORIGINAL_SHA256:
        patched = build_patch(current)
        result.update(
            status="original_supported",
            original_sha256=digest,
            patched_sha256=sha256(patched),
            fingerprint=fingerprint(sha256(patched)),
            source_basis="known_source",
        )
        if backup.is_file():
            result["backup_matches_original"] = backup.read_bytes() == current
        return result

    if MARKER_V2.encode() in current:
        if not backup.is_file():
            result.update(status="patched_needs_attention")
            result["warnings"].append("backup_missing")
            return result
        original = backup.read_bytes()
        result["original_sha256"] = sha256(original)
        try:
            expected = build_patch(original, allow_unreviewed=True)
        except UnsupportedSource:
            result.update(status="patched_needs_attention")
            result["warnings"].append("cannot_verify_source")
            return result
        if current != expected:
            result.update(status="patched_needs_attention")
            result["warnings"].append("additional_edits")
            result["backup_matches_original"] = original == backup.read_bytes()
            return result
        known = sha256(original) in KNOWN_SOURCES
        result.update(
            status="patched_verified",
            guard_version=2,
            patched_sha256=sha256(expected),
            fingerprint=fingerprint(sha256(expected)),
            source_basis="known_source" if known else "unreviewed_structure",
            unreviewed_source=not known,
            backup_matches_original=True,
        )
        return result

    if MARKER_V1.encode() in current:
        if not backup.is_file():
            result.update(status="patched_needs_attention")
            result["warnings"].append("backup_missing")
            return result
        original = backup.read_bytes()
        result["original_sha256"] = sha256(original)
        try:
            reverted = revert_v1(current)
        except ValueError:
            result.update(status="patched_needs_attention")
            result["warnings"].append("cannot_reverse_v1")
            return result
        if reverted != original:
            result.update(status="patched_needs_attention")
            result["warnings"].append("does_not_match_backup")
            return result
        known = sha256(original) in KNOWN_SOURCES
        result.update(
            status="patched_v1_verified",
            guard_version=1,
            patched_sha256=digest,
            fingerprint=fingerprint(digest),
            source_basis="known_source" if known else "unreviewed_structure",
            unreviewed_source=not known,
            backup_matches_original=True,
        )
        return result

    structure = _structure(current.decode("utf-8", errors="replace"))
    result["structure_ok"] = structure["ok"]
    result["structure_problems"] = structure["problems"]
    if backup.is_file():
        result["warnings"].append("stale_backup" if backup.read_bytes() != current else "existing_backup")
    return result


def _rotate_stale_backup(source: Path, original: bytes) -> Path:
    backup = source.with_name(BACKUP_NAME)
    if not backup.exists():
        with backup.open("xb") as handle:
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        return backup
    existing = backup.read_bytes()
    if existing == original:
        return backup
    rotated = source.with_name(BACKUP_NAME + "." + sha256(existing)[:8])
    if rotated.exists():
        raise ValueError("A rotated backup with the same hash already exists; resolve it manually.")
    backup.rename(rotated)
    with backup.open("xb") as handle:
        handle.write(original)
        handle.flush()
        os.fsync(handle.fileno())
    return backup


def install(source: Path, *, allow_unreviewed: bool = False) -> dict:
    ensure_game_closed()
    status = inspect(source)
    if status["status"] == "patched_verified":
        result = inspect(source)
        result["note"] = INSTALL_NOTE
        return result
    if status["status"] == "patched_needs_attention":
        raise ValueError("Patched file needs attention: " + "; ".join(status["warnings"]))

    current = source.read_bytes()
    if status["status"] == "original_supported":
        original = current
    elif status["status"] == "patched_v1_verified":
        original = source.with_name(BACKUP_NAME).read_bytes()
    else:
        original = current

    patched = build_patch(original, allow_unreviewed=allow_unreviewed)
    _rotate_stale_backup(source, original)

    known = sha256(original) in KNOWN_SOURCES
    manifest = {
        "patch_version": VERSION,
        "tool_version": TOOL_VERSION,
        "mod_id": WORKSHOP_ID,
        "mod_version": read_mod_version(source.parent),
        "source_sha256": sha256(original),
        "patched_sha256": sha256(patched),
        "fingerprint": fingerprint(sha256(patched)),
        "source_basis": "known_source" if known else "unreviewed_structure",
        "backup_file": BACKUP_NAME,
        "requires_matching_patch_on_all_peers": True,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    atomic_write(source.with_name(MANIFEST_NAME), (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))

    ensure_game_closed()
    if source.read_bytes() != current:
        raise ValueError("The mod changed while preparing the patch; source was not overwritten.")
    atomic_write(source, patched)
    result = inspect(source)
    result["note"] = INSTALL_NOTE
    return result


def restore(source: Path) -> dict:
    ensure_game_closed()
    status = inspect(source)
    if status["status"] == "original_supported":
        result = inspect(source)
        result["note"] = RESTORE_NOTE
        return result
    if status["status"] not in ("patched_verified", "patched_v1_verified"):
        raise ValueError("Current file is not a verified stability patch; refusing to overwrite it.")

    current = source.read_bytes()
    original = source.with_name(BACKUP_NAME).read_bytes()
    if status["status"] == "patched_verified":
        expected_current = build_patch(original, allow_unreviewed=True)
        changed = current != expected_current
    else:
        changed = revert_v1(current) != original
    if changed:
        raise ValueError("The mod changed while preparing the restore; no files were changed.")

    ensure_game_closed()
    if source.read_bytes() != current:
        raise ValueError("The mod changed while preparing the restore; no files were changed.")
    atomic_write(source, original)
    manifest = source.with_name(MANIFEST_NAME)
    if manifest.is_file():
        manifest.unlink()
    result = inspect(source)
    result["note"] = RESTORE_NOTE
    return result


def verify(source: Path) -> dict:
    status = inspect(source)
    if status["status"] not in ("patched_verified", "patched_v1_verified"):
        raise ValueError("Patch is not installed; run install first.")
    return {
        "verify": "ok",
        "mod_dir": status["mod_dir"],
        "mod_version": status["mod_version"],
        "status": status["status"],
        "guard_version": status["guard_version"],
        "fingerprint": status["fingerprint"],
        "patched_sha256": status["patched_sha256"],
        "note": VERIFY_NOTE,
    }


def _game_directory(source: Path) -> Path:
    return source.parent.parent


def find_save_dir(game_directory: Path) -> Path | None:
    info = game_directory / "savedatapath.txt"
    if info.is_file():
        for line in info.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"(?i)save data path\s*:\s*(.+)$", line.strip())
            if match:
                candidate = Path(match.group(1).strip().replace("/", "\\"))
                if candidate.is_dir():
                    return candidate
    fallback = Path.home() / "Documents" / "My Games" / "Binding of Isaac Repentance+"
    return fallback if fallback.is_dir() else None


def _read_lines(path: Path, limit: int = 2_000_000) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace")[:limit].splitlines()


def _parse_sessions(save_dir: Path | None) -> list[dict]:
    if save_dir is None:
        return []
    root = save_dir / "online_logs" / "desyncs" / "sessions"
    if not root.is_dir():
        return []
    sessions = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        try:
            started = datetime.strptime(directory.name, "%m_%d_%Y__%H_%M_%S")
        except ValueError:
            started = None
        log = directory / "log.txt"
        lines = _read_lines(log)
        removals = [line for line in lines if "NetDesyncHandler::RemoveUser" in line]
        users = sorted({match for line in removals for match in re.findall(r"\b7656\d{13}\b", line)})
        sessions.append({
            "name": directory.name,
            "started": started.strftime("%Y-%m-%dT%H:%M:%S") if started else None,
            "remove_user_events": len(removals),
            "users": users,
            "has_save_snapshots": any(directory.glob("*_begin.dat")) and any(directory.glob("*_end.dat")),
            "bytes": log.stat().st_size if log.is_file() else 0,
        })
    sessions.sort(key=lambda item: item["started"] or "", reverse=True)
    return sessions


def diagnose(source: Path, save_dir: Path | None = None) -> dict:
    status = inspect(source)
    resolved = save_dir.resolve() if save_dir else find_save_dir(_game_directory(source))
    if resolved is not None and not resolved.is_dir():
        resolved = None
    result = {
        "patch": status,
        "save_dir": str(resolved) if resolved else None,
        "guard_log_lines": [],
        "main_log_remove_user_events": 0,
        "desync_sessions": {"dir": None, "total": 0, "recent": [], "before_patch": None, "after_patch": None},
        "diff_files": [],
        "notes": [
            "Session counts track NetDesyncHandler cleanup events, not proof that a specific entity caused a desync.",
        ],
    }
    if resolved is None or not resolved.is_dir():
        result["notes"].append("Save data directory not found; use --save-dir to point at it.")
        return result

    main_log = resolved / "log.txt"
    lines = _read_lines(main_log)
    result["guard_log_lines"] = [line.strip() for line in lines if "[ISAAC-STABILITY]" in line][-10:]
    result["main_log_remove_user_events"] = sum(1 for line in lines if "NetDesyncHandler::RemoveUser" in line)

    sessions = _parse_sessions(resolved)
    sessions_dir = resolved / "online_logs" / "desyncs" / "sessions"
    result["desync_sessions"] = {
        "dir": str(sessions_dir) if sessions_dir.is_dir() else None,
        "total": len(sessions),
        "recent": sessions[:10],
        "before_patch": None,
        "after_patch": None,
    }
    install_time = None
    manifest = source.with_name(MANIFEST_NAME)
    if manifest.is_file():
        try:
            created = json.loads(manifest.read_text(encoding="utf-8")).get("created_utc")
            if created:
                install_time = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(timezone.utc)
        except (OSError, ValueError, json.JSONDecodeError):
            install_time = None
    if install_time is not None:
        before = after = 0
        for session in sessions:
            if not session["started"]:
                continue
            started = datetime.fromisoformat(session["started"]).replace(tzinfo=timezone.utc)
            if started < install_time:
                before += 1
            else:
                after += 1
        result["desync_sessions"]["before_patch"] = before
        result["desync_sessions"]["after_patch"] = after

    diff_files = []
    for path in sorted(resolved.rglob("*diff*.txt"))[:20]:
        if path.is_file():
            diff_files.append({
                "path": path.relative_to(resolved).as_posix(),
                "bytes": path.stat().st_size,
            })
    result["diff_files"] = diff_files
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "install", "restore", "verify", "diagnose"])
    parser.add_argument("--mod-dir", type=Path, help="Installed Watch out, laser! directory")
    parser.add_argument("--allow-unreviewed", action="store_true",
                        help="Patch a structurally compatible but unverified mod version")
    parser.add_argument("--save-dir", type=Path, help="Save data directory for diagnose")
    args = parser.parse_args()
    try:
        source = validate_mod(args.mod_dir if args.mod_dir else discover_mod())
        if args.action == "status":
            result = inspect(source)
        elif args.action == "install":
            result = install(source, allow_unreviewed=args.allow_unreviewed)
        elif args.action == "restore":
            result = restore(source)
        elif args.action == "verify":
            result = verify(source)
        else:
            result = diagnose(source, args.save_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.action == "status":
            return 0 if result["status"] in HEALTHY_STATUSES else 1
        return 0
    except UnsupportedSource as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if exc.source_sha256:
            print(f"main.lua sha256: {exc.source_sha256}", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
