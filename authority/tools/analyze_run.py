"""Summarize actual research observations; never infer gameplay support from capture counts."""
import argparse
from collections import Counter
import json
from pathlib import Path

def analyze(run: Path):
    path = run / "native.jsonl"
    counts, operations, assets, errors = Counter(), Counter(), Counter(), Counter()
    frames, rooms, players = set(), set(), set()
    first = last = None
    max_entities = missing_font_assets = incomplete_colors = 0
    selftests, samples, hooks, stop_ack = [], [], [], False
    observed_payload_bytes = total_commands = 0
    with path.open(encoding="utf-8") as source:
        for line in source:
            try: item = json.loads(line)
            except json.JSONDecodeError: errors["incomplete_log_line"] += 1; continue
            first = item["time_ms"] if first is None else first
            last = item["time_ms"]
            event, data = item["event"], item.get("data", {})
            counts[event] += 1
            if "error" in event or "reject" in event: errors[event] += 1
            if event == "native_binding_probe": hooks.append(data)
            if event == "lua_observer_stopped": stop_ack = True
            if event != "observation": continue
            kind, body = data["kind"], data["body"]
            counts["kind:"+kind] += 1
            observed_payload_bytes += len(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode())
            if kind == "world":
                frames.add(data["frame"]); rooms.add((body.get("stage"), body.get("room")))
                max_entities = max(max_entities, len(body["entities"]))
                for entity in body["entities"]:
                    if "player" in entity: players.add(entity["player"].get("controller"))
            elif kind == "event": selftests.append(body)
            elif kind == "draw":
                total_commands += len(body["commands"])
                for command in body["commands"]:
                    operations[command["op"]] += 1
                    asset = command.get("asset", "(text)"); assets[asset] += 1
                    if command["op"] == "font" and not asset: missing_font_assets += 1
                    if any(k not in command.get("color", {}) for k in ("r", "g", "b", "a")): incomplete_colors += 1
                    if command["op"] in ("font", "text") and len(samples) < 8:
                        sample = {"asset": asset, "color": command.get("color", {})}
                        if "text_hex" in command:
                            sample["text_hex"] = command["text_hex"]
                        else: sample["legacy_text"] = command.get("text", "")
                        if sample not in samples: samples.append(sample)
    status = json.loads((run/"status.json").read_text()) if (run/"status.json").exists() else {}
    duration = (last-first)/1000 if first is not None else 0
    return {"source_run": run.name, "counts": counts, "draw_operations": operations, "top_assets": assets.most_common(15),
        "rooms": sorted(rooms), "controller_indices": sorted(players), "max_entities": max_entities,
        "unique_world_frames": len(frames), "logged_duration_seconds": duration, "log_bytes": path.stat().st_size,
        "observed_json_payload_bytes": observed_payload_bytes,
        "observed_json_bytes_per_second": observed_payload_bytes/duration if duration else 0,
        "network_bytes_measured": False, "operation_latency_measured": False, "game_frame_cost_measured": False,
        "capture_callback_average_us": status.get("native_capture_us", 0)/status.get("native_binding_calls", 1) if status.get("native_binding_calls") else None,
        "capture_callback_max_us": status.get("native_capture_max_us"), "status": status,
        "missing_font_asset_commands": missing_font_assets, "incomplete_color_commands": incomplete_colors,
        "selftests_and_events": selftests, "native_binding_hooks": hooks, "errors": errors, "text_samples": samples,
        "lua_stop_acknowledged": stop_ack, "two_machine_test": False, "real_30_minute_multiplayer_test": False,
        "playable_acceptance_passed": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("source_run", "rooms", "max_entities", "logged_duration_seconds", "lua_stop_acknowledged", "errors")}, ensure_ascii=False))
