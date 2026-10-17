"""Synthetic camera and session: frames for every check, with injectable faults.

Used by the tests, the demo session (N-09) and the self-test. Frames are built in memory and
keyed by requirement key, exactly as the wizard hands them to the checks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from ..checks import AfAttempt, FrameSet
from ..checks.group_b import B1_ISOS, B1_LONG_S, B1_SHORT_S
from ..checks.group_c import C1_REQ, C2_FAST, C2_REF, C3_REQ, C4_FAST
from ..checks.group_d import GENERIC_POINTS, af_requirements
from ..checks.group_e import E1_REQ, E2_REQ, E3_REQ, E5_REQ, E6_REQ, E7_REQ
from ..domain import CfaData, Frame, FrameKind, FrameMeta, FrameRequirement, Provenance
from .sensor import Defects, SensorSpec, synth_chart, synth_dark, synth_flat


@dataclass
class SynthCamera:
    """A pretend body. Every fault is off by default (a healthy camera)."""

    spec: SensorSpec = field(default_factory=SensorSpec)
    defects: Defects = field(default_factory=Defects)
    make: str = "SynthCam"
    model: str = "SC-1"
    serial: str = "SN0001"
    firmware: str = "1.0.0"
    lens: str = "Synth 50mm f/1.8"
    shutter_count: int | None = 12345
    battery_percent: int = 80
    burst_interval_s: float = 0.1
    burst_stall_after: int | None = None  # frame index after which the burst stalls
    fast_curtain_gradient: float = 0.0  # applied at 1/1000 and faster, mechanical shutter only
    electronic_curtain_gradient: float = 0.0
    af_soft_points: dict[str, float] = field(default_factory=dict)  # point -> blur sigma
    af_fail_points: frozenset[str] = frozenset()
    comp_nonlinear_ev: float = 0.0  # extra error at the +1 EV compensation frame
    iso_jump_ev: float = 0.0  # extra error at ISO 800
    spot_follows: bool = True
    exposure_jitter_ev: float = 0.05
    seed: int = 1

    def device_meta(self) -> FrameMeta:
        return FrameMeta(
            make=self.make,
            model=self.model,
            serial=self.serial,
            firmware=self.firmware,
            lens=self.lens,
            shutter_count=self.shutter_count,
            has_maker_notes=True,
            file_type="DNG",
            width=self.spec.width,
            height=self.spec.height,
        )


def _frame(
    cam: SynthCamera,
    key: str,
    i: int,
    arr: np.ndarray | None,
    *,
    kind: FrameKind,
    t0: datetime,
    offset_s: float = 0.0,
    **meta: object,
) -> Frame:
    capture = t0 + timedelta(seconds=offset_s)
    m = FrameMeta(
        make=cam.make,
        model=cam.model,
        serial=cam.serial,
        firmware=cam.firmware,
        lens=cam.lens,
        capture_time=capture.replace(microsecond=0),
        sub_second=round(capture.microsecond / 1e6, 3),
        has_maker_notes=True,
        shutter_count=cam.shutter_count,
        file_type="DNG",
        file_number=1000 + int(offset_s),
        long_exposure_nr=False,
        high_iso_nr=False,
        width=cam.spec.width,
        height=cam.spec.height,
        **meta,  # type: ignore[arg-type]
    )
    cfa = (
        CfaData(arr, cam.spec.pattern, cam.spec.black_level, cam.spec.white_level)
        if arr is not None
        else None
    )
    digest = hashlib.sha256(f"{key}/{i}/{cam.seed}".encode()).hexdigest()
    return Frame(
        id=f"{key}#{i}",
        sha256=digest,
        source=Path(f"{key.replace('/', '_')}-{i}.dng"),
        meta=m,
        kind=kind,
        cfa=cfa,
        provenance=Provenance(
            serial=cam.serial, capture_time=m.capture_time, file_number=m.file_number
        ),
    )


def build_frames(cam: SynthCamera, t0: datetime | None = None) -> FrameSet:
    """Frames for every requirement of every check, keyed as the checks expect."""
    t0 = t0 or datetime(2026, 5, 1, 10, 0, 0)
    rng = np.random.default_rng(cam.seed)
    spec, d = cam.spec, cam.defects
    out: dict[str, list[Frame]] = {}
    counter = 0

    def add(req: FrameRequirement, i: int, arr: np.ndarray | None, **meta: object) -> None:
        nonlocal counter
        counter += 1
        out.setdefault(req.key, []).append(
            _frame(cam, req.key, i, arr, kind=req.kind, t0=t0, offset_s=counter * 3.0, **meta)
        )

    # B1 dark frames
    for iso in B1_ISOS:
        for t in (B1_SHORT_S, B1_LONG_S):
            req = FrameRequirement(FrameKind.DARK, 3, iso=iso, exposure_s=t, tag="b1")
            for i in range(3):
                arr = synth_dark(spec, d, iso=iso, exposure_s=t, rng=rng)
                add(req, i, arr, iso=iso, exposure_s=t, aperture=None)

    # B2 and B4 flats, with the target shifted a little between frames
    for tag, ap in (("b2", 8.0), ("b4", 22.0)):
        req = FrameRequirement(FrameKind.FLAT, 3, aperture=ap, tag=tag)
        for i in range(3):
            arr = synth_flat(
                spec,
                d,
                iso=100,
                exposure_s=1 / 125,
                aperture=ap,
                level=0.6,
                rng=rng,
                shift=(i * 2.0, i * 3.0),
            )
            add(req, i, arr, iso=100, exposure_s=1 / 125, aperture=ap)

    # C1 burst: timestamps only
    for i in range(10):
        gap = cam.burst_interval_s
        off = i * gap
        if cam.burst_stall_after is not None and i > cam.burst_stall_after:
            off += gap * 6
        counter += 1
        f = _frame(
            cam,
            C1_REQ[0].key,
            i,
            None,
            kind=FrameKind.BURST,
            t0=t0,
            offset_s=1000 + off,
            iso=100,
            exposure_s=1 / 500,
            aperture=5.6,
        )
        out.setdefault(C1_REQ[0].key, []).append(f)

    # C2 curtain
    for req in (C2_REF, *C2_FAST):
        grad = cam.fast_curtain_gradient if (req.exposure_s or 1) <= 1 / 1000 else 0.0
        dd = Defects(curtain_gradient=grad)
        for i in range(3):
            arr = synth_flat(
                spec, dd, iso=100, exposure_s=req.exposure_s or 0.01, aperture=8, level=0.6, rng=rng
            )
            add(req, i, arr, iso=100, exposure_s=req.exposure_s, aperture=8.0)
    for req in C4_FAST:
        dd = Defects(curtain_gradient=cam.electronic_curtain_gradient)
        for i in range(3):
            arr = synth_flat(
                spec, dd, iso=100, exposure_s=req.exposure_s or 0.01, aperture=8, level=0.6, rng=rng
            )
            add(
                req,
                i,
                arr,
                iso=100,
                exposure_s=req.exposure_s,
                aperture=8.0,
                shutter_type="electronic",
            )

    # C3 repeatability
    for i in range(10):
        arr = synth_flat(
            spec, Defects(), iso=100, exposure_s=1 / 250, aperture=2.8, level=0.6, rng=rng
        )
        add(C3_REQ[0], i, arr, iso=100, exposure_s=1 / 250, aperture=2.8)

    # E series: the camera picks the exposure for a scene of fixed luminance (EV 12 at ISO 100)
    scene_ev = 12.0

    def auto_exposure(ap: float, iso: int, extra_ev: float = 0.0) -> float:
        return float(ap**2 / 2 ** (scene_ev + extra_ev + np.log2(iso / 100)))

    def level_for(ev_error: float) -> float:
        return float(np.clip(0.18 * 2 ** (ev_error), 0.02, 0.88))

    for i in range(5):
        jit = float(rng.normal(0, cam.exposure_jitter_ev))
        t = auto_exposure(5.6, 200, jit)
        arr = synth_flat(
            spec, Defects(), iso=200, exposure_s=t, aperture=5.6, level=level_for(0.0), rng=rng
        )
        add(E1_REQ[0], i, arr, iso=200, exposure_s=t, aperture=5.6, metering_mode="Multi-segment")
    for req in E2_REQ:
        t = auto_exposure(5.6, 200)
        arr = synth_flat(
            spec, Defects(), iso=200, exposure_s=t, aperture=5.6, level=level_for(0.0), rng=rng
        )
        add(req, 0, arr, iso=200, exposure_s=t, aperture=5.6, metering_mode=req.metering)
    for req in E3_REQ:
        bright = req.tag == "e3-bright"
        delta = 2.5 if (bright and cam.spot_follows) else 0.0
        t = auto_exposure(5.6, 200, -delta)
        arr = synth_flat(
            spec, Defects(), iso=200, exposure_s=t, aperture=5.6, level=level_for(0.0), rng=rng
        )
        add(req, 0, arr, iso=200, exposure_s=t, aperture=5.6, metering_mode="Spot")
    for req in E5_REQ:
        comp = req.exposure_comp_ev or 0.0
        err = cam.comp_nonlinear_ev if comp == 1.0 else 0.0
        t = auto_exposure(5.6, 200, -comp)
        arr = synth_flat(
            spec,
            Defects(),
            iso=200,
            exposure_s=t,
            aperture=5.6,
            level=level_for(comp + err),
            rng=rng,
        )
        add(req, 0, arr, iso=200, exposure_s=t, aperture=5.6, exposure_comp_ev=comp)
    for req in E6_REQ:
        iso = req.iso or 100
        err = cam.iso_jump_ev if iso == 800 else 0.0
        lvl = float(np.clip(0.04 * (iso / 100) * 2**err, 0.01, 0.85))
        arr = synth_flat(
            spec, Defects(), iso=iso, exposure_s=1 / 250, aperture=8.0, level=lvl, rng=rng
        )
        add(req, 0, arr, iso=iso, exposure_s=1 / 250, aperture=8.0)
    for req in E7_REQ:
        ap = req.aperture or 8.0
        lvl = float(np.clip(0.55 * (4.0 / ap) ** 2, 0.01, 0.85))
        arr = synth_flat(
            spec, Defects(), iso=100, exposure_s=1 / 250, aperture=ap, level=lvl, rng=rng
        )
        add(req, 0, arr, iso=100, exposure_s=1 / 250, aperture=ap)

    # D autofocus chart frames, three attempts per point
    for req, pt in zip(af_requirements(GENERIC_POINTS, 3), GENERIC_POINTS, strict=True):
        sigma = cam.af_soft_points.get(pt.name, 0.0)
        for i in range(3):
            arr = synth_chart(spec, iso=100, blur_sigma=sigma, rng=rng)
            add(
                req,
                i,
                arr,
                iso=100,
                exposure_s=1 / 250,
                aperture=5.6,
                af_point=pt.name,
                focus_mode="AF-S",
            )
    return out


def af_attempts(cam: SynthCamera) -> dict[str, list[AfAttempt]]:
    result: dict[str, list[AfAttempt]] = {}
    for pt in GENERIC_POINTS:
        failing = pt.name in cam.af_fail_points
        result[pt.name] = [
            AfAttempt(focused=not failing or i == 0, source="tethered") for i in range(3)
        ]
    return result
