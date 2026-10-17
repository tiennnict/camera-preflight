"""Fetch the pinned ExifTool into packaging/exiftool/bundle at build time (D-42).

The archive is never committed. The download is checked against the pinned SHA-256; the build
stops if the pin is unset or the hash differs.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    pin = json.loads((HERE / "VERSION.json").read_text(encoding="utf-8"))
    if any(pin.get(k) in (None, "", "UNSET") for k in ("version", "url", "sha256")):
        print("ExifTool pin is unset: edit packaging/exiftool/VERSION.json (V-16)", file=sys.stderr)
        return 2
    target = HERE / "bundle"
    archive = HERE / "exiftool.zip"
    request = urllib.request.Request(pin["url"], headers={"User-Agent": "camera-preflight-build"})
    with urllib.request.urlopen(request, timeout=120) as resp:
        archive.write_bytes(resp.read())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest.lower() != str(pin["sha256"]).lower():
        archive.unlink()
        print(f"ExifTool hash mismatch: {digest}", file=sys.stderr)
        return 3
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(target)
    # The Windows archive ships "exiftool(-k).exe"; the app expects exiftool/exiftool.exe.
    for exe in target.rglob("exiftool(-k).exe"):
        exe.rename(exe.with_name("exiftool.exe"))
    archive.unlink()
    print(f"ExifTool {pin['version']} ready in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
