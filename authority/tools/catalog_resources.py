"""Freeze selected loose resources and their dependencies; does not establish native compatibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET


def sprite_metadata(data):
    root = ET.fromstring(data)
    animations = root.find("Animations")
    frames, declared = {}, {}
    for item in animations.findall("Animation"):
        name, count = item.attrib["Name"], int(item.attrib["FrameNum"])
        if name in frames or not 0 <= count <= 100000:
            raise ValueError("Duplicate/invalid animation")
        clips = [item.find("RootAnimation"), *item.findall("./LayerAnimations/LayerAnimation"),
                 *item.findall("./NullAnimations/NullAnimation")]
        timelines = []
        for clip in clips:
            if clip is None:
                continue
            delays = [int(frame.attrib.get("Delay", "1")) for frame in clip.findall("Frame")]
            if any(delay < 1 for delay in delays) or sum(delays) > 100000:
                raise ValueError("Invalid animation timeline")
            timelines.append(sum(delays))
        declared[name] = count
        frames[name] = max(1, count, *timelines)
    default = animations.attrib["DefaultAnimation"]
    if default not in frames:
        raise ValueError("Missing default animation")
    layers = [int(item.attrib["Id"]) for item in root.findall("./Content/Layers/Layer")]
    if len(layers) != len(set(layers)) or any(not 0 <= layer <= 4095 for layer in layers):
        raise ValueError("Invalid sprite layers")
    pages = [item.attrib["Path"] for item in root.findall("./Content/Spritesheets/Spritesheet")]
    return {"animations": frames, "declared_frames": declared, "default_animation": default, "layers": layers}, pages


def font_pages(data):
    if data.startswith(b"BMF\x03"):
        blocks = {}
        offset = 4
        while offset < len(data):
            if offset + 5 > len(data):
                raise ValueError("Truncated BMFont block")
            kind, size = struct.unpack_from("<BI", data, offset)
            offset += 5
            if kind in blocks or offset + size > len(data):
                raise ValueError("Invalid BMFont blocks")
            blocks[kind] = data[offset:offset + size]
            offset += size
        count = struct.unpack_from("<H", blocks[2], 8)[0]
        pages = blocks[3].rstrip(b"\0").split(b"\0")
        if not count or len(pages) != count:
            raise ValueError("Invalid BMFont page count")
        return [page.decode("utf-8") for page in pages]
    if data.lstrip().startswith(b"<"):
        return [page.attrib["file"] for page in ET.fromstring(data).findall("./pages/page")]
    return re.findall(r'^page\s+id=\d+\s+file="([^"]+)"', data.decode("utf-8"), re.MULTILINE)


def catalog(game, sprites, fonts):
    game = game.resolve(strict=True)

    def checked(path):
        original = Path(os.path.abspath(path))
        for part in [original, *original.parents]:
            if part.is_symlink() or part.is_junction():
                raise ValueError("Reparse resource refused")
            if part == game:
                break
        normalized = path.resolve(strict=True)
        if not normalized.is_relative_to(game) or not normalized.is_file():
            raise ValueError("Resource outside game root")
        for part in [normalized, *normalized.parents]:
            if part.is_symlink() or part.is_junction():
                raise ValueError("Reparse resource refused")
            if part == game:
                break
        return normalized

    records = []
    for kind, selections in (("sprite", sprites), ("font", fonts)):
        for selection in selections:
            main = checked(game / selection)
            if kind == "sprite":
                metadata, pages = sprite_metadata(main.read_bytes())
            else:
                metadata = {"animations": {}, "declared_frames": {}, "default_animation": ""}
                pages = font_pages(main.read_bytes())
            if not pages:
                raise ValueError("Resource has no image dependencies")
            dependencies = [main]
            for page in pages:
                image = checked(main.parent / page)
                if image.suffix.lower() != ".png" or not image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Unverified image format")
                dependencies.append(image)
            key = main.relative_to(game).as_posix()
            # Legacy relative loads start below a mod's resources directory.
            alias = key.split("/resources/", 1)[1] if "/resources/" in key else key.removeprefix("resources/")
            records.append({"kind": kind, "path": key, "aliases": [alias], **metadata, "files": [{"path": path.relative_to(game).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in dict.fromkeys(dependencies)]})
    return {"schema": 1, "native_compatibility_requires_live_preflight": True, "resources": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--sprite", action="append", default=[])
    parser.add_argument("--font", action="append", default=[])
    parser.add_argument("--base-catalog", type=Path, help="Append selections to an existing frozen candidate catalog")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = catalog(args.game, args.sprite, args.font)
    if args.base_catalog:
        base = json.loads(args.base_catalog.read_text(encoding="utf-8"))
        if base.get("schema") != 1 or not isinstance(base.get("resources"), list):
            raise ValueError("Invalid base catalog")
        paths = {item["path"].lower() for item in base["resources"]}
        aliases = {alias.lower() for item in base["resources"] for alias in item["aliases"]}
        for item in result["resources"]:
            if item["path"].lower() in paths or any(alias.lower() in aliases for alias in item["aliases"]):
                raise ValueError("Duplicate resource path or alias")
            paths.add(item["path"].lower())
            aliases.update(alias.lower() for alias in item["aliases"])
        base["resources"].extend(result["resources"])
        result = base
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"resources": len(result["resources"]), "dependencies": sum(len(r["files"]) for r in result["resources"])}))
