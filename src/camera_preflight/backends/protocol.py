"""Backend interface (FR-CON-02) and its data types. Implementations live in the host process."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..domain import DeviceInfo


class BackendError(Exception):
    """Base class for backend failures."""

    code = "backend.error"


class CommandFailed(BackendError):
    code = "backend.command_failed"


class NotSupported(BackendError):
    code = "backend.not_supported"


class Disconnected(BackendError):
    code = "backend.disconnected"


@dataclass(frozen=True)
class Capabilities:
    brand: str = ""
    backend: str = ""  # "ptp:canon", "sdk:sony", "sim"
    can_capture: bool = False
    can_set_exposure: bool = False
    can_set_iso: bool = False
    can_set_aperture: bool = False
    can_set_metering: bool = False
    can_set_comp: bool = False
    can_set_shutter_mode: bool = False
    can_select_af_point: bool = False
    can_drive_focus: bool = False
    live_view: bool = False
    reads_shutter_count: bool = False
    reads_battery: bool = False
    reads_storage: bool = False
    can_burst: bool = False
    sdk_features: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaptureSettings:
    """What the app wants the camera to use for one shot (None = leave as it is)."""

    iso: int | None = None
    exposure_s: float | None = None
    aperture: float | None = None
    metering: str | None = None
    exposure_comp_ev: float | None = None
    shutter_mode: str | None = None  # "mechanical", "electronic"
    af_point: str | None = None
    focus_mode: str | None = None
    burst: int = 1
    defocus_first: bool = False
    kind: str = "other"  # dark, flat, chart, burst, other: lets a simulator build the scene
    tag: str = ""
    index: int = 0


@dataclass(frozen=True)
class RemoteFile:
    ref: str
    name: str
    size: int = 0


@dataclass
class CaptureOutcome:
    ok: bool
    files: list[RemoteFile] = field(default_factory=list)
    focus_failed: bool = False  # tier 1 signal (R-01)
    timed_out: bool = False


class CameraBackend(Protocol):
    name: str

    def open(self) -> None: ...

    def close(self) -> None: ...

    def capabilities(self) -> Capabilities: ...

    def device_info(self) -> DeviceInfo: ...

    def snapshot_settings(self) -> dict[str, Any]: ...

    def apply_settings(self, settings: CaptureSettings) -> None: ...

    def restore_settings(self, snapshot: dict[str, Any]) -> None: ...

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome: ...

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path: ...

    def live_view_frame(self) -> Any | None: ...
