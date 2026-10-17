"""Zip the PyInstaller output, collect third-party licence texts and write SHA256SUMS (NFR-13).

``--with-sdk`` is for the maintainer's local build of the official binary release (D-47). It copies
the runtime files of each vendor SDK found under ``sdk/<brand>/`` next to the executable. CI never
uses it, and the SDK files are never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP = DIST / "camera-preflight"
BRANDS = ("canon", "nikon", "sony")
DOC_NAMES = ("readme", "license", "licence", "notice", "copying", "eula", "terms")


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


def bundle_sdk(source: Path, target: Path) -> list[str]:
    """Copy the folder holding each SDK's library, plus readme and licence files found above it.

    Returns one line per brand for the manifest. Brands without an SDK are skipped."""
    sys.path.insert(0, str(ROOT / "src"))
    from camera_preflight.backends.sdk.loader import find_sdk

    manifest: list[str] = []
    for brand in BRANDS:
        folder = source / brand
        loc = find_sdk(brand, folder)
        if loc is None:
            print(f"sdk: {brand}: not found in {folder}, skipped")
            continue
        dest = target / brand
        shutil.copytree(loc.library.parent, dest, dirs_exist_ok=True)
        # Vendor readme and licence texts stay with the files they cover.
        docs = dest / "vendor-docs"
        for parent in list(loc.library.parents)[:5]:
            if parent == folder.parent:
                break
            for f in parent.iterdir():
                if f.is_file() and f.suffix.lower() in {".txt", ".md", ".pdf"}:
                    if f.stem.lower().startswith(DOC_NAMES):
                        docs.mkdir(exist_ok=True)
                        shutil.copyfile(f, docs / f.name)
            if parent == folder:
                break
        files = [p for p in dest.rglob("*") if p.is_file()]
        for p in sorted(files):
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            manifest.append(f"{digest}  {brand}/{p.relative_to(dest).as_posix()}")
        print(f"sdk: {brand}: {len(files)} files from {loc.library.parent}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--with-sdk",
        nargs="?",
        const=str(ROOT / "sdk"),
        metavar="DIR",
        help="bundle vendor SDK runtime files from DIR (default: ./sdk); local builds only (D-47)",
    )
    ap.add_argument(
        "--accept-vendor-terms",
        action="store_true",
        help="confirm the vendors' redistribution terms allow shipping the bundled files",
    )
    args = ap.parse_args(argv)
    if not APP.exists():
        print("build output not found; run PyInstaller first", file=sys.stderr)
        return 2
    suffix = ""
    if not args.with_sdk and (APP / "sdk").exists():
        shutil.rmtree(APP / "sdk")  # a plain build never carries SDK files left by an earlier one
    if args.with_sdk:
        if os.environ.get("CI"):
            print(
                "--with-sdk is refused in CI: SDK files never go through CI (D-47)", file=sys.stderr
            )
            return 2
        if not args.accept_vendor_terms:
            print(
                "--with-sdk needs --accept-vendor-terms: the maintainer confirms the vendors allow"
                " redistribution (V-01)",
                file=sys.stderr,
            )
            return 2
        sdk_target = APP / "sdk"
        if sdk_target.exists():
            shutil.rmtree(sdk_target)
        manifest = bundle_sdk(Path(args.with_sdk), sdk_target)
        if not manifest:
            print("no SDK found; nothing bundled", file=sys.stderr)
            return 2
        (sdk_target / "BUNDLED.txt").write_text(
            "Vendor SDK runtime files bundled in this build (SHA-256, path).\n"
            "Each SDK stays under its vendor's own terms; see the vendor-docs folders.\n\n"
            + "\n".join(manifest)
            + "\n",
            encoding="utf-8",
        )
        suffix = "-with-sdk"
    n = collect_licenses(APP / "licenses")
    version = metadata.version("camera-preflight")
    archive = shutil.make_archive(
        str(DIST / f"camera-preflight-{version}-windows-x64{suffix}"),
        "zip",
        DIST,
        "camera-preflight",
    )
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    sums = DIST / f"SHA256SUMS{suffix}"
    sums.write_text(f"{digest}  {Path(archive).name}\n", encoding="utf-8")
    size_mb = Path(archive).stat().st_size / 1e6
    print(f"{archive} ({size_mb:.0f} MB, {n} licence files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
