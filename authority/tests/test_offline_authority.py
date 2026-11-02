"""Offline checks for the pointer-free capture fixture and the live-probe checklist."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "authority" / "tools"))

from live_acceptance import SKIP_PACKET, STATE, evaluate_report, steps
from native_capture import decode_capture, encode_capture, load_json


FIXTURE = ROOT / "authority" / "fixtures" / "state" / "native_capture_room_start.json"
BLOB = ROOT / "authority" / "fixtures" / "state" / "native_capture_room_start.bin"


class NativeCaptureTests(unittest.TestCase):
    def test_fixture_roundtrip(self):
        document = load_json(FIXTURE)
        self.assertFalse(document["in_game_recording"])
        encoded = encode_capture(document)
        self.assertEqual(encoded, BLOB.read_bytes())
        decoded = decode_capture(encoded)
        self.assertEqual(decoded["frame"], 120)
        self.assertEqual(decoded["room_index"], 71)
        self.assertEqual(decoded["previous_room"], 84)
        self.assertEqual(decoded["players"][0]["x"], 320.0)
        self.assertEqual(decoded["players"][0]["y"], 380.0)
        self.assertEqual(decoded["players"][0]["size"], 10.0)
        self.assertEqual(decoded["players"][0]["pointer"], 0x3CE6A014)
        self.assertEqual(len(decoded["entities"]), 2)

    def test_trailing_bytes_rejected(self):
        with self.assertRaises(ValueError):
            decode_capture(BLOB.read_bytes() + b"\x00")


class LiveChecklistTests(unittest.TestCase):
    def test_commands_name_the_verified_entry_points(self):
        by_id = {step["id"]: step for step in steps()}
        self.assertIn("0x554cd0", by_id["skip-packet"]["command"])
        self.assertIn("-SkipRet 4", by_id["skip-packet"]["command"])
        self.assertIn("-PacketRva '0x2fadc0'", by_id["skip-packet"]["command"])
        self.assertIn("-StateProbe", by_id["state-probe"]["command"])
        self.assertIn("0x554cd0", SKIP_PACKET)
        self.assertIn("-StateProbe", STATE)
        self.assertTrue(all(step["playable"] is False for step in steps()))
        guest = next(step for step in steps() if step["id"] == "guest-render")
        self.assertIsNone(guest["command"])
        self.assertFalse(guest["implemented_in_game"])
        dual = next(step for step in steps() if step["id"] == "dual-machine")
        self.assertTrue(dual["requires_two_machines"])
        self.assertFalse(dual["playable"])

    def test_script_contains_the_same_entry_points(self):
        script = (ROOT / "authority" / "tools" / "run_live_acceptance.ps1").read_text(encoding="utf-8")
        self.assertIn("live_acceptance.py", script)
        self.assertIn("playable", script)

    def test_playable_report_is_rejected(self):
        result = evaluate_report({"playable": True, "cycles": [], "packet_phases": []})
        self.assertFalse(result["schema_ok"])
        self.assertFalse(result["playable"])
        self.assertIn("playable_must_stay_false", result["reasons"])

    def test_high_entity_skip_schema(self):
        report = {
            "playable": False,
            "packet_hook": True,
            "hook_disabled": True,
            "gameplay_observed": True,
            "recovered": True,
            "frame_delta_during_skip_ok": True,
            "cycles": [
                {"player_moved_during_skip": False, "frame_delta_during_skip": 0},
                {"player_moved_during_skip": False, "frame_delta_during_skip": 1},
            ],
            "packet_phases": [
                {"name": "normal_before", "entities_max": 42, "bytes_max": 2200, "time_average_us": 800},
                {"name": "normal_after", "entities_max": 10},
            ],
        }
        result = evaluate_report(report)
        self.assertTrue(result["schema_ok"])
        self.assertFalse(result["playable"])
        self.assertFalse(result["in_game_verified_by_this_tool"])
        low = json.loads(json.dumps(report))
        low["packet_phases"][0]["entities_max"] = 6
        self.assertIn("high_entity_sample_missing", evaluate_report(low)["reasons"])

    def test_cli_check_report_exits_nonzero_for_playable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "playable_claim.json"
            path.write_text(json.dumps({"playable": True, "cycles": [], "packet_phases": []}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "authority" / "tools" / "live_acceptance.py"), "--check-report", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("playable_must_stay_false", completed.stdout)


if __name__ == "__main__":
    unittest.main()
