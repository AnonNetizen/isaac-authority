"""Copy a stopped native runtime diagnostic into a distributable evidence report."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BINARIES = ("authority-tests.exe", "authority-bridge-tests.exe", "authority-runtime-tests.exe",
            "authority-resource-tests.exe", "authority-suite-tests.exe", "isaac-authority.exe", "isaac_authority_probe.dll")

def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def summarize(run, binary_dir, output):
    live = json.loads((run / "mod-runtime.json").read_text(encoding="utf-8"))
    stopped = json.loads((run / "stopped.json").read_text(encoding="utf-8"))
    if not all(stopped.get(k) for k in ("stopped", "lua_iat_restored", "native_binding_hooks_disabled")):
        raise ValueError("Diagnostic has not confirmed hook restoration")
    live["binary_sha256"] = {name: digest(binary_dir / name) for name in BINARIES}
    live["run_directory_name"] = run.name
    live["report_collected_utc"] = datetime.now(timezone.utc).isoformat()
    live["shutdown_verified"] = False
    live["mcm_personal_configuration_and_rendering_tested"] = False
    live["date_default_clock"] = "coin model time_ms / 1000, not the current calendar"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve past evidence; every diagnostic needs a distinct output name.
    with output.open("x", encoding="utf-8") as target:
        json.dump(live, target, indent=2)
    with output.with_name(output.stem + "-stopped.json").open("x", encoding="utf-8") as target:
        json.dump(stopped, target, indent=2)
    return {"report": str(output), "preflight_passed": live.get("engine_api_preflight", {}).get("probe_passed"),
            "model_passed": live.get("fixture_probe_passed"), "playable": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--binary-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.run.resolve(), args.binary_dir.resolve(), args.output.resolve())))
