"""Print and check the live J460 probes that this environment cannot run.

Nothing here injects into isaac-ng, and a schema check never sets playable.
The new AuthorityLink is not attached to Steam; the dual-machine commands below
only exercise the existing JSON observer and are not a co-op acceptance pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GAME_PLACEHOLDER = "<GAME>"
PID_PLACEHOLDER = "<PID>"
OUT_PLACEHOLDER = "<FRESH_OUT>"
BINARY = r"authority\build-engine-layout\Release"
BUILD = r"authority\tools\build.ps1 -BuildDirectory build-engine-layout"
STATE = (
    "authority\\tools\\run.ps1 -Game '<GAME>' -Mode attach -ProcessId <PID> "
    "-BinaryDirectory 'authority\\build-engine-layout\\Release' "
    "-OutputDirectory '<FRESH_OUT>' -StateProbe"
)
SKIP_PACKET = (
    "authority\\tools\\run.ps1 -Game '<GAME>' -Mode attach -ProcessId <PID> "
    "-BinaryDirectory 'authority\\build-engine-layout\\Release' "
    "-OutputDirectory '<FRESH_OUT>' -SkipProbe -CandidateRva '0x554cd0' "
    "-SkipRet 4 -SkipCycles '2000,5000,2000' -PacketRva '0x2fadc0'"
)
OFFLINE = (
    "cmake -S authority -B authority/build-host-tests -DIA_HOST_TESTS=ON && "
    "cmake --build authority/build-host-tests && "
    "ctest --test-dir authority/build-host-tests --output-on-failure"
)


def _fill(command: str, game: str, pid: str, output: str) -> str:
    return command.replace(GAME_PLACEHOLDER, game).replace(PID_PLACEHOLDER, pid).replace(OUT_PLACEHOLDER, output)


def steps(game: str = GAME_PLACEHOLDER, pid: str = PID_PLACEHOLDER) -> list[dict]:
    return [
        {
            "id": "offline",
            "requires_game": False,
            "playable": False,
            "summary": "Host compiler tests for the pointer-free model and loopback link. This does not touch the game.",
            "command": OFFLINE,
        },
        {
            "id": "build",
            "requires_game": True,
            "requires_windows": True,
            "playable": False,
            "summary": "Close isaac-ng first. The build runs authority-tests.exe and authority-state-tests.exe.",
            "command": BUILD,
        },
        {
            "id": "state-probe",
            "requires_game": True,
            "requires_windows": True,
            "playable": False,
            "summary": "Restart the game, enter a seed run, focus isaac-ng, then attach. Read-only. Use a fresh output directory.",
            "command": _fill(STATE, game, pid, r"authority\runs\state-<fresh>"),
            "expect": "state-probe.json with playable false. Offsets are checked against Lua truth by the owner; this tool does not accept them.",
        },
        {
            "id": "skip-packet",
            "requires_game": True,
            "requires_windows": True,
            "playable": False,
            "summary": (
                "Exit the game so the previous DLL unloads, start a new process, enter a room with 30-60 entities, "
                "focus isaac-ng, then attach. Stay focused for the settle, the 10s capture, the 2s/5s/2s skips, and recovery. "
                "0x554cd0 must use ret 4. The packet hook is the 0x2fadc0 sub-update and is not a skip target."
            ),
            "command": _fill(SKIP_PACKET, game, pid, r"authority\runs\skip-packet-<fresh>"),
            "expect": "skip-probe.json. Do not commit the run directory.",
        },
        {
            "id": "guest-render",
            "requires_game": True,
            "playable": False,
            "implemented_in_game": False,
            "summary": (
                "No in-game guest render command exists. GuestView only plans position/room writes and is covered by "
                "authority-state-tests. Do not write entity memory from an untested hook."
            ),
            "command": None,
        },
        {
            "id": "dual-machine",
            "requires_game": True,
            "requires_two_machines": True,
            "playable": False,
            "summary": (
                "Two PCs, same isaac-ng.exe hash, one fresh output directory per machine, game restarted on each. "
                "These commands use the existing JSON/CBOR observer. AuthorityLink is not connected to Steam, "
                "so this does not apply host state and is not a 30-minute co-op pass."
            ),
            "commands": [
                "authority\\tools\\run.ps1 -Game '<GAME>' -Mode attach -ProcessId <PID_A> -Role capture -Peer <STEAM_ID_B> -Session <SHARED_8_TO_128> -Manifest <MANIFEST_JSON> -BinaryDirectory 'authority\\build-engine-layout\\Release' -OutputDirectory 'authority\\runs\\peer-a-<fresh>'",
                "authority\\tools\\run.ps1 -Game '<GAME>' -Mode attach -ProcessId <PID_B> -Role preview -Peer <STEAM_ID_A> -Session <SHARED_8_TO_128> -Manifest <MANIFEST_JSON> -BinaryDirectory 'authority\\build-engine-layout\\Release' -OutputDirectory 'authority\\runs\\peer-b-<fresh>'",
            ],
        },
    ]


def evaluate_report(document: dict) -> dict:
    """Schema check only. playable is always reported false by this tool."""
    reasons = []
    if not isinstance(document, dict):
        return {"schema_ok": False, "playable": False, "in_game_verified_by_this_tool": False, "reasons": ["report is not an object"]}
    if document.get("playable") is True:
        reasons.append("playable_must_stay_false")
    kind = "skip" if "cycles" in document or "packet_phases" in document else "state" if "room_index" in document or "entities" in document else "unknown"
    if kind == "skip":
        if document.get("packet_hook") is not True:
            reasons.append("packet_hook_missing")
        if document.get("hook_disabled") is not True:
            reasons.append("hook_not_disabled")
        if document.get("gameplay_observed") is not True or document.get("recovered") is not True:
            reasons.append("skip_did_not_recover")
        if document.get("frame_delta_during_skip_ok") is not True:
            reasons.append("frame_advanced_during_skip")
        cycles = document.get("cycles")
        if not isinstance(cycles, list) or not cycles:
            reasons.append("no_skip_cycles")
        else:
            for cycle in cycles:
                if cycle.get("player_moved_during_skip") is not False:
                    reasons.append("player_moved_during_skip")
                    break
                delta = cycle.get("frame_delta_during_skip")
                if not isinstance(delta, int) or delta > 1:
                    reasons.append("frame_delta_during_skip")
                    break
        phases = document.get("packet_phases")
        if not isinstance(phases, list):
            reasons.append("no_packet_phases")
        else:
            before = next((phase for phase in phases if phase.get("name") == "normal_before"), None)
            if before is None:
                reasons.append("normal_before_missing")
            elif not isinstance(before.get("entities_max"), int) or before["entities_max"] < 30:
                reasons.append("high_entity_sample_missing")
    elif kind == "state":
        if document.get("probe_passed") is not True:
            reasons.append("state_probe_not_passed")
    else:
        reasons.append("unrecognized_report")
    return {
        "schema_ok": not reasons,
        "playable": False,
        "in_game_verified_by_this_tool": False,
        "kind": kind,
        "reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live J460 acceptance commands. Does not mark the prototype playable.")
    parser.add_argument("--print", action="store_true", help="Print every owner step.")
    parser.add_argument("--step", choices=[step["id"] for step in steps()], help="Print one step.")
    parser.add_argument("--game", default=GAME_PLACEHOLDER)
    parser.add_argument("--pid", default=PID_PLACEHOLDER)
    parser.add_argument("--check-report", type=Path, help="Validate a state-probe.json or skip-probe.json schema.")
    args = parser.parse_args(argv)
    if args.check_report:
        document = json.loads(args.check_report.read_text(encoding="utf-8"))
        result = evaluate_report(document)
        print(json.dumps(result, indent=2))
        if "playable_must_stay_false" in result["reasons"]:
            return 1
        return 0 if result["schema_ok"] else 2
    chosen = steps(args.game, str(args.pid))
    if args.step:
        chosen = [step for step in chosen if step["id"] == args.step]
    print(json.dumps({"playable": False, "in_game_verified_by_this_tool": False, "steps": chosen}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
