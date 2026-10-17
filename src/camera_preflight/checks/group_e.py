"""Group E: metering and exposure (TEST-CATALOGUE section 7). Consistency and linearity only."""

from __future__ import annotations

import numpy as np

from ..analysis.common import binned_signal
from ..analysis.metering import exposure_value, linear_fit, log2_levels, spread
from ..domain import (
    CheckResult,
    CheckSpec,
    Confidence,
    Frame,
    FrameKind,
    FrameRequirement,
    Level,
    Severity,
)
from .base import (
    INSUFFICIENT,
    Check,
    CheckContext,
    FrameSet,
    FunctionCheck,
    finding,
    make_result,
    msg,
    not_tested,
)
from .specs import SEMI_OR_UPLOAD, make_spec

E1_REQ = (FrameRequirement(FrameKind.OTHER, 5, tag="e1"),)
E2_MODES = ("evaluative", "centre_weighted", "spot")
E2_REQ = tuple(FrameRequirement(FrameKind.OTHER, 1, metering=m, tag="e2") for m in E2_MODES)
E3_REQ = (
    FrameRequirement(FrameKind.OTHER, 1, metering="spot", tag="e3-bright"),
    FrameRequirement(FrameKind.OTHER, 1, metering="spot", tag="e3-dark"),
)
E5_COMPS = (-2.0, -1.0, 0.0, 1.0, 2.0)
E5_REQ = tuple(FrameRequirement(FrameKind.OTHER, 1, exposure_comp_ev=c, tag="e5") for c in E5_COMPS)
E6_ISOS = (100, 200, 400, 800, 1600)
E6_REQ = tuple(
    FrameRequirement(FrameKind.FLAT, 1, iso=i, exposure_s=1 / 250, aperture=8.0, tag="e6")
    for i in E6_ISOS
)
E7_APERTURES = (4.0, 5.6, 8.0, 11.0, 16.0)
E7_REQ = tuple(
    FrameRequirement(FrameKind.FLAT, 1, iso=100, exposure_s=1 / 250, aperture=a, tag="e7")
    for a in E7_APERTURES
)


def _ev(f: Frame) -> float | None:
    m = f.meta
    if m.aperture and m.exposure_s and m.iso:
        return exposure_value(m.aperture, m.exposure_s, m.iso)
    return None


def _accepted(frames: FrameSet, key: str) -> list[Frame]:
    return [f for f in frames.get(key, ()) if f.accepted]


def _level(f: Frame) -> float | None:
    if f.cfa is None:
        return None
    c = f.cfa
    return float(binned_signal(c.array, c.pattern, c.black_level).mean())


def e1(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    evs = [e for f in _accepted(frames, E1_REQ[0].key) if (e := _ev(f)) is not None]
    if len(evs) < 3:
        return not_tested(spec, ctx, INSUFFICIENT)
    sp = spread(evs)
    fnd = [finding("spread", "e1.spread", ev=f"{sp:.2f}", frames=len(evs))]
    if sp > ctx.params.get("e1.spread_ev"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("e1.spread", ev=f"{sp:.2f}"),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("e1.pass", ev=f"{sp:.2f}"),
        confidence=Confidence.MEDIUM,
        findings=fnd,
    )


def e2(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    per_mode: dict[str, float] = {}
    for req in E2_REQ:
        evs = [e for f in _accepted(frames, req.key) if (e := _ev(f)) is not None]
        if evs:
            per_mode[req.metering or ""] = float(np.mean(evs))
    if len(per_mode) < 2:
        return not_tested(spec, ctx, INSUFFICIENT)
    sp = spread(list(per_mode.values()))
    fnd = [finding("mode", "e2.mode", mode=k, ev=f"{v:.2f}") for k, v in per_mode.items()]
    if sp > ctx.params.get("e2.mode_dev_ev"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("e2.differ", ev=f"{sp:.2f}"),
            confidence=Confidence.LOW,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("e2.pass", ev=f"{sp:.2f}"),
        confidence=Confidence.LOW,
        findings=fnd,
    )


def e3(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    evs = {}
    for req in E3_REQ:
        vals = [e for f in _accepted(frames, req.key) if (e := _ev(f)) is not None]
        if vals:
            evs[req.tag] = float(np.mean(vals))
    if len(evs) < 2:
        return not_tested(spec, ctx, INSUFFICIENT)
    change = abs(evs["e3-bright"] - evs["e3-dark"])
    fnd = [finding("change", "e3.change", ev=f"{change:.2f}")]
    if change < ctx.params.get("e3.min_change_ev"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("e3.no_change", ev=f"{change:.2f}"),
            confidence=Confidence.LOW,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("e3.pass", ev=f"{change:.2f}"),
        confidence=Confidence.LOW,
        findings=fnd,
    )


def e4(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    levels = [lv for f in _accepted(frames, E1_REQ[0].key) if (lv := _level(f)) is not None]
    cfa = next((f.cfa for f in _accepted(frames, E1_REQ[0].key) if f.cfa), None)
    if not levels or cfa is None:
        return not_tested(spec, ctx, INSUFFICIENT)
    usable = cfa.white_level - cfa.black_level
    frac = float(np.mean(levels)) / usable
    # Report only: the offset from mid-grey may be by design (TEST-CATALOGUE E4).
    offset = float(np.log2(max(frac, 1e-6) / ctx.params.get("e4.mid_grey")))
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("e4.report", percent=f"{frac:.0%}", offset=f"{offset:+.1f}"),
        confidence=Confidence.LOW,
        findings=[finding("level", "e4.report", percent=f"{frac:.0%}", offset=f"{offset:+.1f}")],
    )


def _series(frames: FrameSet, reqs, x_of):
    xs: list[float] = []
    ys: list[float] = []
    for r in reqs:
        for f in _accepted(frames, r.key):
            lv = _level(f)
            if lv is None or lv <= 0 or f.cfa is None:
                continue
            usable = f.cfa.white_level - f.cfa.black_level
            if lv / usable > 0.9:  # clipped frames carry no information about linearity
                continue
            xs.append(x_of(r, f))
            ys.append(log2_levels([lv])[0])
    return xs, ys


def e5(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    xs, ys = _series(frames, E5_REQ, lambda r, _f: r.exposure_comp_ev or 0.0)
    if len(xs) < 4:
        return not_tested(spec, ctx, INSUFFICIENT)
    fit = linear_fit(xs, ys)
    fnd = [finding("fit", "e5.fit", slope=f"{fit.slope:.2f}", resid=f"{fit.max_residual:.2f}")]
    if fit.max_residual > ctx.params.get("e5.nonlinear_ev"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("e5.nonlinear", ev=f"{fit.max_residual:.2f}"),
            confidence=Confidence.LOW,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("e5.pass", slope=f"{fit.slope:.2f}"),
        confidence=Confidence.LOW,
        findings=fnd,
    )


def e6(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    xs, ys = _series(frames, E6_REQ, lambda r, _f: float(np.log2((r.iso or 100) / 100)))
    if len(xs) < 4:
        return not_tested(spec, ctx, INSUFFICIENT)
    fit = linear_fit(xs, ys)
    # Level should rise by one EV per ISO stop; measure departures from that line.
    dev = max(abs(y - (xs[i] + (ys[0] - xs[0]))) for i, y in enumerate(ys))
    fnd = [finding("fit", "e6.fit", slope=f"{fit.slope:.2f}", dev=f"{dev:.2f}")]
    if dev > ctx.params.get("e6.jump_ev"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("e6.jump", ev=f"{dev:.2f}"),
            confidence=Confidence.LOW,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("e6.pass", slope=f"{fit.slope:.2f}"),
        confidence=Confidence.LOW,
        findings=fnd,
    )


def e7(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    xs, ys = _series(frames, E7_REQ, lambda r, _f: -2.0 * float(np.log2(r.aperture or 8.0)))
    if len(xs) < 4:
        return not_tested(spec, ctx, INSUFFICIENT)
    dev = max(abs(y - (xs[i] + (ys[0] - xs[0]))) for i, y in enumerate(ys))
    fnd = [finding("fit", "e7.fit", dev=f"{dev:.2f}")]
    if dev > ctx.params.get("e7.step_ev"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("e7.step", ev=f"{dev:.2f}"),
            confidence=Confidence.LOW,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("e7.pass"), confidence=Confidence.LOW, findings=fnd
    )


E1 = FunctionCheck(
    make_spec("E1", "E", SEMI_OR_UPLOAD, requirements=E1_REQ, max_shots=5, gate_rules=("G1",)), e1
)
E2 = FunctionCheck(
    make_spec("E2", "E", SEMI_OR_UPLOAD, requirements=E2_REQ, max_shots=3, gate_rules=("G1",)), e2
)
E3 = FunctionCheck(
    make_spec("E3", "E", SEMI_OR_UPLOAD, requirements=E3_REQ, max_shots=3, gate_rules=("G1",)), e3
)
E4 = FunctionCheck(make_spec("E4", "E", SEMI_OR_UPLOAD), e4)
E5 = FunctionCheck(
    make_spec("E5", "E", SEMI_OR_UPLOAD, requirements=E5_REQ, max_shots=5, gate_rules=("G1",)), e5
)
E6 = FunctionCheck(
    make_spec("E6", "E", SEMI_OR_UPLOAD, requirements=E6_REQ, max_shots=5, gate_rules=("G1", "G3")),
    e6,
)
E7 = FunctionCheck(
    make_spec("E7", "E", SEMI_OR_UPLOAD, requirements=E7_REQ, max_shots=5, gate_rules=("G1", "G3")),
    e7,
)

GROUP_E: tuple[Check, ...] = (E1, E2, E3, E4, E5, E6, E7)
