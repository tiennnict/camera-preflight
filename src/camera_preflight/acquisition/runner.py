"""Connected acquisition: apply settings, shoot, download, validate (FR-ACQ-05, FR-ACQ-06, FR-ACQ-09).

The runner does every camera action the backend allows. When a command fails it retries once and
then raises ``ManualFallback``, which the wizard shows as a guided manual step (D-25).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..backends.protocol import (
    BackendError,
    CameraBackend,
    CaptureSettings,
    CommandFailed,
    NotSupported,
)
from ..domain import FrameRequirement, ParameterSet
from ..io import MetadataReader, SessionFolder
from ..wizard_types import IngestFn, IngestResult

MAX_RESHOOTS = 2  # automatic re-shoots after a rejected frame (FR-GATE-03)
CAPTURE_BASE_S = 20.0  # release, AF, image processing and transfer of one RAW file [Guess]
EXPOSURE_FACTOR = 2.2  # long exposure noise reduction can double the time (Nikon Usage 10.3)


class Sink(Protocol):
    """What the runner needs from the wizard."""

    session: SessionFolder
    reader: MetadataReader | None
    params: ParameterSet

    def next_frame_id(self) -> str: ...

    def reference_serial(self) -> str | None: ...

    def register(self, outcome: Any) -> None: ...

    def record_attempt(self, point: str, focused: bool, lens: int) -> None: ...


@dataclass
class ManualFallback(Exception):
    """A command failed twice: the user does this item by hand, then the run continues."""

    requirement_key: str
    reason_code: str  # message code explaining what to do by hand
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.reason_code}: {self.detail}"


TARGET_LEVEL = 0.65  # flat frames aim for the middle of the 50 to 80% histogram range (G2)
BASE_ISO = 100
START_EXPOSURE_S = 1 / 125


def settings_for(
    req: FrameRequirement,
    index: int,
    af_point: str | None = None,
    exposure_s: float | None = None,
) -> CaptureSettings:
    explicit_iso = req.iso
    if explicit_iso is None and req.kind.value in ("flat", "chart", "dark"):
        explicit_iso = BASE_ISO  # never inherit the previous step's ISO
    return CaptureSettings(
        iso=explicit_iso,
        exposure_s=req.exposure_s if req.exposure_s is not None else exposure_s,
        aperture=req.aperture,
        metering=req.metering,
        exposure_comp_ev=req.exposure_comp_ev,
        shutter_mode=req.shutter_mode,
        af_point=af_point,
        burst=req.count if req.tag == "c1" else 1,
        defocus_first=req.kind.value == "chart",
        kind=req.kind.value,
        tag=req.tag,
        index=index,
    )


class ConnectedRunner:
    def __init__(
        self,
        backend: CameraBackend,
        sink: Sink,
        ingest: IngestFn,
        *,
        lens: int = 1,
        timeout_s: float = CAPTURE_BASE_S,
        on_progress: Callable[[str, int, int], None] | None = None,
        workdir: Path | None = None,
    ) -> None:
        self.backend = backend
        self.sink = sink
        self.ingest = ingest
        self.lens = lens
        self.timeout_s = timeout_s
        self.progress = on_progress or (lambda *_: None)
        self.workdir = workdir or Path(tempfile.mkdtemp(prefix="cp-dl-"))
        self.snapshot: dict[str, object] = {}
        self._auto_exposure: dict[str, float] = {}
        self.changed = False

    def capture_timeout(self, settings: CaptureSettings) -> float:
        """Time to wait for one capture call: the fixed part plus the exposure itself, per frame.
        A fixed 5 s used to time out every 30 s dark frame on a real body."""
        shots = max(settings.burst, 1)
        exposure = settings.exposure_s or 0.0
        return self.timeout_s * shots + EXPOSURE_FACTOR * exposure * shots

    def start(self) -> None:
        """Remember the original settings before the first change (FR-ACQ-06)."""
        if not self.snapshot:
            try:
                self.snapshot = self.backend.snapshot_settings()
            except NotSupported:
                self.snapshot = {}

    def restore(self) -> bool:
        """Put every setting the app changed back; False when the camera refuses."""
        if not self.changed:
            return True
        try:
            self.backend.restore_settings(dict(self.snapshot))
            self.changed = False
            return True
        except BackendError:
            return False

    # ---- one requirement ---------------------------------------------------------------------
    def run_requirement(
        self, req: FrameRequirement, *, manual_done: bool = False, af_point: str | None = None
    ) -> int:
        """Shoot ``req.count`` accepted frames. Returns the number accepted."""
        self.start()
        accepted = 0
        total = 1 if req.tag == "c1" else req.count
        index = 0
        if af_point is None and req.tag.startswith("af"):
            af_point = req.tag.split(":", 1)[1]
        exposure = self._exposure_for(req, af_point) if self._needs_metering(req) else None
        while accepted < total:
            settings = settings_for(req, index, af_point, exposure)
            if not manual_done:
                self._apply(req, settings)
            reshoots = 0
            while True:
                outcome = self._shoot(settings, af_point)
                if outcome is None:
                    index += 1
                    settings = settings_for(req, index, af_point, exposure)
                    if index > total + 6:
                        raise ManualFallback(req.key, "fallback.focus", af_point or "")
                    continue
                files = [self.backend.download(f, self.workdir) for f in outcome.files]
                results = [self._ingest(p, req) for p in files]
                good = [r for r in results if r.accepted]
                for r in results:
                    self.sink.register(r)
                if req.tag == "c1" or good:
                    accepted += len(good) if req.tag == "c1" else 1
                    break
                reshoots += 1
                if reshoots > MAX_RESHOOTS:
                    return accepted
            index += 1
            self.progress(req.key, min(accepted, total), total)
            if req.tag == "c1":
                break
        return accepted

    @staticmethod
    def _needs_metering(req: FrameRequirement) -> bool:
        """Flat and chart sets that fix no exposure: the app finds one that fills the histogram."""
        return (
            req.kind.value in ("flat", "chart")
            and req.exposure_s is None
            and req.tag in ("b2", "b4", "c3", "af", "af2")
        ) or (req.kind.value == "chart" and req.exposure_s is None)

    def _exposure_for(self, req: FrameRequirement, af_point: str | None) -> float:
        """Trial shots, each corrected by the measured level (the camera is in manual exposure)."""
        key = f"{req.kind.value}/{req.aperture}"
        if key in self._auto_exposure:
            return self._auto_exposure[key]
        exposure = START_EXPOSURE_S
        for _ in range(4):
            level = self._trial_level(req, exposure, af_point)
            if level is None or 0.5 <= level <= 0.8:
                break
            exposure = min(max(exposure * TARGET_LEVEL / max(level, 0.01), 1 / 8000), 30.0)
        self._auto_exposure[key] = exposure
        return exposure

    def _trial_level(
        self, req: FrameRequirement, exposure: float, af_point: str | None
    ) -> float | None:
        from ..analysis.common import binned_signal
        from ..io.raw import decode_raw

        settings = settings_for(req, 0, af_point, exposure)
        try:
            self.backend.apply_settings(settings)
            self.changed = True
            out = self.backend.capture(settings, self.capture_timeout(settings))
            if not out.ok or not out.files:
                return None
            path = self.backend.download(out.files[0], self.workdir)
            cfa = decode_raw(path)
        except (BackendError, OSError, ValueError):
            return None
        usable = max(cfa.white_level - cfa.black_level, 1.0)
        return float(binned_signal(cfa.array, cfa.pattern, cfa.black_level).mean()) / usable

    def _apply(self, req: FrameRequirement, settings: CaptureSettings) -> None:
        last: Exception | None = None
        for _ in range(2):  # one retry (FR-ACQ-09)
            try:
                self.backend.apply_settings(settings)
                self.changed = True
                return
            except NotSupported as exc:
                raise ManualFallback(req.key, "fallback.setting", str(exc)) from exc
            except CommandFailed as exc:
                last = exc
        raise ManualFallback(req.key, "fallback.setting", str(last))

    def _shoot(self, settings: CaptureSettings, af_point: str | None):  # type: ignore[no-untyped-def]
        """One capture; a focus failure is recorded as a tier 1 signal and returns None."""
        last: Exception | None = None
        for _ in range(2):
            try:
                out = self.backend.capture(settings, self.capture_timeout(settings))
            except CommandFailed as exc:
                last = exc
                continue
            if out.focus_failed or not out.ok:
                if af_point:
                    self.sink.record_attempt(af_point, False, self.lens)
                return None
            if af_point:
                self.sink.record_attempt(af_point, True, self.lens)
            return out
        raise ManualFallback("", "fallback.capture", str(last))

    def _ingest(self, path: Path, req: FrameRequirement) -> IngestResult:
        return self.ingest(
            path,
            self.sink.session,
            self.sink.reader,  # type: ignore[arg-type]
            self.sink.next_frame_id(),
            (req,),
            self.sink.params,
            self.sink.reference_serial(),
        )
