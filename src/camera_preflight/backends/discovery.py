"""Camera detection for the start screen (FR-CON-01, FR-CON-04, FR-CON-06).

Detection runs in backend host processes so a faulty USB stack or SDK cannot crash the app. The
brands on USB are read first (no camera session); then each SDK library the user has for those
brands is tried in its own host process, because two vendor libraries in one process can clash
(several Nikon modules ship DLLs with the same names). Standard PTP over libusb is tried last and
only when pyusb is installed.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .client import BackendClient
from .protocol import BackendError
from .sdk.loader import find_all_sdk
from .usb_scan import present_brands

BRAND_ORDER = ("nikon", "canon", "sony")
OPEN_TIMEOUT_S = 40.0  # an SDK that has not opened the camera by then is given up [Guess]


@dataclass(frozen=True)
class DetectResult:
    found: bool
    spec: str | None = None
    camera: str = ""
    brand: str = ""
    hint_code: str = "detect.none"  # message code for what to do next
    sdk_dir: Path | None = None  # the library the found backend uses
    seen_brand: str = ""  # a brand on USB that could not be opened


@dataclass(frozen=True)
class Candidate:
    spec: str
    brand: str
    library: Path | None = None


def candidates(
    sdk_dirs: Mapping[str, Path], present: frozenset[str] | None, ptp: bool
) -> list[Candidate]:
    """What to try, in order. ``present`` None means the USB list is unknown: try everything."""
    out: list[Candidate] = []
    brands = [b for b in BRAND_ORDER if present is None or b in present]
    for brand in brands:
        seen: set[str] = set()
        for loc in find_all_sdk(brand, sdk_dirs.get(brand)):
            # One copy of each library name is enough (Canon ships several EDSDK.dll copies);
            # every Nikon module type is tried because each serves other bodies.
            key = loc.library.name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(Candidate(f"sdk:{brand}", brand, loc.library))
    if ptp and (present is None or present):
        out.append(Candidate("ptp-usb", ""))
    return out


def _attempt(c: Candidate, workdir: Path | None) -> tuple[str, str] | None:
    client: BackendClient | None = None
    try:
        client = BackendClient(c.spec, sdk_dir=c.library, workdir=workdir)
        client.open(timeout_s=OPEN_TIMEOUT_S)
        info = client.device_info()
        return info.model or "", info.brand or c.brand.capitalize()
    except BackendError:
        return None
    finally:
        if client is not None:
            client.close()


def _pyusb_installed() -> bool:
    return importlib.util.find_spec("usb") is not None


def detect(
    *,
    prefer: str | None = None,
    workdir: Path | None = None,
    sdk_dirs: Mapping[str, Path] | None = None,
    attempt: Callable[[Candidate, Path | None], tuple[str, str] | None] = _attempt,
    scan: Callable[[], frozenset[str] | None] | None = None,
) -> DetectResult:
    """``prefer`` forces a backend such as ``sim`` (demo) instead of looking at USB."""
    if prefer:
        got = attempt(Candidate(prefer, ""), workdir)
        if got is None:
            return DetectResult(False)
        return DetectResult(True, prefer, got[0], got[1], "detect.found")
    present = (scan or present_brands)()
    if present is not None and not present:
        return DetectResult(False)
    dirs = {k.lower(): v for k, v in (sdk_dirs or {}).items()}
    tried_brands: set[str] = set()
    for c in candidates(dirs, present, _pyusb_installed()):
        tried_brands.add(c.brand)
        got = attempt(c, workdir)
        if got is not None:
            return DetectResult(True, c.spec, got[0], got[1], "detect.found", c.library)
    seen = sorted(present or ())
    if seen:
        brand = seen[0]
        hint = "detect.failed" if brand in tried_brands else "detect.no_sdk"
        return DetectResult(False, hint_code=hint, seen_brand=brand)
    return DetectResult(False)
