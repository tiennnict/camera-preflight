"""A simulated camera backend: lets the connected flow run with no hardware (N-09, M3 tests).

It renders every shot from a ``SynthCamera``, writes it as a DNG with a metadata sidecar, and
can fail on command to exercise retry and the manual fallback (FR-ACQ-09). The simulated user
acts through ``sim_command``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from ..backends.protocol import (
    Capabilities,
    CaptureOutcome,
    CaptureSettings,
    CommandFailed,
    NotSupported,
    RemoteFile,
)
from ..domain import DeviceInfo, FrameMeta
from .dng import write_dng
from .files import _dng_meta
from .sensor import Defects, synth_chart, synth_dark, synth_flat
from .session import SynthCamera

_SCENE_LUMA = {"normal": 120, "dark": 4, "flat": 200, "chart": 150}


class SimBackend:
    name = "sim"

    def __init__(
        self,
        camera: SynthCamera | None = None,
        workdir: Path | None = None,
        faulty: bool = False,
    ) -> None:
        self.cam = camera or SynthCamera()
        self.workdir = workdir or Path.cwd() / "sim-camera"
        self.faulty = faulty
        self.scene = "normal"
        self._pending_scene: tuple[str, int] | None = None
        self._props: dict[str, Any] = {"iso": 100, "exposure_s": 1 / 125, "aperture": 5.6}
        self._shots = 0
        self._files: dict[str, tuple[Path, int]] = {}
        self._fail: dict[str, int] = {}
        self._rng = np.random.default_rng(self.cam.seed)
        self._t0 = datetime(2026, 5, 1, 10, 0, 0)
        self._opened = False
        self.applied: list[CaptureSettings] = []
        self.restored: list[dict[str, Any]] = []

    # ---- user and fault simulation ------------------------------------------------------
    def sim_command(self, name: str, **kw: Any) -> Any:
        if name == "user_action":
            self._pending_scene = (str(kw["scene"]), int(kw.get("after_polls", 1)))
        elif name == "set_scene":
            self.scene = str(kw["scene"])
        elif name == "fail_next":
            self._fail[str(kw["method"])] = int(kw.get("count", 1))
        elif name == "disconnect":
            self._opened = False
        else:
            raise NotSupported(name)
        return True

    def _maybe_fail(self, method: str) -> None:
        if not self._opened:
            from ..backends.protocol import Disconnected

            raise Disconnected("simulated camera is unplugged")
        n = self._fail.get(method, 0)
        if n > 0:
            self._fail[method] = n - 1
            raise CommandFailed(f"simulated failure of {method}")

    # ---- CameraBackend --------------------------------------------------------------------
    def open(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def capabilities(self) -> Capabilities:
        return Capabilities(
            brand=self.cam.make,
            backend="sim",
            can_capture=True,
            can_set_exposure=True,
            can_set_iso=True,
            can_set_aperture=True,
            can_set_metering=True,
            can_set_comp=True,
            can_set_shutter_mode=True,
            can_select_af_point=True,
            can_drive_focus=True,
            live_view=True,
            reads_shutter_count=self.cam.shutter_count is not None,
            reads_battery=True,
            reads_storage=True,
            can_burst=True,
        )

    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            brand=self.cam.make,
            model=self.cam.model,
            serial=self.cam.serial,
            firmware=self.cam.firmware,
            lens=self.cam.lens,
            battery_percent=self.cam.battery_percent,
            shutter_count=None
            if self.cam.shutter_count is None
            else self.cam.shutter_count + self._shots,
            storage=("slot1",),
            af_fine_tune=0,
            usb_mode="PTP",
        )

    def snapshot_settings(self) -> dict[str, Any]:
        self._maybe_fail("snapshot_settings")
        return dict(self._props)

    def apply_settings(self, settings: CaptureSettings) -> None:
        self._maybe_fail("apply_settings")
        self.applied.append(settings)
        for k in ("iso", "exposure_s", "aperture"):
            v = getattr(settings, k)
            if v is not None:
                self._props[k] = v

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        self._maybe_fail("restore_settings")
        self.restored.append(dict(snapshot))
        self._props = dict(snapshot)

    def live_view_frame(self) -> np.ndarray | None:
        self._maybe_fail("live_view_frame")
        if self._pending_scene:
            scene, left = self._pending_scene
            left -= 1
            self._pending_scene = (scene, left) if left > 0 else None
            if left <= 0:
                self.scene = scene
        luma = _SCENE_LUMA.get(self.scene, 120)
        rng = np.random.default_rng(self._shots + luma)
        h, w = 60, 80
        if self.scene == "chart":
            tex = np.kron(np.random.default_rng(3).random((15, 20)) > 0.5, np.ones((4, 4)))
            frame = 40 + 170 * tex
        elif self.scene == "normal":
            frame = np.random.default_rng(11).normal(luma, 45, (h, w))  # an ordinary scene
        else:
            frame = np.full((h, w), float(luma))
        return np.clip(frame + rng.normal(0, 1.5, (h, w)), 0, 255).astype(np.uint8)

    # ---- capture ----------------------------------------------------------------------------
    def _render(self, s: CaptureSettings) -> tuple[np.ndarray | None, dict[str, Any]]:
        cam, spec = self.cam, self.cam.spec
        iso = s.iso or int(self._props["iso"])
        t = s.exposure_s or float(self._props["exposure_s"])
        ap = s.aperture or float(self._props["aperture"])
        rng = self._rng
        meta: dict[str, Any] = {"iso": iso, "exposure_s": t, "aperture": ap}
        if s.kind == "dark":
            return synth_dark(spec, cam.defects, iso=iso, exposure_s=t, rng=rng), meta
        if s.kind == "chart":
            point = s.af_point or "centre"
            sigma = cam.af_soft_points.get(point, 0.0)
            meta.update(af_point=point, focus_mode="AF-S")
            return synth_chart(spec, iso=iso, blur_sigma=sigma, rng=rng), meta
        if s.kind == "burst":
            return None, meta
        scene_ev = 12.0
        level = 0.6
        d = cam.defects
        tag = s.tag
        if tag.startswith("e6"):
            level = float(np.clip(0.04 * iso / 100, 0.01, 0.85))
        elif tag.startswith("e7"):
            level = float(np.clip(0.55 * (4.0 / ap) ** 2, 0.01, 0.85))
        elif tag.startswith(("e1", "e2", "e3", "e5")):
            comp = s.exposure_comp_ev or 0.0
            t = float(ap**2 / 2 ** (scene_ev - comp + np.log2(iso / 100)))
            meta.update(
                exposure_s=t, exposure_comp_ev=comp, metering_mode=s.metering or "Multi-segment"
            )
            level = float(np.clip(0.18 * 2**comp, 0.02, 0.88))
            if tag == "e3-bright" and cam.spot_follows:
                meta["exposure_s"] = t / 2**2.5  # spot on a bright area: the camera exposes less
            d = Defects()
        elif tag.startswith(("c2", "c4")):
            fast = t <= 1 / 1000
            electronic = s.shutter_mode == "electronic"
            grad = cam.electronic_curtain_gradient if electronic else cam.fast_curtain_gradient
            d = Defects(curtain_gradient=grad if fast else 0.0)
            if electronic:
                meta["shutter_type"] = "electronic"
        elif tag.startswith("c3"):
            d = Defects()
        return synth_flat(spec, d, iso=iso, exposure_s=t, aperture=ap, level=level, rng=rng), meta

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        self._maybe_fail("capture")
        if settings.kind == "chart" and (settings.af_point or "") in self.cam.af_fail_points:
            if settings.index == 0:
                return CaptureOutcome(ok=False, focus_failed=True, timed_out=True)
        out = CaptureOutcome(ok=True)
        count = max(settings.burst, 1)
        for i in range(count):
            self._shots += 1
            arr, extra = self._render(settings)
            when = self._t0 + timedelta(seconds=self._shots * 3.0)
            if settings.kind == "burst":
                when = self._t0 + timedelta(seconds=1000 + i * self.cam.burst_interval_s)
            meta = FrameMeta(
                make=self.cam.make,
                model=self.cam.model,
                serial=self.cam.serial,
                firmware=self.cam.firmware,
                lens=self.cam.lens,
                capture_time=when.replace(microsecond=0),
                sub_second=round(when.microsecond / 1e6, 3),
                has_maker_notes=True,
                shutter_count=(self.cam.shutter_count or 0) + self._shots
                if self.cam.shutter_count is not None
                else None,
                file_type="DNG",
                file_number=1000 + self._shots,
                long_exposure_nr=False,
                high_iso_nr=False,
                width=self.cam.spec.width,
                height=self.cam.spec.height,
                **extra,
            )
            name = f"IMG_{self._shots:04d}.dng"
            path = self.workdir / name
            pix = (
                arr
                if arr is not None
                else np.full(
                    (self.cam.spec.height, self.cam.spec.width),
                    self.cam.spec.black_level,
                    dtype=np.float32,
                )
            )
            write_dng(path, pix, _dng_meta(meta, self.cam), self.cam.spec.pattern)
            (self.workdir / (name + ".meta.json")).write_text(
                meta.model_dump_json(), encoding="utf-8"
            )
            self._files[name] = (path, self._shots)
            out.files.append(RemoteFile(ref=name, name=name, size=path.stat().st_size))
        return out

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path:
        self._maybe_fail("download")
        src, _ = self._files[ref.ref]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / ref.name
        dest.write_bytes(src.read_bytes())
        side = src.with_name(src.name + ".meta.json")
        dest.with_name(dest.name + ".meta.json").write_text(
            side.read_text(encoding="utf-8"), encoding="utf-8"
        )
        return dest


def sidecar_meta(path: Path) -> dict[str, Any]:
    return json.loads(path.with_name(path.name + ".meta.json").read_text(encoding="utf-8"))
