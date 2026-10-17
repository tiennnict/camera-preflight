"""Camera detection for the start screen (FR-CON-01, FR-CON-04).

Detection runs in the backend host so a faulty USB stack cannot crash the app. A camera is
found when the host can open a PTP session; the result also tells the user what to check.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .client import BackendClient
from .protocol import BackendError


@dataclass(frozen=True)
class DetectResult:
    found: bool
    spec: str | None = None
    camera: str = ""
    brand: str = ""
    hint_code: str = "detect.none"  # message code for what to do next


def detect(*, prefer: str | None = None, workdir: Path | None = None) -> DetectResult:
    """``prefer`` forces a backend such as ``sim`` (demo) instead of looking at USB."""
    spec = prefer or "ptp-usb"
    client: BackendClient | None = None
    try:
        client = BackendClient(spec, workdir=workdir)
        client.open()
        info = client.device_info()
        return DetectResult(True, spec, info.model or "", info.brand or "", "detect.found")
    except BackendError:
        return DetectResult(False, None, "", "", "detect.none")
    finally:
        if client is not None:
            client.close()
