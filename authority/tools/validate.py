"""Run core, Lua capture and host-side isolation MODEL checks; do not operate Isaac."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def lua_tests(name,env=None):
    result = subprocess.run([sys.executable, str(ROOT / "tests" / name)], capture_output=True, text=True,env=env)
    if result.returncode: raise RuntimeError(result.stdout + result.stderr)
    count = re.search(r"Ran (\d+) tests", result.stderr)
    if not count: raise RuntimeError("Missing test summary for " + name)
    return int(count.group(1))

def source_files():
    paths=[ROOT/"CMakeLists.txt", ROOT/"README.md"]
    for folder in ("native","lua","research","tests","tools","fixtures","docs","third_party","trace_runtime","slice_runtime","slice2_runtime","slice3_runtime"):
        paths.extend(path for path in (ROOT/folder).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix!=".pyc")
    return sorted(paths)

def validate(binary_dir,lua_runtime):
    native = subprocess.run([str(binary_dir / "authority-tests.exe")], capture_output=True, text=True, check=True)
    capture_count = lua_tests("test_lua_capture.py")
    isolation_count = lua_tests("test_isolation.py")
    catalog_count = lua_tests("test_resource_catalog.py")
    packed_count = lua_tests("test_packed_resources.py")
    bridge=json.loads(subprocess.run([str(binary_dir/"authority-bridge-tests.exe"),str(lua_runtime)],
        capture_output=True,text=True,check=True).stdout)
    bridge["lua_runtime_sha256"]=digest(lua_runtime)
    runtime=json.loads(subprocess.run([str(binary_dir/"authority-runtime-tests.exe"),str(lua_runtime),str(ROOT)],
        capture_output=True,text=True,check=True).stdout)
    runtime["lua_runtime_sha256"]=digest(lua_runtime)
    suite_env=dict(os.environ,IA_SUITE_BINARY=str(binary_dir/"authority-suite-tests.exe"),IA_SUITE_LUA=str(lua_runtime))
    suite_count=lua_tests("test_runtime_suite.py",suite_env)
    suite=json.loads(subprocess.run([str(binary_dir/"authority-suite-tests.exe"),str(lua_runtime),str(lua_runtime.parent),str(ROOT),str(ROOT/"research/runtime_suite.json")],
        capture_output=True,text=True,encoding="utf-8",check=True).stdout)
    resources=json.loads(subprocess.run([str(binary_dir/"authority-resource-tests.exe")],capture_output=True,text=True,check=True).stdout)
    with tempfile.TemporaryDirectory(prefix="isaac-authority-check-") as temporary:
        candidate = Path(temporary)
        (candidate/"isaac-ng.exe").write_bytes(b"unsupported test image")
        unknown = subprocess.run([str(binary_dir/"isaac-authority.exe"), "--check", "--game", str(candidate)], capture_output=True, text=True, check=True)
        if json.loads(unknown.stdout)["game_supported"]: raise RuntimeError("Unsupported hash accepted")
        rejected = subprocess.run([str(binary_dir/"isaac-authority.exe"), "--attach", "0", "--game", str(candidate)], capture_output=True, text=True)
        if rejected.returncode != 1 or "Unsupported game hash" not in rejected.stderr: raise RuntimeError("Unsupported injection not refused")
        invalid = subprocess.run([str(binary_dir/"isaac-authority.exe"), "--check", "--stop"], capture_output=True, text=True)
        if invalid.returncode != 1 or "exactly one mode" not in invalid.stderr: raise RuntimeError("Ambiguous launcher modes not refused")
        for extra,expected in [(["--object-probe","--check"],"requires attach"),
            (["--object-probe","--attach","0","--peer","1"],"cannot combine"),
            (["--runtime-probe","--check"],"requires attach"),
            (["--runtime-probe","--attach","0","--peer","1"],"cannot combine"),
            (["--runtime-probe","--attach","0"],"requires --runtime-source"),
            (["--runtime-source",str(ROOT),"--check"],"requires --runtime-probe")]:
            refusal=subprocess.run([str(binary_dir/"isaac-authority.exe"),*extra,"--game",str(candidate)],capture_output=True,text=True)
            if refusal.returncode!=1 or expected not in refusal.stderr: raise RuntimeError("Unsafe object probe combination accepted")
        for extra,expected in [(["--api-probe","--check"],"requires attach"),
            (["--api-probe","--attach","0","--runtime-probe"],"cannot combine"),
            (["--api-probe","--attach","0","--peer","1"],"cannot combine")]:
            refusal=subprocess.run([str(binary_dir/"isaac-authority.exe"),*extra,"--game",str(candidate)],capture_output=True,text=True)
            if refusal.returncode!=1 or expected not in refusal.stderr: raise RuntimeError("Unsafe API probe combination accepted")
        for extra,expected in [(["--runtime-suite","missing.json","--check"],"requires attach"),
            (["--runtime-suite","missing.json","--attach","0"],"requires --runtime-source"),
            (["--runtime-suite","missing.json","--runtime-source",str(ROOT),"--attach","0","--api-probe"],"cannot combine"),
            (["--runtime-suite","missing.json","--runtime-source",str(ROOT),"--attach","0"],"file_size")]:
            refusal=subprocess.run([str(binary_dir/"isaac-authority.exe"),*extra,"--game",str(candidate)],capture_output=True,text=True)
            if refusal.returncode!=1 or expected not in refusal.stderr:raise RuntimeError("Unsafe suite combination accepted: "+refusal.stderr)
    return {"native": json.loads(native.stdout), "lua": {"passed": capture_count, "runtime": "Lua 5.3 / lupa 2.6", "mock_game_api": True},
            "host_side_isolation": {"passed": isolation_count, "runtime": "Lua 5.3 / lupa 2.6", "mock_game_api": True,
                "all_contexts_on_host": True, "generic_legacy_mod_compatibility": False},
            "native_object_bridge":bridge,
            "native_mod_runtime":runtime,
            "runtime_suite":{"passed":suite_count,"native_game_used":False,"diagnostic_passed":suite["diagnostic_passed"],
                "expected_outcomes_passed":suite["expected_outcomes_passed"],"skipped":suite["skipped"],"presentation_gate_passed":suite["presentation_gate_passed"],
                "manifest_sha256":suite["manifest_sha256"]},
            "resource_boundaries":resources,
            "resource_catalog":{"passed":catalog_count,"native_game_used":False},
            "packed_resource_parser":{"passed":packed_count,"native_game_used":False},
            "binary_sha256": {name:digest(binary_dir/name) for name in ("authority-tests.exe", "authority-bridge-tests.exe", "authority-runtime-tests.exe", "authority-resource-tests.exe", "authority-suite-tests.exe", "isaac-authority.exe", "isaac_authority_probe.dll")},
            "launcher_negative_checks_passed": 16,
            "source_sha256": {path.relative_to(ROOT).as_posix():digest(path) for path in source_files()},
            "lua_source_sha256": digest(ROOT/"lua"/"probe.lua"),
            "playable_acceptance_passed": False, "live_game_results": "See separate run reports; these checks do not operate Isaac."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lua-runtime",type=Path,required=True,help="Installed pinned x86 Lua5.3.3r.dll (not redistributed)")
    args = parser.parse_args()
    result = validate(args.binary_dir.resolve(),args.lua_runtime.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"native_passed": result["native"]["passed"], "lua_passed": result["lua"]["passed"],
        "isolation_model_passed": result["host_side_isolation"]["passed"],
        "native_bridge_passed":result["native_object_bridge"]["passed"],
        "native_mod_model_passed":result["native_mod_runtime"]["passed"], "runtime_suite_checks_passed":result["runtime_suite"]["passed"],
        "presentation_gate_passed":result["runtime_suite"]["presentation_gate_passed"],"resource_boundary_passed":result["resource_boundaries"]["passed"], "playable": False}))
