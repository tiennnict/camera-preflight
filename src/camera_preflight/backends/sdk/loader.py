"""Vendor SDK loader (D-24, D-31, FR-CON-06).

No SDK file is ever part of the repository or a release. The user's folder (or the test
environment's) is searched at runtime, only inside the backend host process.

[Unverified] The library names below follow the vendors' public naming and must be confirmed
against the SDK versions the test environment downloads (V-01, V-02, V-23). The adapters expose
the SDK features each brand adds; the bindings that call them are added and tested against the
real SDK in that environment, never from memory.
"""

from __future__ import annotations

import ctypes
import os
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...domain import DeviceInfo
from ..protocol import (
    BackendError,
    Capabilities,
    CaptureOutcome,
    CaptureSettings,
    NotSupported,
    RemoteFile,
)

LIBRARY_NAMES: dict[str, tuple[str, ...]] = {
    "canon": ("EDSDK.dll", "libEDSDK.so", "EDSDK.framework"),
    # [Sourced] Remote SDK v2.1.0 ships Module/Win/BinaryFile/ControlServiceLayer.dll
    "nikon": ("ControlServiceLayer.dll",),
    # [Sourced] Camera Remote SDK v2.02.00 ships external/crsdk/Cr_Core.dll (adapters in CrAdapter/)
    "sony": ("Cr_Core.dll", "libCr_Core.so"),
}

# [Sourced] The D-SLR packages ship one MAID3 module per body family, e.g. the D7200 package
# S-SDKD7200-011BF-ALLIN has Module/Win/Binary Files/x64/Type0017.md3.
LIBRARY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "nikon": (re.compile(r"type\d{4}\.md3", re.IGNORECASE),),
}
MAX_DEPTH = 7  # vendor zips unpack to e.g. S-SDKD7200-011BF-ALLIN/Module/Win/Binary Files/x64

SDK_FEATURES: dict[str, tuple[str, ...]] = {
    "canon": ("focus_drive", "newer_bodies", "live_view"),
    "nikon": ("af_point_selection", "focus_check"),
    "sony": ("af_area", "focus_check", "focus_position", "af_response_time"),
}


class SdkUnavailable(BackendError):
    code = "backend.sdk_unavailable"


def add_dll_directories(*folders: Path) -> list[Any]:
    """Let Windows find the DLLs next to an SDK library. Returns handles to close later; empty
    elsewhere (``os.add_dll_directory`` exists on Windows only)."""
    add: Any = getattr(os, "add_dll_directory", None)
    if add is None:
        return []
    return [add(str(f.resolve())) for f in folders if f.is_dir()]  # absolute: WinError 87


@dataclass(frozen=True)
class SdkLocation:
    brand: str
    folder: Path
    library: Path


def _built_for_this_cpu(path: Path) -> bool:
    """False only for a PE file built for the other of x86 and x64 than this process.

    A folder with both builds (Canon ships ``EDSDK`` and ``EDSDK_64``) must not hand a 32-bit
    library to a 64-bit process. Anything that is not a PE file counts as a match.
    """
    try:
        with path.open("rb") as f:
            head = f.read(64)
            if head[:2] != b"MZ" or len(head) < 64:
                return True
            f.seek(struct.unpack_from("<I", head, 0x3C)[0])
            sig = f.read(6)
    except OSError:
        return True
    if len(sig) < 6 or sig[:4] != b"PE\0\0":
        return True
    machine = struct.unpack_from("<H", sig, 4)[0]
    want = 0x8664 if struct.calcsize("P") == 8 else 0x14C
    return machine == want or machine not in (0x8664, 0x14C)


def _matches(brand: str, name: str) -> bool:
    if name.lower() in {n.lower() for n in LIBRARY_NAMES.get(brand, ())}:
        return True
    return any(p.fullmatch(name) for p in LIBRARY_PATTERNS.get(brand, ()))


def find_all_sdk(brand: str, folder: Path | None) -> list[SdkLocation]:
    """Every SDK library for ``brand`` in ``folder`` (searched recursively, bounded depth) that is
    built for this process's CPU. ``folder`` may also be the library file itself. Libraries of the
    other CPU are listed last so a folder holding only those still reports them."""
    if folder is None:
        return []
    if folder.is_file():
        return [SdkLocation(brand, folder.parent, folder)] if _matches(brand, folder.name) else []
    if not folder.is_dir():
        return []
    found: list[Path] = []
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        depth = Path(root).relative_to(folder).parts
        if len(depth) > MAX_DEPTH:
            dirs[:] = []
            continue
        found += [Path(root) / f for f in sorted(files) if _matches(brand, f)]
        found += [Path(root) / d for d in dirs if _matches(brand, d)]
    native = [p for p in found if _built_for_this_cpu(p)]
    other = [p for p in found if p not in native]
    return [SdkLocation(brand, folder, p) for p in native + other]


def find_sdk(brand: str, folder: Path | None) -> SdkLocation | None:
    """The first library built for this process's CPU; failing that, the first one found."""
    found = find_all_sdk(brand, folder)
    return found[0] if found else None


def sdk_present(brand: str, folder: Path | None) -> bool:
    return find_sdk(brand, folder) is not None


class SdkAdapter:
    """Base of the per-brand adapters. Loads the native library; commands come with the bindings."""

    brand = ""

    def __init__(self, location: SdkLocation) -> None:
        self.location = location
        self.name = f"sdk:{self.brand}"
        self._lib: ctypes.CDLL | None = None

    def open(self) -> None:
        try:
            self._lib = ctypes.CDLL(str(self.location.library))
        except OSError as exc:
            raise SdkUnavailable(f"cannot load {self.location.library.name}: {exc}") from exc

    def close(self) -> None:
        self._lib = None

    def capabilities(self) -> Capabilities:
        return Capabilities(
            brand=self.brand.capitalize(), backend=self.name, sdk_features=self.features()
        )

    def device_info(self) -> DeviceInfo:
        raise self._unbound("device info")

    def snapshot_settings(self) -> dict[str, Any]:
        raise self._unbound("settings")

    def apply_settings(self, settings: CaptureSettings) -> None:
        raise self._unbound("settings")

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        raise self._unbound("settings")

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        raise self._unbound("capture")

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path:
        raise self._unbound("download")

    def live_view_frame(self) -> Any | None:
        return None

    def features(self) -> tuple[str, ...]:
        return SDK_FEATURES.get(self.brand, ())

    def _unbound(self, what: str) -> NotSupported:
        return NotSupported(f"{what}: SDK bindings are not part of this build (V-23)")


def open_sdk_backend(brand: str, folder: Path | None) -> SdkAdapter:
    location = find_sdk(brand, folder)
    if location is None:
        raise SdkUnavailable(f"{brand} SDK not found")
    return _adapter(brand, location)


def _adapter(brand: str, location: SdkLocation) -> SdkAdapter:
    if brand == "nikon":
        if location.library.suffix.lower() == ".md3":
            from .nikon_module import NikonModuleAdapter

            return NikonModuleAdapter(location)
        from .nikon import NikonAdapter

        return NikonAdapter(location)
    if brand == "sony":
        from .sony import SonyAdapter

        return SonyAdapter(location)
    if brand == "canon":
        from .canon import CanonAdapter

        return CanonAdapter(location)
    cls = type(f"{brand.capitalize()}Adapter", (SdkAdapter,), {"brand": brand})
    return cls(location)
