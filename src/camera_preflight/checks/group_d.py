"""Group D: autofocus (TEST-CATALOGUE section 6). Two tiers (D-04); verdicts are Suspect (D-03)."""

from __future__ import annotations

import numpy as np

from ..analysis.af import AfPoint, coefficient_of_variation, region_sharpness, sharpness_map
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
from ..knowledge import resolve_af_point_count
from .base import (
    INSUFFICIENT,
    NO_REFERENCE,
    UNREADABLE,
    AfAttempt,
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
from .specs import (
    CONNECTED_SEMI,
    FROM_FIRST_FRAME,
    SEMI_OR_UPLOAD,
    make_spec,
)

GENERIC_POINTS: tuple[AfPoint, ...] = (
    AfPoint("centre", 0.5, 0.5, is_centre=True),
    AfPoint("left", 0.15, 0.5),
    AfPoint("right", 0.85, 0.5),
    AfPoint("top", 0.5, 0.15),
    AfPoint("bottom", 0.5, 0.85),
)
SDK_ANY = frozenset({"canon", "sony", "nikon"})


def af_key(point: str, prefix: str = "af") -> str:
    return FrameRequirement(FrameKind.CHART, 1, tag=f"{prefix}:{point}").key


def af_requirements(
    points: tuple[AfPoint, ...], attempts: int, prefix: str = "af"
) -> tuple[FrameRequirement, ...]:
    return tuple(
        FrameRequirement(FrameKind.CHART, attempts, tag=f"{prefix}:{p.name}") for p in points
    )


def priority_points(points: tuple[AfPoint, ...]) -> tuple[AfPoint, ...]:
    """Centre plus the four outermost points (D5)."""
    centre = next((p for p in points if p.is_centre), None) or min(
        points, key=lambda p: (p.x - 0.5) ** 2 + (p.y - 0.5) ** 2
    )
    others = [p for p in points if p is not centre]
    if len(others) <= 4:
        return (centre, *others)
    by_far = sorted(others, key=lambda p: -((p.x - 0.5) ** 2 + (p.y - 0.5) ** 2))
    picked: list[AfPoint] = []
    for want in ("left", "right", "top", "bottom"):
        if want == "left":
            cand = min(by_far, key=lambda p: p.x)
        elif want == "right":
            cand = max(by_far, key=lambda p: p.x)
        elif want == "top":
            cand = min(by_far, key=lambda p: p.y)
        else:
            cand = max(by_far, key=lambda p: p.y)
        if cand not in picked:
            picked.append(cand)
    return (centre, *picked)


def points_for(ctx: CheckContext) -> tuple[AfPoint, ...]:
    """Generic 5-point plan; the knowledge base layout is applied by the wizard (D1)."""
    return GENERIC_POINTS


def _centre_name(points: tuple[AfPoint, ...]) -> str:
    return next((p.name for p in points if p.is_centre), points[0].name)


def _sharp_by_point(
    frames: FrameSet, points: tuple[AfPoint, ...], prefix: str = "af"
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for p in points:
        vals: list[float] = []
        for f in frames_of(frames, af_key(p.name, prefix)):
            assert f.cfa is not None
            vals.append(region_sharpness(f.cfa.array, f.cfa.pattern, f.cfa.black_level, p))
        if vals:
            out[p.name] = vals
    return out


def d1(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    res = (
        resolve_af_point_count(ctx.kb, ctx.derived)
        if ctx.derived
        else resolve_af_point_count(ctx.kb, _empty())
    )
    if res.value is None:
        return make_result(
            spec,
            ctx,
            Level.PASS,
            msg("d1.generic"),
            confidence=Confidence.LOW,
            findings=[finding("plan", "d1.generic")],
        )
    conf = res.confidence_cap or Confidence.MEDIUM
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg(f"d1.points_{res.tier}", count=res.value),
        confidence=conf,
        findings=[finding("points", f"d1.points_{res.tier}", count=res.value)],
    )


def _empty():
    from ..knowledge import DerivedRecord

    return DerivedRecord()


def _tier1(ctx: CheckContext, points: tuple[AfPoint, ...]):
    """Points that failed to focus in at least ``af.fail_attempts`` attempts."""
    need = int(ctx.params.get("af.fail_attempts"))
    bad: list[tuple[str, bool]] = []  # (point, all failures measured by the app)
    seen = 0
    for p in points:
        attempts = ctx.af_attempts.get(p.name, [])
        if not attempts:
            continue
        if (
            len(attempts) < int(ctx.params.get("af.attempts"))
            and sum(1 for a in attempts if not a.focused) < need
        ):
            continue  # too few reports to call this point; it stays untested
        seen += 1
        fails = [a for a in attempts if not a.focused]
        if len(fails) >= need:
            bad.append((p.name, all(a.source == "tethered" for a in fails)))
    return bad, seen


def _d2_like(
    spec: CheckSpec, ctx: CheckContext, points: tuple[AfPoint, ...], ok_code: str
) -> CheckResult:
    bad, seen = _tier1(ctx, points)
    if not seen:
        return not_tested(spec, ctx, INSUFFICIENT)
    centre = _centre_name(points)
    if bad:
        name, measured = bad[0]
        sev = Severity.HIGH if any(n == centre for n, _ in bad) else Severity.MEDIUM
        conf = Confidence.MEDIUM if measured else Confidence.LOW
        fnd = [finding("no_focus", "d2.point", point=n, measured=m) for n, m in bad]
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d2.fails", point=name, count=len(bad)),
            confidence=conf,
            severity=sev,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg(ok_code, count=seen), confidence=Confidence.MEDIUM
    )


def d2(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    return _d2_like(spec, ctx, points_for(ctx), "d2.pass")


def _soft_points(sharp: dict[str, list[float]], points: tuple[AfPoint, ...], ratio: float):
    centre = _centre_name(points)
    means = {k: float(np.mean(v)) for k, v in sharp.items()}
    reference = means.get(centre) or float(np.median(list(means.values())))
    if reference <= 0:
        return [], reference, means
    soft = [n for n, m in means.items() if n != centre and m < ratio * reference]
    if means.get(centre, reference) < ratio * float(np.median(list(means.values()))):
        soft.insert(0, centre)
    return soft, reference, means


def d3(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    return _d3_like(spec, frames, ctx, points_for(ctx))


def _d3_like(
    spec: CheckSpec, frames: FrameSet, ctx: CheckContext, points: tuple[AfPoint, ...]
) -> CheckResult:
    sharp = _sharp_by_point(frames, points)
    if len(sharp) < 2:
        return not_tested(spec, ctx, INSUFFICIENT)
    soft, _ref, means = _soft_points(sharp, points, ctx.params.get("af.soft_ratio"))
    fnd = [
        finding("sharpness", "d3.value", point=n, value=f"{m:.3f}")
        for n, m in sorted(means.items())
    ]
    if soft:
        centre = _centre_name(points)
        sev = (
            Severity.HIGH if centre in soft else Severity.LOW if len(soft) == 1 else Severity.MEDIUM
        )
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d3.soft", points=", ".join(soft)),
            confidence=Confidence.MEDIUM,
            severity=sev,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("d3.pass", count=len(means)),
        confidence=Confidence.MEDIUM,
        findings=fnd,
    )


def d4(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    return _d4_like(spec, frames, ctx, points_for(ctx))


def _d4_like(
    spec: CheckSpec, frames: FrameSet, ctx: CheckContext, points: tuple[AfPoint, ...]
) -> CheckResult:
    sharp = {k: v for k, v in _sharp_by_point(frames, points).items() if len(v) >= 2}
    if not sharp:
        return not_tested(spec, ctx, INSUFFICIENT)
    limit = ctx.params.get("af.repeat_cv")
    cvs = {k: coefficient_of_variation(v) for k, v in sharp.items()}
    unstable = [k for k, cv in cvs.items() if cv > limit]
    fnd = [finding("cv", "d4.cv", point=k, cv=f"{v:.2f}") for k, v in sorted(cvs.items())]
    if unstable:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d4.unstable", points=", ".join(unstable)),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("d4.pass"), confidence=Confidence.MEDIUM, findings=fnd
    )


def d5(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    """Early D2 to D4 on the priority points (centre plus four outermost)."""
    pts = priority_points(points_for(ctx))
    parts = [
        _d2_like(spec, ctx, pts, "d2.pass"),
        _d3_like(spec, frames, ctx, pts),
        _d4_like(spec, frames, ctx, pts),
    ]
    tested = [r for r in parts if r.level is not Level.NOT_TESTED]
    if not tested:
        return not_tested(spec, ctx, INSUFFICIENT)
    bad = [r for r in tested if r.level is Level.SUSPECT]
    fnd = [Finding(kind="part", message=r.explanation) for r in tested]
    if bad:
        worst = max(
            bad,
            key=lambda r: ["low", "medium", "high", "blocker"].index(
                r.severity.value if r.severity else "low"
            ),
        )
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            worst.explanation,
            confidence=Confidence.LOW,
            severity=worst.severity,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("d5.pass", count=len(pts)),
        confidence=Confidence.LOW,
        findings=fnd,
    )


def d6(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    fs = frames_of(frames, FrameRequirement(FrameKind.CHART, 1, tag="region").key)
    if not fs:
        return not_tested(spec, ctx, INSUFFICIENT)
    maps = []
    for f in fs:
        assert f.cfa is not None
        maps.append(sharpness_map(f.cfa.array, f.cfa.pattern, f.cfa.black_level))
    mean_map = np.mean(maps, axis=0)
    med = float(np.median(mean_map))
    weak = int(np.sum(mean_map < ctx.params.get("af.soft_ratio") * med)) if med > 0 else 0
    fnd = [finding("map", "d6.map", weak=weak, regions=int(mean_map.size))]
    if weak:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d6.weak", count=weak),
            confidence=Confidence.LOW,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("d6.pass"), confidence=Confidence.LOW, findings=fnd
    )


def d7(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    times = ctx.sdk_data.get("af_response_s")
    if not isinstance(times, list) or not times:
        return not_tested(spec, ctx, INSUFFICIENT)
    ref = ctx.kb.af.max_response_s if ctx.kb else None
    median = float(np.median([float(t) for t in times]))
    fnd = [finding("time", "d7.time", median=f"{median:.2f}")]
    if ref is None:
        res = not_tested(spec, ctx, NO_REFERENCE)
        return res.model_copy(update={"findings": tuple(fnd)})
    if median > ctx.params.get("d7.slow_ratio") * float(ref.value):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d7.slow", median=f"{median:.2f}", ref=ref.value),
            confidence=ref.confidence,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("d7.pass", median=f"{median:.2f}"),
        confidence=ref.confidence,
        findings=fnd,
    )


def d8(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    pos = ctx.sdk_data.get("focus_position")
    if not isinstance(pos, list) or not pos:
        return not_tested(spec, ctx, INSUFFICIENT)
    missed = [p for p in pos if not bool(p[1])]
    if missed:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d8.missed", count=len(missed)),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
        )
    return make_result(spec, ctx, Level.PASS, msg("d8.pass"), confidence=Confidence.MEDIUM)


def d9(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    value = ctx.device.af_fine_tune if ctx.device else None
    if value is None:
        first = next(
            (f for fs in frames.values() for f in fs if f.meta.af_fine_tune is not None), None
        )
        value = first.meta.af_fine_tune if first else None
    if value is None:
        return not_tested(spec, ctx, UNREADABLE)
    if value != 0:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d9.set", value=value),
            confidence=Confidence.HIGH,
            severity=Severity.LOW,
            findings=[finding("fine_tune", "d9.set", value=value)],
        )
    return make_result(spec, ctx, Level.PASS, msg("d9.zero"), confidence=Confidence.HIGH)


def faulty_points(
    frames: FrameSet,
    ctx: CheckContext,
    attempts: dict[str, list[AfAttempt]],
    prefix: str = "af",
) -> set[str]:
    """Points with a tier 1 or tier 2 fault for one lens (input of D10)."""
    points = points_for(ctx)
    bad: set[str] = set()
    need = int(ctx.params.get("af.fail_attempts"))
    for p in points:
        if sum(1 for a in attempts.get(p.name, []) if not a.focused) >= need:
            bad.add(p.name)
    sharp = _sharp_by_point(frames, points, prefix)
    if len(sharp) >= 2:
        soft, _ref, _means = _soft_points(sharp, points, ctx.params.get("af.soft_ratio"))
        bad.update(soft)
    return bad


def d10(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    lenses = {k: v for k, v in ctx.af_by_lens.items()}
    if len(lenses) < 2:
        return not_tested(spec, ctx, INSUFFICIENT)
    sets = list(lenses.values())
    both = set.intersection(*sets)
    any_ = set.union(*sets)
    only_one = any_ - both
    fnd: list[Finding] = [
        finding("lens", "d10.lens", lens=k, points=", ".join(sorted(v))) for k, v in lenses.items()
    ]
    if both:
        # The fault repeats with both lenses: the only AF case that may be a Fail (TEST-CATALOGUE D).
        return make_result(
            spec,
            ctx,
            Level.FAIL,
            msg("d10.body", points=", ".join(sorted(both))),
            confidence=Confidence.MEDIUM,
            severity=Severity.HIGH,
            findings=fnd,
        )
    if only_one:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("d10.lens", points=", ".join(sorted(only_one))),
            confidence=Confidence.MEDIUM,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("d10.pass"), confidence=Confidence.MEDIUM, findings=fnd
    )


_GEN_REQ = af_requirements(GENERIC_POINTS, 3)

D1 = FunctionCheck(
    make_spec("D1", "D", FROM_FIRST_FRAME, kb_fields=("af_point_count", "af_layout")), d1
)
D2 = FunctionCheck(
    make_spec(
        "D2", "D", SEMI_OR_UPLOAD, requirements=_GEN_REQ, max_shots=15, gate_rules=("G1", "G6")
    ),
    d2,
)
D3 = FunctionCheck(
    make_spec("D3", "D", SEMI_OR_UPLOAD, requirements=_GEN_REQ, gate_rules=("G1", "G6")), d3
)
D4 = FunctionCheck(make_spec("D4", "D", SEMI_OR_UPLOAD), d4)
D5 = FunctionCheck(
    make_spec(
        "D5",
        "D",
        SEMI_OR_UPLOAD,
        requirements=af_requirements(priority_points(GENERIC_POINTS), 3),
        max_shots=15,
    ),
    d5,
)
D6 = FunctionCheck(make_spec("D6", "D", CONNECTED_SEMI, needs_sdk=SDK_ANY), d6)
D7 = FunctionCheck(
    make_spec("D7", "D", CONNECTED_SEMI, needs_sdk=SDK_ANY, kb_fields=("af_response",)), d7
)
D8 = FunctionCheck(make_spec("D8", "D", CONNECTED_SEMI, needs_sdk=frozenset({"sony"})), d8)
D9 = FunctionCheck(make_spec("D9", "D", FROM_FIRST_FRAME), d9)
D10 = FunctionCheck(make_spec("D10", "D", SEMI_OR_UPLOAD, max_shots=15), d10)

GROUP_D: tuple[Check, ...] = (D1, D2, D3, D4, D5, D6, D7, D8, D9, D10)
