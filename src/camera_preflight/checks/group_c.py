"""Group C: shutter (TEST-CATALOGUE section 5). Absolute speed is not measured (C5)."""

from __future__ import annotations

from ..analysis.shutter import burst_rhythm, curtain_gradient, level_spread_ev
from ..domain import (
    CheckResult,
    CheckSpec,
    Confidence,
    Finding,
    FrameKind,
    FrameRequirement,
    Level,
    Severity,
)
from ..knowledge import resolve_burst_fps
from .base import (
    INSUFFICIENT,
    NOT_APPLICABLE,
    REQUIRES_INSTRUMENT,
    RESOLUTION_LOW,
    Check,
    CheckContext,
    FrameSet,
    FunctionCheck,
    finding,
    frames_of,
    make_result,
    msg,
    not_tested,
)
from .manual import from_answer
from .specs import AUTO_OR_UPLOAD, MANUAL_BOTH, SEMI_OR_UPLOAD, make_spec

C1_REQ = (FrameRequirement(FrameKind.BURST, 10, tag="c1"),)
REF_S = 1 / 30
FAST_S = (1 / 250, 1 / 1000, 1 / 4000, 1 / 8000)
C2_REF = FrameRequirement(FrameKind.FLAT, 3, exposure_s=REF_S, tag="c2")
C2_FAST = tuple(FrameRequirement(FrameKind.FLAT, 3, exposure_s=t, tag="c2") for t in FAST_S)
C3_REQ = (FrameRequirement(FrameKind.FLAT, 10, exposure_s=1 / 250, tag="c3"),)
C4_FAST = tuple(
    FrameRequirement(FrameKind.FLAT, 3, exposure_s=t, tag="c4", shutter_mode="electronic")
    for t in FAST_S[1:]
)


def c1(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    fs = [f for f in frames.get(C1_REQ[0].key, ()) if f.accepted]
    if len(fs) < ctx.params.get("c1.min_frames"):
        return not_tested(spec, ctx, INSUFFICIENT)
    if any(f.meta.capture_time is None or f.meta.sub_second is None for f in fs):
        return not_tested(spec, ctx, RESOLUTION_LOW)  # needs sub-second timestamps (V-17)
    stamps = [t for f in fs if (t := f.meta.capture_seconds()) is not None]
    rep = burst_rhythm(stamps)
    if rep is None:
        return not_tested(spec, ctx, INSUFFICIENT)
    p = ctx.params
    fnd = [finding("rhythm", "c1.rhythm", fps=f"{rep.fps:.1f}", cv=f"{rep.cv:.2f}")]
    rated = resolve_burst_fps(ctx.kb)
    if rep.max_ratio > p.get("c1.stall_factor"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c1.stall", ratio=f"{rep.max_ratio:.1f}"),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    if rep.cv > p.get("c1.cv_max"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c1.uneven", cv=f"{rep.cv:.2f}"),
            confidence=Confidence.MEDIUM,
            severity=Severity.LOW,
            findings=fnd,
        )
    if rated.value is not None and rep.fps < p.get("c1.fps_ratio_min") * float(rated.value):  # type: ignore[arg-type]
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c1.slow", fps=f"{rep.fps:.1f}", rated=rated.value),
            confidence=rated.confidence_cap or Confidence.LOW,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("c1.pass", fps=f"{rep.fps:.1f}"),
        confidence=Confidence.MEDIUM,
        findings=fnd,
    )


def _gradients(frames: FrameSet, ctx: CheckContext, fast: tuple[FrameRequirement, ...]):
    ref = frames_of(frames, C2_REF.key)
    out: list[tuple[float, float]] = []
    if not ref:
        return out, False
    c0 = ref[0].cfa
    assert c0 is not None
    for req in fast:
        fs = frames_of(frames, req.key)
        if len(fs) < 2:
            continue
        rep = curtain_gradient(
            [f.cfa.array for f in fs if f.cfa],
            [f.cfa.array for f in ref if f.cfa],
            c0.pattern,
            c0.black_level,
        )
        out.append((req.exposure_s or 0.0, max(abs(rep.gradient_rows), abs(rep.gradient_cols))))
    return out, True


def c2(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    grads, has_ref = _gradients(frames, ctx, C2_FAST)
    if not has_ref or not grads:
        return not_tested(spec, ctx, INSUFFICIENT)
    limit = ctx.params.get("c2.gradient_max")
    fnd: list[Finding] = [
        finding("gradient", "c2.gradient", speed=f"1/{round(1 / t)}", amp=f"{g:.3f}")
        for t, g in grads
    ]
    bad = [(t, g) for t, g in grads if g > limit]
    if bad:
        t, g = max(bad, key=lambda x: x[1])
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c2.gradient", speed=f"1/{round(1 / t)}", amp=f"{g:.1%}"),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("c2.pass"), confidence=Confidence.MEDIUM, findings=fnd
    )


def c3(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    fs = frames_of(frames, C3_REQ[0].key)
    if len(fs) < 5:
        return not_tested(spec, ctx, INSUFFICIENT)
    c0 = fs[0].cfa
    assert c0 is not None
    spread, levels = level_spread_ev([f.cfa.array for f in fs if f.cfa], c0.pattern, c0.black_level)
    fnd = [finding("spread", "c3.spread", ev=f"{spread:.3f}", frames=len(levels))]
    if spread > ctx.params.get("c3.spread_ev_max"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c3.spread", ev=f"{spread:.2f}"),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("c3.pass", ev=f"{spread:.2f}"),
        confidence=Confidence.MEDIUM,
        findings=fnd,
    )


def c4(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    mech, has_ref = _gradients(frames, ctx, C2_FAST)
    elec, _ = _gradients(frames, ctx, C4_FAST)
    if not elec:
        return not_tested(spec, ctx, NOT_APPLICABLE)
    if not has_ref or not mech:
        return not_tested(spec, ctx, INSUFFICIENT)
    limit = ctx.params.get("c2.gradient_max")
    speeds = {t for t, _ in elec}
    mech_bad = any(g > limit for t, g in mech if t in speeds)
    elec_bad = any(g > limit for _, g in elec)
    fnd = [finding("mode", "c4.modes", mechanical=mech_bad, electronic=elec_bad)]
    if mech_bad and not elec_bad:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c4.curtain"),
            confidence=Confidence.LOW,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    if elec_bad:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("c4.sensor_or_light"),
            confidence=Confidence.LOW,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("c4.pass"), confidence=Confidence.LOW, findings=fnd
    )


def c5(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    return not_tested(spec, ctx, REQUIRES_INSTRUMENT)


C1 = FunctionCheck(
    make_spec(
        "C1", "C", AUTO_OR_UPLOAD, requirements=C1_REQ, max_shots=10, kb_fields=("max_burst_fps",)
    ),
    c1,
)
C2 = FunctionCheck(
    make_spec(
        "C2",
        "C",
        SEMI_OR_UPLOAD,
        requirements=(C2_REF, *C2_FAST),
        max_shots=15,
        gate_rules=("G1", "G2", "G3", "G4"),
    ),
    c2,
)
C3 = FunctionCheck(
    make_spec(
        "C3", "C", SEMI_OR_UPLOAD, requirements=C3_REQ, max_shots=10, gate_rules=("G1", "G2", "G3")
    ),
    c3,
)
C4 = FunctionCheck(
    make_spec(
        "C4",
        "C",
        SEMI_OR_UPLOAD,
        requirements=C4_FAST,
        max_shots=12,
        gate_rules=("G1", "G2", "G3", "G4"),
    ),
    c4,
)
C5 = FunctionCheck(make_spec("C5", "C", MANUAL_BOTH), c5)
C6 = FunctionCheck(make_spec("C6", "C", MANUAL_BOTH), lambda spec, _f, ctx: from_answer(spec, ctx))

GROUP_C: tuple[Check, ...] = (C1, C2, C3, C4, C5, C6)
