"""Append explicitly selected packed sprite/image candidates. Contains no asset bytes."""
import argparse
import json
import hashlib
from pathlib import Path, PurePosixPath
from catalog_resources import sprite_metadata
from packed_resources import Archive, name_hash


def append(game, catalog, sprite, images, archive_order):
    game = game.resolve(strict=True)
    archives = []
    for name in archive_order:
        file = game / "resources/packed" / name
        if file.is_symlink() or file.is_junction() or not file.resolve().is_relative_to(game):
            raise ValueError("Invalid archive path")
        archives.append(Archive(file))

    def logical(name):
        name = name.replace("\\", "/").lower()
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or ":" in name or "\0" in name or not name.startswith("gfx/"):
            raise ValueError("Invalid packed logical path")
        return name

    def read(name):
        name = logical(name)
        entry = "resources/" + name
        hits = [archive for archive in archives if name_hash(entry) in archive.entries]
        if not hits:
            raise ValueError("Missing packed resource: " + name)
        # Explicit caller order; this is a candidate until canonical preflight.
        data, metadata = hits[0].read(entry)
        return name, data, metadata

    def record(kind, name, data, metadata, dependencies, **extra):
        files = {item["archive"]: {"path": "resources/packed/" + item["archive"], "sha256": item["archive_sha256"]}
                 for item in [metadata, *dependencies]}
        return {"kind": kind, "storage": "packed", "path": "resources/" + name, "engine_path": name,
                "aliases": [name], "packed_entries": [metadata, *dependencies], "files": list(files.values()), **extra}

    name, data, main = read(sprite)
    metadata, pages = sprite_metadata(data)
    dependencies = []
    for page in pages:
        image_name = (PurePosixPath(name).parent / page.replace("\\", "/")).as_posix()
        _, image, info = read(image_name)
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid packed image")
        dependencies.append(info)
    catalog["resources"].append(record("sprite", name, data, main, dependencies, **metadata))
    for selected in images:
        name, data, info = read(selected)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid packed image")
        catalog["resources"].append(record("image", name, data, info, []))
    # Freeze all archive providers, including currently non-selected overlays.
    environment = []
    for file in sorted((game / "resources/packed").glob("*.a")):
        if file.is_symlink() or file.is_junction():
            raise ValueError("Reparse archive refused")
        with file.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        environment.append({"path": file.relative_to(game).as_posix(), "sha256": digest})
    catalog["packed_environment"] = environment
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--sprite", required=True)
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--archive", action="append", required=True, help="Explicit priority, highest first")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = append(args.game, json.loads(args.catalog.read_text()), args.sprite, args.image, args.archive)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"resources": len(result["resources"]), "playable": False}))
