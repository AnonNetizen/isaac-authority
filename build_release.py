"""Build a small patch-only package, without redistributing the third-party mod."""

from __future__ import annotations

from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifacts"
PACKAGE_NAME = "ISAAC-Coop-Stability-v2"
VERSION = "2.0.0"
FILES = [
    "coop_guard.lua",
    "patch_watch_out_laser.ps1",
    "patch_watch_out_laser.py",
    "install.cmd",
    "status.cmd",
    "restore.cmd",
    "verify.cmd",
    "diagnose.cmd",
    "README.md",
    "CHANGELOG.md",
    "使用说明.txt",
]


def build(output: Path = OUTPUT) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / (PACKAGE_NAME + ".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(path)
            archive.write(path, PACKAGE_NAME + "/" + name)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity check failed")
        if len(archive.infolist()) != len(FILES):
            raise ValueError("Unexpected archive entry count")
        for name in FILES:
            if archive.read(PACKAGE_NAME + "/" + name) != (ROOT / name).read_bytes():
                raise ValueError(f"Archive content mismatch: {name}")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (output / (PACKAGE_NAME + ".zip.sha256")).write_text(
        f"{digest}  {PACKAGE_NAME}.zip\n", encoding="utf-8"
    )
    return archive_path


if __name__ == "__main__":
    print(build())
