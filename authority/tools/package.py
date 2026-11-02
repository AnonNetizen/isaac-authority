"""Create a portable research bundle, excluding game assets, saves, raw logs and crash dumps."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.8.0"

def reports_directory():
    local=ROOT/"reports"
    return local if local.is_dir() else ROOT.parent/"reports"
def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def package(binary_dir, output, evidence="j460"):
    validation = json.loads((reports_directory()/"validation.json").read_text())
    for name, expected in validation["binary_sha256"].items():
        if digest(binary_dir/name) != expected: raise ValueError("Binary changed since validation: " + name)
    if digest(ROOT/"lua"/"probe.lua") != validation["lua_source_sha256"]: raise ValueError("Lua changed since validation")
    for name,expected in validation["source_sha256"].items():
        if digest(ROOT/name) != expected: raise ValueError("Source changed since validation: " + name)
    if not validation.get("host_side_isolation",{}).get("passed"):
        raise ValueError("Missing host-side isolation model validation")
    if not validation.get("native_object_bridge",{}).get("passed"):
        raise ValueError("Missing native userdata bridge validation")
    if not validation.get("native_mod_runtime",{}).get("passed"):
        raise ValueError("Missing native mod runtime validation")
    if not validation.get("resource_boundaries",{}).get("passed") or not validation.get("resource_catalog",{}).get("passed"):
        raise ValueError("Missing resource boundary/catalog validation")
    if not validation.get("packed_resource_parser",{}).get("passed"):
        raise ValueError("Missing packed resource parser validation")
    if not validation.get("runtime_suite",{}).get("diagnostic_passed"):
        raise ValueError("Missing frozen runtime-suite validation")
    native_validated=evidence=="j460"
    live=json.loads((reports_directory()/("j460-runtime-suite.json" if native_validated else "j460-personal-options.json")).read_text())
    suite=live.get("runtime_suite",{}) if native_validated else json.loads((reports_directory()/"runtime-suite-offline.json").read_text())
    if not suite.get("diagnostic_passed") or suite.get("failed")!=0 or suite.get("manifest_sha256")!=digest(ROOT/"research/runtime_suite.json"):
        raise ValueError("Missing matching runtime-suite functional evidence")
    if native_validated:
        stopped=json.loads((reports_directory()/"j460-runtime-suite-stopped.json").read_text())
        if not all(stopped.get(key) for key in ("stopped","lua_iat_restored","native_binding_hooks_disabled")):
            raise ValueError("Batch hook restoration has not been confirmed")
        if suite.get("skipped")!=0 or suite.get("shared_resource_preflight_count")!=1:
            raise ValueError("Batch functional expectations have not been verified in J460")
        if live.get("shared_resource_validation",{}).get("archives_hashed")!=len(json.loads((ROOT/"research/resource_catalog.json").read_text())["packed_environment"]):
            raise ValueError("Shared archive verification not proven")
        if live.get("binary_sha256",{}).get("isaac_authority_probe.dll") != digest(binary_dir/"isaac_authority_probe.dll"):
            raise ValueError("Live runtime evidence belongs to a different DLL")
    if not live.get("engine_api_preflight",{}).get("probe_passed") or not live.get("fixture_probe_passed"):
        raise ValueError("Missing successful resource preflight/native model evidence")
    if live.get("bootstrap_sha256") != digest(ROOT/"research"/"native_context.lua"):
        raise ValueError("Live runtime evidence belongs to a different bootstrap")
    if not live.get("personal_option_probe",{}).get("passed"):
        raise ValueError("Missing native personal option isolation evidence")
    personal=live.get("personal_mcm_eid_initializations",[])
    if {p.get("requested_language") for p in personal}!={"zh","en"} or len(personal)!=2 or not all(p.get("loaded") and p.get("actual_eid_language_selection_tested") and p.get("source_unchanged") for p in personal):
        raise ValueError("Missing unchanged Chinese/English private initialization evidence")
    expected_catalog=json.loads((ROOT/"research"/"resource_catalog.json").read_text())
    if live["engine_api_preflight"].get("resource_inventory") != expected_catalog:
        raise ValueError("Live resource evidence belongs to a different catalog")
    mcm=[mod for mod in live.get("unmodified_mod_probes",[]) if mod.get("mod")=="mod_config_menu_cn_2494192799"]
    if len(mcm)!=1 or not mcm[0].get("loaded") or not mcm[0].get("source_unchanged"):
        raise ValueError("Missing unchanged MCM private initialization evidence")
    eid=[mod for mod in live.get("unmodified_mod_probes",[]) if mod.get("mod")=="external item descriptions_836319872"]
    combined=live.get("combined_mcm_eid_private_initialization",{})
    if len(eid)!=1 or not eid[0].get("source_unchanged") or not combined.get("source_unchanged"):
        raise ValueError("Missing unchanged EID/combined private initialization evidence")
    files = {}
    for name in validation["binary_sha256"]: files["bin/"+name] = binary_dir/name
    for folder in ("native", "lua", "research", "tests", "tools", "third_party", "fixtures", "docs"):
        for path in (ROOT/folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files["source/"+path.relative_to(ROOT).as_posix()] = path
    for name in ("CMakeLists.txt", "README.md"):
        files["source/"+name] = ROOT/name
    files["README.md"] = ROOT/"README.md"
    files["run.ps1"] = ROOT/"tools"/"run.ps1"
    for path in (ROOT/"docs").glob("*.md"): files["docs/"+path.name] = path
    for path in reports_directory().glob("*.json"): files["reports/"+path.name] = path
    # The baseline restoration verifier derives the exact historical patch; bundle its own dependencies.
    for name in ("patch_watch_out_laser.py", "coop_guard.lua"):
        helper = ROOT.parent/name
        if not helper.is_file(): helper = ROOT/"tools"/"legacy"/name
        files["source/tools/legacy/"+name] = helper
    records = [{"path": name, "sha256": digest(path), "bytes": path.stat().st_size} for name,path in sorted(files.items())]
    manifest = {"version": VERSION, "native_observer_version": VERSION, "kind": "observer_and_native_host_mod_runtime_coin_model",
                "evidence_level":evidence,"current_j460_batch_validated":native_validated,
                "playable": False, "generic_mod_compatibility_passed": False, "engine_api_preflight_passed": native_validated,
                "historical_0_7_initialization_evidence_included":True,
                "mcm_private_initialization_passed":native_validated, "eid_private_initialization_passed":native_validated and eid[0].get("loaded",False),
                "combined_mcm_eid_private_initialization_passed":native_validated and combined.get("loaded",False),
                "personal_option_contexts_tested":native_validated,"eid_auto_language_getter_tested":native_validated,
                "chinese_english_private_initializations_passed":native_validated,"personal_hud_rendering_tested":False,
                "runtime_suite_diagnostic_passed":True,"presentation_gate_passed":suite.get("presentation_gate_passed",False),
                "automatic_batch_hook_restoration_passed":native_validated,"shutdown_verified":False,
                "resource_catalog_sha256":digest(ROOT/"research"/"resource_catalog.json"), "files": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        prefix = "isaac-authority-research-"+VERSION+"/"
        for name,path in sorted(files.items()): archive.write(path, prefix+name)
        archive.writestr(prefix+"bundle-manifest.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip(): raise ValueError("Archive CRC check failed")
        for record in records:
            data = archive.read(prefix+record["path"])
            if hashlib.sha256(data).hexdigest() != record["sha256"]: raise ValueError("Archive hash verification failed")
    checksum = digest(output)
    output.with_suffix(output.suffix+".sha256").write_text(checksum+"  "+output.name+"\n", encoding="ascii")
    return {"archive": str(output), "bytes": output.stat().st_size, "sha256": checksum, "files_verified": len(records), "playable": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence",choices=("local","j460"),default="j460",help="local explicitly leaves current J460 batch unverified; includes historical 0.7 evidence")
    args = parser.parse_args()
    print(json.dumps(package(args.binary_dir.resolve(), args.output.resolve(),args.evidence), indent=2))
