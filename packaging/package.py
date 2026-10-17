"""Zip the PyInstaller output, collect third-party licence texts and write SHA256SUMS (NFR-13)."""

from __future__ import annotations

import hashlib
import shutil
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP = DIST / "camera-preflight"


def collect_licenses(target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        for f in dist.files or []:
            low = f.name.lower()
            if low.startswith(("license", "licence", "copying", "notice")):
                src = Path(str(dist.locate_file(f)))
                if src.is_file():
                    shutil.copyfile(src, target / f"{name}-{f.name}")
                    count += 1
    return count


def main() -> int:
    if not APP.exists():
        print("build output not found; run PyInstaller first", file=sys.stderr)
        return 2
    n = collect_licenses(APP / "licenses")
    version = metadata.version("camera-preflight")
    archive = shutil.make_archive(
        str(DIST / f"camera-preflight-{version}-windows-x64"), "zip", DIST, "camera-preflight"
    )
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    (DIST / "SHA256SUMS").write_text(f"{digest}  {Path(archive).name}\n", encoding="utf-8")
    size_mb = Path(archive).stat().st_size / 1e6
    print(f"{archive} ({size_mb:.0f} MB, {n} licence files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
