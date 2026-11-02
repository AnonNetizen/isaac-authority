"""Offline Lua 5.3, installer, migration, diagnostics, and packaging checks."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".tools"))

try:
    from lupa.lua53 import LuaRuntime
    HAVE_LUA = True
except Exception:  # pragma: no cover - only without the bundled lupa
    LuaRuntime = None
    HAVE_LUA = False

import build_release
import patch_watch_out_laser as installer

TEMP_ROOT = ROOT / ".tools"
TEMP_ROOT.mkdir(exist_ok=True)
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def _find_source():
    configured = os.environ.get("ISAAC_LASER_SOURCE")
    if configured:
        path = Path(configured)
        try:
            text = path.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            return path
        if installer.MARKER_V1 in text or installer.MARKER_V2 in text:
            backup = path.with_name(installer.BACKUP_NAME)
            if backup.is_file():
                return backup
        return path
    try:
        candidate = installer.validate_mod(installer.discover_mod())
    except Exception:
        return None
    try:
        text = candidate.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    if installer.MARKER_V1 in text or installer.MARKER_V2 in text:
        backup = candidate.with_name(installer.BACKUP_NAME)
        return backup if backup.is_file() else None
    return candidate


SOURCE = _find_source()
ORIGINAL = SOURCE.read_bytes() if SOURCE else None
PATCHED = installer.build_patch(ORIGINAL, allow_unreviewed=True) if ORIGINAL else None
REQUIRES_SOURCE = unittest.skipIf(ORIGINAL is None, "Watch out, laser! source not available")


def build_v1(original: bytes) -> bytes:
    text = original.decode("utf-8")
    newline = installer._newline_for(text)
    payload = (ROOT / "legacy" / "coop_guard_v1.lua").read_text(encoding="utf-8")
    payload = payload.replace("\r\n", "\n").rstrip("\n").replace("\n", newline) + newline
    gate = "    if isaacCoopStabilityShouldSkip() then" + newline + "        return" + newline + "    end" + newline
    reset = "        isaacCoopStabilityBlocked = false" + newline
    text = text.replace(installer.RENDER_ANCHOR + newline, payload + installer.RENDER_ANCHOR + newline + gate, 1)
    text = text.replace(installer.START_ANCHOR + newline, installer.START_ANCHOR + newline + reset, 1)
    return text.encode("utf-8")


V1_PATCHED = build_v1(ORIGINAL) if ORIGINAL else None


def make_mod_directory(parent: Path, original: bytes) -> Path:
    directory = Path(tempfile.mkdtemp(prefix="mod-", dir=str(parent)))
    (directory / "metadata.xml").write_text(
        "<metadata><id>2887926286</id><version>1.1</version><name>Watch out, laser!</name></metadata>",
        encoding="utf-8",
    )
    (directory / "main.lua").write_bytes(original)
    return directory


def powershell_available() -> bool:
    return sys.platform == "win32" and POWERSHELL.is_file()


def game_running() -> bool:
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq isaac-ng.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, errors="replace", timeout=15,
        )
    except OSError:
        return True
    return "isaac-ng.exe" in result.stdout.lower()


def run_powershell(*arguments) -> subprocess.CompletedProcess:
    command = [
        str(POWERSHELL),
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(ROOT / "patch_watch_out_laser.ps1"),
    ]
    command.extend(str(item) for item in arguments)
    return subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=180)


MOCKS = r"""
REPENTANCE_PLUS = true
players = {}
indicatorCalls = 0
debugMessages = {}
Isaac = {
    GetPlayer = function(index) return players[index + 1] end,
    DebugString = function(message) table.insert(debugMessages, message) end,
    GetFrameCount = function() return 42 end,
}
function Game() return { GetNumPlayers = function() return #players end } end
function GetPtrHash(player) return player.key end
mod = { HasData = function() return false end }
function makePlayer(key, isLocal, owner, subPlayer)
    local player = { key = key }
    function player:IsSubPlayer() return subPlayer == true end
    function player:GetMainTwin() return owner or self end
    if isLocal ~= nil then
        function player:IsLocalPlayer() return isLocal end
    end
    return player
end
function makePlainPlayer(key)
    return { key = key }
end
__TS__ArrayForEach = function(items, fn)
    for _, item in ipairs(items) do fn(nil, item) end
end
local enemy = { Type = 0 }
function enemy:GetData() return {} end
function enemy:GetSprite() return {} end
function enemy:IsDead() return false end
function enemy:Exists() return true end
ActiveEnemy = { enemy }
function VanillaElseIfHell() indicatorCalls = indicatorCalls + 1 end
function debugContains(needle)
    for _, message in ipairs(debugMessages) do
        if string.find(message, needle, 1, true) then return true end
    end
    return false
end
function debugCount() return #debugMessages end
function debugText() return table.concat(debugMessages, "\n") end
"""


def guard_runtime(patched: bytes = PATCHED):
    text = patched.decode("utf-8")
    render_start = text.index(installer.RENDER_ANCHOR)
    render_end = text.index("function postUpdate(self)", render_start)
    start = text.index(installer.START_ANCHOR)
    end = text.index("    local function preGameExit(self)", start)
    runtime = LuaRuntime()
    runtime.execute(
        MOCKS
        + installer.PAYLOAD.read_text(encoding="utf-8")
        + text[render_start:render_end]
        + text[start:end]
        + "\nnewRun = postGameStarted\n"
    )
    return runtime


@unittest.skipUnless(HAVE_LUA, "lupa (Lua 5.3) is not available")
@REQUIRES_SOURCE
class GuardTests(unittest.TestCase):
    def setUp(self):
        self.lua = guard_runtime()

    def run_lua(self, body):
        self.lua.execute(body)

    def indicator_calls(self):
        return int(self.lua.globals().indicatorCalls)

    def has_debug(self, needle):
        return bool(self.lua.globals().debugContains(needle))

    def debug_count(self):
        return int(self.lua.globals().debugCount())

    def test_single_player_keeps_indicators_and_logs_once(self):
        self.run_lua("players={makePlayer(1)}; postRender()")
        self.assertEqual(self.indicator_calls(), 1)
        self.assertTrue(self.has_debug("reason=single_player"))
        self.assertTrue(self.has_debug("indicators=kept"))
        self.assertTrue(self.has_debug("v2"))
        self.assertEqual(self.debug_count(), 1)

    def test_online_blocks_both_views(self):
        for is_local, remote in ((True, False), (False, True)):
            lua = guard_runtime()
            lua.execute(
                "players={makePlayer(1,%s),makePlayer(2,%s)}; postRender()"
                % ("true" if is_local else "false", "true" if remote else "false")
            )
            self.assertEqual(int(lua.globals().indicatorCalls), 0)
            self.assertTrue(bool(lua.globals().debugContains("reason=remote_player")))
            self.assertTrue(bool(lua.globals().debugContains("indicators=disabled")))

    def test_local_coop_with_locality_api_keeps_indicators(self):
        self.run_lua("players={makePlayer(1,true),makePlayer(2,true)}; postRender()")
        self.assertEqual(self.indicator_calls(), 1)
        self.assertTrue(self.has_debug("reason=local_coop"))

    def test_vanilla_coop_without_locality_api_blocks(self):
        self.run_lua("players={makePlayer(1),makePlayer(2)}; postRender()")
        self.assertEqual(self.indicator_calls(), 0)
        self.assertTrue(self.has_debug("reason=coop_fallback"))

    def test_plain_players_block_conservatively(self):
        self.run_lua("players={makePlainPlayer(1),makePlainPlayer(2)}; postRender()")
        self.assertEqual(self.indicator_calls(), 0)
        self.assertTrue(self.has_debug("reason=coop_fallback"))

    def test_jacob_and_esau_are_single_owner(self):
        self.run_lua("local jacob=makePlayer(1); players={jacob,makePlayer(2,nil,jacob)}; postRender()")
        self.assertEqual(self.indicator_calls(), 1)
        self.assertTrue(self.has_debug("reason=single_owner"))

    def test_sub_player_does_not_trigger_coop(self):
        self.run_lua("players={makePlayer(1),makePlayer(2,nil,nil,true)}; postRender()")
        self.assertEqual(self.indicator_calls(), 1)

    def test_peer_leaving_does_not_reenable_and_does_not_spam(self):
        self.run_lua("players={makePlayer(1,true),makePlayer(2,false)}; postRender()")
        self.run_lua("players={makePlayer(1,true)}; postRender(); postRender()")
        self.assertEqual(self.indicator_calls(), 0)
        self.assertEqual(self.debug_count(), 2)

    def test_new_run_resets_state(self):
        self.run_lua("players={makePlayer(1,true),makePlayer(2,false)}; postRender()")
        self.run_lua("players={makePlayer(1)}; newRun(); postRender()")
        self.assertEqual(self.indicator_calls(), 1)
        self.assertTrue(self.has_debug("reason=single_player"))

    def test_pre_repentance_plus_keeps_indicators(self):
        self.run_lua("REPENTANCE_PLUS=false; players={makePlayer(1),makePlayer(2)}; postRender()")
        self.assertEqual(self.indicator_calls(), 1)
        self.assertTrue(self.has_debug("reason=older_game"))

    def test_detection_error_keeps_indicators_and_logs(self):
        self.run_lua("Game=function() error('not available') end; postRender()")
        self.assertEqual(self.indicator_calls(), 1)
        self.assertTrue(self.has_debug("reason=detection_unavailable"))
        self.assertTrue(self.has_debug("indicators=kept"))

    def test_four_player_online_blocks(self):
        self.run_lua(
            "players={makePlayer(1,true),makePlayer(2,false),makePlayer(3,false),makePlayer(4,false)}; postRender()"
        )
        self.assertEqual(self.indicator_calls(), 0)
        self.assertTrue(self.has_debug("players=4"))

    def test_transition_logs_blocked_reason(self):
        self.run_lua("players={makePlayer(1,true)}; postRender()")
        self.run_lua("indicatorCalls=0; players={makePlayer(1,true),makePlayer(2,false)}; postRender()")
        self.assertEqual(self.indicator_calls(), 0)
        self.assertTrue(self.has_debug("blocked reason=remote_player"))
        self.assertEqual(self.debug_count(), 2)

    def test_missing_debug_string_does_not_crash(self):
        self.run_lua("Isaac.DebugString=nil; players={makePlayer(1)}; postRender()")
        self.assertEqual(self.indicator_calls(), 1)


@REQUIRES_SOURCE
class StructureTests(unittest.TestCase):
    def test_real_layout_is_accepted(self):
        structure = installer._structure(ORIGINAL.decode("utf-8"))
        self.assertTrue(structure["ok"], structure["problems"])
        self.assertIn("LaserIndicator", structure["metrics"]["spawn_functions"])
        self.assertIn("TargetLaserIndicator", structure["metrics"]["spawn_functions"])

    def test_patched_text_compiles_in_lua53(self):
        if not HAVE_LUA:
            self.skipTest("lupa (Lua 5.3) is not available")
        LuaRuntime().compile(PATCHED.decode("utf-8"))

    def test_v1_reversal_matches_original(self):
        self.assertEqual(installer.revert_v1(V1_PATCHED), ORIGINAL)

    def test_duplicate_render_anchor_is_rejected(self):
        text = ORIGINAL.decode("utf-8").replace(
            installer.RENDER_ANCHOR + "\n",
            installer.RENDER_ANCHOR + "\n" + installer.RENDER_ANCHOR + "\n",
            1,
        )
        self.assertFalse(installer._structure(text)["ok"])

    def test_missing_registration_is_rejected(self):
        text = ORIGINAL.decode("utf-8").replace(installer.POST_UPDATE_REGISTRATION, "-- removed", 1)
        self.assertFalse(installer._structure(text)["ok"])

    def test_missing_spawns_are_rejected(self):
        text = ORIGINAL.decode("utf-8").replace("Isaac.Spawn(", "Isaac.SpawnDisabled(")
        self.assertFalse(installer._structure(text)["ok"])

    def test_renamed_spawn_function_is_rejected(self):
        text = ORIGINAL.decode("utf-8").replace("function LaserIndicator(", "function LaserIndicatorMoved(", 1)
        self.assertFalse(installer._structure(text)["ok"])

    def test_dispatcher_outside_post_render_is_rejected(self):
        text = ORIGINAL.decode("utf-8") + "\nIHateDelirium(nil)\n"
        self.assertFalse(installer._structure(text)["ok"])

    def test_known_source_hash_matches_workshop_metadata(self):
        self.assertEqual(installer.read_mod_version(SOURCE.parent), "1.1")


@REQUIRES_SOURCE
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stability-test-", dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.closed = mock.patch.object(installer, "ensure_game_closed")
        self.closed.start()
        self.addCleanup(self.closed.stop)
        self.directory = make_mod_directory(Path(self.temp.name), ORIGINAL)
        self.source = self.directory / "main.lua"

    def test_status_reports_original_supported(self):
        status = installer.inspect(self.source)
        self.assertEqual(status["status"], "original_supported")
        self.assertEqual(status["source_sha256"], installer.ORIGINAL_SHA256)
        self.assertEqual(status["fingerprint"], installer.fingerprint(installer.sha256(PATCHED)))
        self.assertTrue(status["backup_present"] is False)

    def test_install_creates_backup_manifest_and_patch(self):
        status = installer.install(self.source)
        self.assertEqual(status["status"], "patched_verified")
        self.assertEqual(status["guard_version"], 2)
        self.assertEqual(self.source.read_bytes(), PATCHED)
        self.assertEqual((self.directory / installer.BACKUP_NAME).read_bytes(), ORIGINAL)
        manifest = json.loads((self.directory / installer.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(manifest["patch_version"], 2)
        self.assertEqual(manifest["tool_version"], installer.TOOL_VERSION)
        self.assertEqual(manifest["fingerprint"], installer.fingerprint(installer.sha256(PATCHED)))
        self.assertEqual(manifest["source_basis"], "known_source")
        self.assertTrue(manifest["created_utc"].endswith("+00:00"))

    def test_install_is_idempotent(self):
        first = installer.install(self.source)
        second = installer.install(self.source)
        self.assertEqual(second["status"], "patched_verified")
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(self.source.read_bytes(), PATCHED)
        self.assertEqual((self.directory / installer.BACKUP_NAME).read_bytes(), ORIGINAL)

    def test_restore_roundtrip_keeps_backup_and_removes_manifest(self):
        installer.install(self.source)
        restored = installer.restore(self.source)
        self.assertEqual(restored["status"], "original_supported")
        self.assertEqual(self.source.read_bytes(), ORIGINAL)
        self.assertTrue((self.directory / installer.BACKUP_NAME).is_file())
        self.assertFalse((self.directory / installer.MANIFEST_NAME).exists())

    def test_unknown_version_is_refused_by_default(self):
        edited = ORIGINAL + b"\n-- local edit\n"
        self.source.write_bytes(edited)
        with self.assertRaises(installer.UnsupportedSource):
            installer.install(self.source)
        self.assertEqual(self.source.read_bytes(), edited)
        self.assertFalse((self.directory / installer.BACKUP_NAME).exists())

    def test_allow_unreviewed_installs_and_restores(self):
        edited = ORIGINAL + b"\n-- local edit\n"
        self.source.write_bytes(edited)
        result = installer.install(self.source, allow_unreviewed=True)
        self.assertEqual(result["status"], "patched_verified")
        self.assertTrue(result["unreviewed_source"])
        self.assertEqual(result["source_basis"], "unreviewed_structure")
        self.assertEqual(result["guard_version"], 2)
        self.assertEqual(self.source.read_bytes(), installer.build_patch(edited, allow_unreviewed=True))
        installer.restore(self.source)
        self.assertEqual(self.source.read_bytes(), edited)

    def test_layout_mutation_is_refused_even_when_unreviewed(self):
        broken = ORIGINAL.replace(b"function postRender(self)", b"function postRender(self, extra)", 1)
        self.source.write_bytes(broken)
        with self.assertRaises(installer.UnsupportedSource):
            installer.install(self.source, allow_unreviewed=True)
        self.assertEqual(self.source.read_bytes(), broken)

    def test_v1_state_is_detected_and_upgraded(self):
        self.source.write_bytes(V1_PATCHED)
        (self.directory / installer.BACKUP_NAME).write_bytes(ORIGINAL)
        status = installer.inspect(self.source)
        self.assertEqual(status["status"], "patched_v1_verified")
        self.assertEqual(status["guard_version"], 1)
        upgraded = installer.install(self.source)
        self.assertEqual(upgraded["status"], "patched_verified")
        self.assertEqual(upgraded["guard_version"], 2)
        self.assertEqual(self.source.read_bytes(), PATCHED)
        installer.restore(self.source)
        self.assertEqual(self.source.read_bytes(), ORIGINAL)

    def test_v1_state_can_be_restored_directly(self):
        self.source.write_bytes(V1_PATCHED)
        (self.directory / installer.BACKUP_NAME).write_bytes(ORIGINAL)
        restored = installer.restore(self.source)
        self.assertEqual(restored["status"], "original_supported")
        self.assertEqual(self.source.read_bytes(), ORIGINAL)

    def test_stale_backup_is_rotated_not_deleted(self):
        stale = ORIGINAL + b"\n-- stale backup\n"
        (self.directory / installer.BACKUP_NAME).write_bytes(stale)
        result = installer.install(self.source)
        self.assertEqual(result["status"], "patched_verified")
        rotated = list(self.directory.glob(installer.BACKUP_NAME + ".*"))
        self.assertEqual(len(rotated), 1)
        self.assertEqual(rotated[0].read_bytes(), stale)
        self.assertEqual((self.directory / installer.BACKUP_NAME).read_bytes(), ORIGINAL)

    def test_missing_backup_needs_attention(self):
        self.source.write_bytes(PATCHED)
        status = installer.inspect(self.source)
        self.assertEqual(status["status"], "patched_needs_attention")
        self.assertIn("backup_missing", status["warnings"])
        with self.assertRaises(ValueError):
            installer.install(self.source)
        with self.assertRaises(ValueError):
            installer.restore(self.source)

    def test_additional_edits_need_attention(self):
        self.source.write_bytes(PATCHED + b"\n-- extra edit\n")
        (self.directory / installer.BACKUP_NAME).write_bytes(ORIGINAL)
        status = installer.inspect(self.source)
        self.assertEqual(status["status"], "patched_needs_attention")
        self.assertIn("additional_edits", status["warnings"])
        with self.assertRaises(ValueError):
            installer.restore(self.source)

    def test_wrong_mod_is_rejected(self):
        (self.directory / "metadata.xml").write_text(
            "<metadata><id>123</id></metadata>", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            installer.validate_mod(self.directory)

    def test_verify_requires_install(self):
        with self.assertRaises(ValueError):
            installer.verify(self.source)

    def test_verify_returns_fingerprint(self):
        installer.install(self.source)
        result = installer.verify(self.source)
        self.assertEqual(result["verify"], "ok")
        self.assertEqual(result["fingerprint"], installer.fingerprint(installer.sha256(PATCHED)))
        self.assertEqual(result["guard_version"], 2)
        self.assertIn("PATCH FINGERPRINT", result["note"])

    def test_unknown_status_reports_structure(self):
        edited = ORIGINAL + b"\n-- local edit\n"
        self.source.write_bytes(edited)
        status = installer.inspect(self.source)
        self.assertEqual(status["status"], "unsupported_version")
        self.assertTrue(status["structure_ok"])


def build_save_fixture(parent: Path) -> Path:
    save = parent / "Binding of Isaac Repentance+"
    save.mkdir()
    (save / "log.txt").write_text(
        "\n".join([
            "[INFO] - boot",
            "[INFO] - [Frame: 100] [ISAAC-STABILITY] v2 frame=100 active reason=remote_player players=2 indicators=disabled",
            "[INFO] - [Frame: 456] NetDesyncHandler::RemoveUser() Removing user \"Celestite\" 76561198452579868",
        ]) + "\n",
        encoding="utf-8",
    )
    sessions = save / "online_logs" / "desyncs" / "sessions"
    first = sessions / "07_25_2026__14_07_45"
    first.mkdir(parents=True)
    (first / "log.txt").write_text(
        "[INFO] - [Frame: 456] NetDesyncHandler::RemoveUser() Removing user \"Celestite\" 76561198452579868\n"
        "[INFO] - [Frame: 457] NetDesyncHandler::RemoveUser() Removing user \"Celestite\" 76561198452579868\n",
        encoding="utf-8",
    )
    (first / "persistentgamedata1_begin.dat").write_bytes(b"begin")
    (first / "persistentgamedata1_end.dat").write_bytes(b"end")
    second = sessions / "07_25_2026__15_40_23"
    second.mkdir()
    (second / "log.txt").write_text(
        "[INFO] - [Frame: 2] NetDesyncHandler::RemoveUser() Removing user \"2290854787\" 76561199204558078\n",
        encoding="utf-8",
    )
    (save / "online_logs" / "desyncs" / "desync_diff.txt").write_text("diff\n", encoding="utf-8")
    return save


@REQUIRES_SOURCE
class DiagnoseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stability-diagnose-", dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.directory = make_mod_directory(Path(self.temp.name), ORIGINAL)
        self.source = self.directory / "main.lua"
        self.save = build_save_fixture(Path(self.temp.name))

    def test_diagnose_parses_logs_and_sessions(self):
        result = installer.diagnose(self.source, self.save)
        self.assertEqual(result["save_dir"], str(self.save.resolve()))
        self.assertEqual(len(result["guard_log_lines"]), 1)
        self.assertIn("v2", result["guard_log_lines"][0])
        self.assertEqual(result["main_log_remove_user_events"], 1)
        sessions = result["desync_sessions"]
        self.assertEqual(sessions["total"], 2)
        self.assertEqual(sessions["recent"][0]["name"], "07_25_2026__15_40_23")
        self.assertEqual(sessions["recent"][0]["remove_user_events"], 1)
        older = next(item for item in sessions["recent"] if item["name"] == "07_25_2026__14_07_45")
        self.assertEqual(older["remove_user_events"], 2)
        self.assertTrue(older["has_save_snapshots"])
        self.assertEqual(older["users"], ["76561198452579868"])
        self.assertEqual(len(result["diff_files"]), 1)
        self.assertIsNone(sessions["before_patch"])
        self.assertIsNone(sessions["after_patch"])

    def test_diagnose_handles_missing_save_directory(self):
        result = installer.diagnose(self.source, Path(self.temp.name) / "missing")
        self.assertIsNone(result["save_dir"])
        self.assertEqual(result["desync_sessions"]["total"], 0)


@unittest.skipUnless(powershell_available(), "PowerShell is not available")
@REQUIRES_SOURCE
class PowerShellParityTests(unittest.TestCase):
    def setUp(self):
        if game_running():
            self.skipTest("Isaac must be closed for the PowerShell installer")
        self.temp = tempfile.TemporaryDirectory(prefix="stability-ps-", dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.closed = mock.patch.object(installer, "ensure_game_closed")
        self.closed.start()
        self.addCleanup(self.closed.stop)
        self.directory = make_mod_directory(Path(self.temp.name), ORIGINAL)
        self.source = self.directory / "main.lua"

    def ps_json(self, *arguments):
        process = run_powershell(*arguments)
        self.assertIn(process.returncode, (0, 1), process.stderr)
        self.assertTrue(process.stdout.strip(), process.stderr)
        return process.returncode, json.loads(process.stdout)

    def assert_same_json(self, left, right, ignore=()):
        self.assertEqual(set(left) - set(ignore), set(right) - set(ignore))
        for key in left:
            if key in ignore:
                continue
            self.assertEqual(left[key], right[key], key)

    def test_status_matches_python(self):
        _, result = self.ps_json("status", "-ModDir", self.directory)
        self.assert_same_json(installer.inspect(self.source), result)

    def test_install_verify_and_restore_match_python(self):
        code, installed = self.ps_json("install", "-ModDir", self.directory)
        self.assertEqual(code, 0)
        self.assertEqual(installed["status"], "patched_verified")
        self.assertEqual(self.source.read_bytes(), PATCHED)
        manifest = json.loads((self.directory / installer.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertTrue(manifest["created_utc"].endswith("+00:00"))
        _, verified = self.ps_json("verify", "-ModDir", self.directory)
        self.assert_same_json(installer.verify(self.source), verified)
        _, restored = self.ps_json("restore", "-ModDir", self.directory)
        self.assertEqual(restored["status"], "original_supported")
        self.assertEqual(self.source.read_bytes(), ORIGINAL)
        self.assertFalse((self.directory / installer.MANIFEST_NAME).exists())

    def test_unknown_version_refused_without_flag(self):
        edited = ORIGINAL + b"\n-- local edit\n"
        self.source.write_bytes(edited)
        code, status = self.ps_json("status", "-ModDir", self.directory)
        self.assertEqual(code, 1)
        self.assertEqual(status["status"], "unsupported_version")
        self.assertTrue(status["structure_ok"])
        process = run_powershell("install", "-ModDir", self.directory)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(self.source.read_bytes(), edited)

    def test_allow_unreviewed_matches_python(self):
        edited = ORIGINAL + b"\n-- local edit\n"
        self.source.write_bytes(edited)
        code, installed = self.ps_json("install", "-ModDir", self.directory, "-AllowUnreviewed")
        self.assertEqual(code, 0)
        self.assertEqual(installed["status"], "patched_verified")
        self.assertTrue(installed["unreviewed_source"])
        self.assertEqual(self.source.read_bytes(), installer.build_patch(edited, allow_unreviewed=True))
        _, status = self.ps_json("status", "-ModDir", self.directory)
        self.assert_same_json(installer.inspect(self.source), status)

    def test_v1_state_status_and_upgrade(self):
        self.source.write_bytes(V1_PATCHED)
        (self.directory / installer.BACKUP_NAME).write_bytes(ORIGINAL)
        _, status = self.ps_json("status", "-ModDir", self.directory)
        self.assert_same_json(installer.inspect(self.source), status)
        code, installed = self.ps_json("install", "-ModDir", self.directory)
        self.assertEqual(code, 0)
        self.assertEqual(installed["status"], "patched_verified")
        self.assertEqual(self.source.read_bytes(), PATCHED)

    def test_diagnose_matches_python(self):
        save = build_save_fixture(Path(self.temp.name))
        _, result = self.ps_json("diagnose", "-ModDir", self.directory, "-SaveDir", save)
        self.assert_same_json(installer.diagnose(self.source, save), result)


@REQUIRES_SOURCE
class PackagingTests(unittest.TestCase):
    def test_build_package(self):
        with tempfile.TemporaryDirectory(prefix="stability-pack-", dir=TEMP_ROOT) as temp:
            archive = build_release.build(Path(temp))
            self.assertTrue(archive.is_file())
            sidecar = archive.with_name(archive.name + ".sha256")
            self.assertTrue(sidecar.is_file())
            digest = installer.sha256(archive.read_bytes())
            self.assertEqual(sidecar.read_text(encoding="utf-8").split()[0], digest)
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                self.assertEqual(len(names), len(build_release.FILES))
                self.assertFalse(any(name.endswith("/main.lua") for name in names))
                for name in build_release.FILES:
                    entry = build_release.PACKAGE_NAME + "/" + name
                    self.assertIn(entry, names)
                    self.assertEqual(bundle.read(entry), (ROOT / name).read_bytes())


class CompileTests(unittest.TestCase):
    def test_python_sources_compile(self):
        for relative in (
            "patch_watch_out_laser.py",
            "build_release.py",
            "test_stability_patch.py",
            "authority/tools/manifest.py",
            "authority/tools/prepare_baseline.py",
        ):
            py_compile.compile(str(ROOT / relative), doraise=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
