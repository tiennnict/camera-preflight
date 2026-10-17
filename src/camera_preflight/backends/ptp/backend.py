"""PTP backend on a ``Transport`` (FR-CON-02, FR-CON-03). One class, per-brand hooks.

[Unverified] Only standard PTP operations are used. Brand specific extras (Canon shutter count,
live view, remote AF point) stay unavailable until verified on hardware (V-03, V-04, V-05).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ...domain import DeviceInfo
from ..protocol import (
    Capabilities,
    CaptureOutcome,
    CaptureSettings,
    CommandFailed,
    NotSupported,
    RemoteFile,
)
from . import codec
from .session import PtpSession
from .transport import Transport

_METERING = {"evaluative": 5, "centre_weighted": 2, "spot": 4}
_BUSY_CODES = {codec.RC_DEVICE_BUSY, 0x2005}  # busy, operation not supported while focusing
CANON_SHUTTER_COUNT = 0xD1AC  # [Sourced] up to about DIGIC 5; newer bodies [Unverified] (V-05)


def _brand(manufacturer: str) -> str:
    low = manufacturer.lower()
    for name in ("canon", "nikon", "sony"):
        if name in low:
            return name.capitalize()
    return manufacturer


class PtpBackend:
    def __init__(self, transport: Transport, poll_s: float = 0.1) -> None:
        self.name = "ptp"
        self.session = PtpSession(transport)
        self._info: codec.DeviceInfoData | None = None
        self._poll = poll_s
        self._handles: set[int] = set()

    # ---- lifecycle -------------------------------------------------------------------------
    def open(self) -> None:
        self.session.open()
        self._info = self.session.device_info()
        self._handles = set(self.session.object_handles())

    def close(self) -> None:
        self.session.close()
        self.session.t.close()

    @property
    def info(self) -> codec.DeviceInfoData:
        if self._info is None:
            raise CommandFailed("session not open")
        return self._info

    def _has_prop(self, prop: int) -> bool:
        return prop in self.info.properties

    # ---- information -----------------------------------------------------------------------
    def capabilities(self) -> Capabilities:
        brand = _brand(self.info.manufacturer)
        return Capabilities(
            brand=brand,
            backend=f"ptp:{brand.lower()}",
            can_capture=codec.OP_INITIATE_CAPTURE in self.info.operations,
            can_set_exposure=self._has_prop(codec.PROP_EXPOSURE_TIME),
            can_set_iso=self._has_prop(codec.PROP_ISO),
            can_set_aperture=self._has_prop(codec.PROP_FNUMBER),
            can_set_metering=self._has_prop(codec.PROP_METERING),
            can_set_comp=self._has_prop(codec.PROP_EXPOSURE_BIAS),
            reads_battery=self._has_prop(codec.PROP_BATTERY),
            reads_storage=codec.OP_GET_STORAGE_IDS in self.info.operations,
            reads_shutter_count=brand == "Canon" and CANON_SHUTTER_COUNT in self.info.properties,
        )

    def device_info(self) -> DeviceInfo:
        i = self.info
        battery = (
            self.session.get_prop(codec.PROP_BATTERY, "<B")
            if self._has_prop(codec.PROP_BATTERY)
            else None
        )
        count = None
        if _brand(i.manufacturer) == "Canon" and CANON_SHUTTER_COUNT in i.properties:
            count = self.session.get_prop(CANON_SHUTTER_COUNT, "<I")
        storage: tuple[str, ...] = ()
        if codec.OP_GET_STORAGE_IDS in i.operations:
            storage = tuple(f"slot{n + 1}" for n, _ in enumerate(self.session.storage_ids()))
        return DeviceInfo(
            brand=_brand(i.manufacturer),
            model=i.model,
            serial=i.serial or None,
            firmware=i.device_version or None,
            battery_percent=battery,
            shutter_count=count,
            storage=storage,
        )

    # ---- settings ----------------------------------------------------------------------------
    def snapshot_settings(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        if self._has_prop(codec.PROP_ISO):
            snap["iso"] = self.session.get_prop(codec.PROP_ISO)
        if self._has_prop(codec.PROP_EXPOSURE_TIME):
            snap["exposure_raw"] = self.session.get_prop(codec.PROP_EXPOSURE_TIME, "<I")
        if self._has_prop(codec.PROP_FNUMBER):
            snap["aperture_raw"] = self.session.get_prop(codec.PROP_FNUMBER)
        if self._has_prop(codec.PROP_EXPOSURE_BIAS):
            snap["bias_raw"] = self.session.get_prop(codec.PROP_EXPOSURE_BIAS, "<h")
        if self._has_prop(codec.PROP_METERING):
            snap["metering"] = self.session.get_prop(codec.PROP_METERING)
        return snap

    def apply_settings(self, settings: CaptureSettings) -> None:
        if settings.iso is not None:
            self._set(codec.PROP_ISO, settings.iso, "<H", "ISO")
        if settings.exposure_s is not None:
            self._set(
                codec.PROP_EXPOSURE_TIME, round(settings.exposure_s * 10_000), "<I", "exposure"
            )
        if settings.aperture is not None:
            self._set(codec.PROP_FNUMBER, round(settings.aperture * 100), "<H", "aperture")
        if settings.exposure_comp_ev is not None:
            self._set(
                codec.PROP_EXPOSURE_BIAS,
                round(settings.exposure_comp_ev * 1000),
                "<h",
                "compensation",
            )
        if settings.metering is not None:
            self._set(codec.PROP_METERING, _METERING.get(settings.metering, 5), "<H", "metering")
        if settings.af_point is not None:
            raise NotSupported("remote AF point selection needs a verified vendor backend (V-03)")
        if settings.shutter_mode is not None:
            raise NotSupported("shutter mode selection needs a verified vendor backend")

    def _set(self, prop: int, value: int, fmt: str, label: str) -> None:
        if not self._has_prop(prop):
            raise NotSupported(f"{label} cannot be set over standard PTP on this body")
        self.session.set_prop(prop, value, fmt)

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        if "iso" in snapshot:
            self.session.set_prop(codec.PROP_ISO, snapshot["iso"])
        if "exposure_raw" in snapshot:
            self.session.set_prop(codec.PROP_EXPOSURE_TIME, snapshot["exposure_raw"], "<I")
        if "aperture_raw" in snapshot:
            self.session.set_prop(codec.PROP_FNUMBER, snapshot["aperture_raw"])
        if "bias_raw" in snapshot:
            self.session.set_prop(codec.PROP_EXPOSURE_BIAS, snapshot["bias_raw"], "<h")
        if "metering" in snapshot:
            self.session.set_prop(codec.PROP_METERING, snapshot["metering"])

    # ---- capture -------------------------------------------------------------------------------
    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        if codec.OP_INITIATE_CAPTURE not in self.info.operations:
            raise NotSupported("InitiateCapture is not available")
        out = CaptureOutcome(ok=True)
        for _ in range(max(settings.burst, 1)):
            r = self.session.transact(codec.OP_INITIATE_CAPTURE, (0, 0))
            if r.code != codec.RC_OK:
                # tier 1 signal (R-01): focus not acquired or shutter not released
                return CaptureOutcome(ok=False, focus_failed=r.code in _BUSY_CODES, timed_out=False)
            new = self._wait_new_object(timeout_s)
            if new is None:
                return CaptureOutcome(ok=False, focus_failed=True, timed_out=True, files=out.files)
            for h in new:
                name, size = self.session.object_name(h)
                out.files.append(RemoteFile(ref=str(h), name=name, size=size))
        return out

    def _wait_new_object(self, timeout_s: float) -> list[int] | None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            handles = set(self.session.object_handles())
            new = sorted(handles - self._handles)
            if new:
                self._handles = handles
                return new
            time.sleep(self._poll)
        return None

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / ref.name
        dest.write_bytes(self.session.get_object(int(ref.ref)))
        return dest

    def live_view_frame(self) -> Any | None:
        return None  # live view needs a vendor operation; helpers fall back to the button (V-22)


def open_usb_backend() -> PtpBackend:
    from .transport import UsbTransport

    return PtpBackend(UsbTransport())
