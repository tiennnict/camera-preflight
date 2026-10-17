"""Group B: sensor checks (TEST-CATALOGUE section 4). Analysis runs on CFA planes (R-08)."""

from __future__ import annotations

import numpy as np

from ..analysis.common import binned_signal
from ..analysis.dust import find_blobs, mark_sensor_side, relative_map
from ..analysis.pixels import (
    classify,
    cluster_defects,
    flat_outliers,
    noise_and_banding,
    repeated_bright,
)
from ..analysis.uniformity import analyse_uniformity
from ..domain import (
    CheckResult,
    CheckSpec,
    Confidence,
    Finding,
    Frame,
    FrameKind,
    FrameRequirement,
    Level,
    Message,
    Severity,
)
from . import evidence as ev
from .base import (
    INSUFFICIENT,
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
from .specs import SEMI_OR_UPLOAD, make_spec

Coord = tuple[int, int]

B1_ISOS = (100, 1600, 6400)
B1_SHORT_S = 1 / 100
B1_LONG_S = 30.0


def _dark(iso: int, t: float) -> FrameRequirement:
    return FrameRequirement(FrameKind.DARK, 3, iso=iso, exposure_s=t, tag="b1")


B1_REQ = tuple(_dark(i, t) for i in B1_ISOS for t in (B1_SHORT_S, B1_LONG_S))
B2_REQ = (FrameRequirement(FrameKind.FLAT, 3, aperture=8.0, tag="b2"),)
B4_REQ = (FrameRequirement(FrameKind.FLAT, 3, aperture=22.0, tag="b4"),)
B2_KEY = B2_REQ[0].key
B4_KEY = B4_REQ[0].key


def _cfa(frame: Frame):
    assert frame.cfa is not None
    return frame.cfa


def _verdict(
    n_isolated: int, n_clusters: int, megapixels: float, allowance: float
) -> tuple[Level, Severity | None, Confidence]:
    """Shared scale for B1 to B3: cluster = High, isolated counted against an allowance."""
    if n_clusters:
        return Level.SUSPECT, Severity.HIGH, Confidence.HIGH
    if n_isolated > allowance * max(megapixels, 0.01):
        return Level.SUSPECT, Severity.MEDIUM, Confidence.MEDIUM
    return Level.PASS, None, Confidence.MEDIUM


def _defect_findings(kind: str, defects: dict[Coord, tuple[str, float]]) -> list[Finding]:
    return [
        finding(kind, f"b.{kind}", row=r, col=c, channel=ch, excess=f"{x:.0f}")
        for (r, c), (ch, x) in sorted(defects.items())
    ]


def _hot_from_darks(
    frames: FrameSet, ctx: CheckContext
) -> tuple[dict[Coord, tuple[str, float]], dict[Coord, str], tuple[int, int] | None, int]:
    """Repeated bright pixels over all dark sets, their classification, mosaic shape, sets used."""
    p = ctx.params
    hot: dict[Coord, tuple[str, float]] = {}
    kinds: dict[Coord, str] = {}
    shape: tuple[int, int] | None = None
    sets = 0
    for iso in B1_ISOS:
        found_by_t: dict[float, dict[Coord, tuple[str, float]]] = {}
        for t in (B1_SHORT_S, B1_LONG_S):
            fs = frames_of(frames, _dark(iso, t).key)
            if len(fs) < 2:
                continue
            cfa0 = _cfa(fs[0])
            shape = shape or cfa0.shape
            found = repeated_bright(
                [_cfa(f).array for f in fs],
                cfa0.pattern,
                k_sigma=p.get("b1.k_sigma"),
                min_excess_dn=p.get("b1.min_excess_dn"),
                repeat_min=int(p.get("b1.repeat_min")),
            )
            found_by_t[t] = found
            sets += 1
            for c, v in found.items():
                if c not in hot or v[1] > hot[c][1]:
                    hot[c] = v
        if B1_SHORT_S in found_by_t and B1_LONG_S in found_by_t:
            kinds.update(
                classify(
                    found_by_t[B1_SHORT_S],
                    found_by_t[B1_LONG_S],
                    exposure_ratio=B1_LONG_S / B1_SHORT_S,
                    growth_ratio=p.get("b3.hot_growth_ratio"),
                )
            )
    return hot, kinds, shape, sets


def _flat_defects(frames: FrameSet, ctx: CheckContext):
    fs = frames_of(frames, B2_KEY)
    if len(fs) < 2:
        return None
    cfa0 = _cfa(fs[0])
    stuck, dead = flat_outliers(
        [_cfa(f).array for f in fs],
        cfa0.pattern,
        cfa0.black_level,
        rel_dev=ctx.params.get("b2.rel_dev"),
    )
    return stuck, dead, cfa0.shape


def b1(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    hot, kinds, shape, sets = _hot_from_darks(frames, ctx)
    if shape is None or sets == 0:
        return not_tested(spec, ctx, INSUFFICIENT)
    hot_only = {c: v for c, v in hot.items() if kinds.get(c, "hot") == "hot"}
    clusters = [
        g
        for g in cluster_defects(
            list(hot_only), shape, int(ctx.params.get("b1.cluster_distance_px"))
        )
        if len(g) > 1
    ]
    in_cluster = {c for g in clusters for c in g}
    isolated = len(hot_only) - len(in_cluster)
    mp = shape[0] * shape[1] / 1e6
    level, sev, conf = _verdict(isolated, len(clusters), mp, ctx.params.get("b1.allowance_per_mp"))
    evid = ev.pixel_map(ctx.evidence_dir, "b1-hot-pixels", shape, hot_only, msg("evidence.hot_map"))
    fnd = _defect_findings("hot", hot_only)
    if level is Level.PASS:
        code = "b1.pass_none" if not hot_only else "b1.pass_few"
        return make_result(
            spec,
            ctx,
            level,
            msg(code, count=len(hot_only)),
            confidence=conf,
            findings=fnd,
            evidence=[e for e in [evid] if e],
        )
    code = "b1.cluster" if clusters else "b1.many"
    return make_result(
        spec,
        ctx,
        level,
        msg(code, count=len(hot_only), clusters=len(clusters)),
        confidence=conf,
        severity=sev,
        findings=fnd,
        evidence=[e for e in [evid] if e],
    )


def b2(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    res = _flat_defects(frames, ctx)
    if res is None:
        return not_tested(spec, ctx, INSUFFICIENT)
    stuck, dead, shape = res
    allc = {**stuck, **dead}
    clusters = [
        g
        for g in cluster_defects(list(allc), shape, int(ctx.params.get("b1.cluster_distance_px")))
        if len(g) > 1
    ]
    in_cluster = {c for g in clusters for c in g}
    isolated = len(allc) - len(in_cluster)
    mp = shape[0] * shape[1] / 1e6
    level, sev, conf = _verdict(isolated, len(clusters), mp, ctx.params.get("b1.allowance_per_mp"))
    evid = ev.pixel_map(ctx.evidence_dir, "b2-stuck-dead", shape, allc, msg("evidence.stuck_map"))
    fnd = _defect_findings("stuck_bright", stuck) + _defect_findings("dead", dead)
    if level is Level.PASS:
        return make_result(
            spec,
            ctx,
            level,
            msg("b2.pass", count=len(allc)),
            confidence=conf,
            findings=fnd,
            evidence=[e for e in [evid] if e],
        )
    return make_result(
        spec,
        ctx,
        level,
        msg("b2.defects", stuck=len(stuck), dead=len(dead)),
        confidence=conf,
        severity=sev,
        findings=fnd,
        evidence=[e for e in [evid] if e],
    )


def b3(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    hot, kinds, shape_d, sets = _hot_from_darks(frames, ctx)
    flat = _flat_defects(frames, ctx)
    if sets == 0 and flat is None:
        return not_tested(spec, ctx, INSUFFICIENT)
    stuck_all: dict[Coord, tuple[str, float]] = {}
    dead: dict[Coord, tuple[str, float]] = {}
    shape = shape_d
    if flat is not None:
        stuck_all.update(flat[0])
        dead = flat[1]
        shape = shape or flat[2]
    hot_only = {c: v for c, v in hot.items() if kinds.get(c, "hot") == "hot"}
    for c, v in hot.items():
        if kinds.get(c) == "stuck_bright":
            stuck_all[c] = v
    total = {**hot_only, **stuck_all, **dead}
    assert shape is not None
    clusters = [
        g
        for g in cluster_defects(list(total), shape, int(ctx.params.get("b1.cluster_distance_px")))
        if len(g) > 1
    ]
    isolated = len(total) - len({c for g in clusters for c in g})
    mp = shape[0] * shape[1] / 1e6
    level, sev, conf = _verdict(isolated, len(clusters), mp, ctx.params.get("b1.allowance_per_mp"))
    by_channel: dict[str, int] = {}
    for _c, (ch, _x) in total.items():
        by_channel[ch] = by_channel.get(ch, 0) + 1
    fnd = [
        finding(
            "classification", "b3.classes", hot=len(hot_only), stuck=len(stuck_all), dead=len(dead)
        ),
        *[
            finding("channel", "b3.channel", channel=ch, count=n)
            for ch, n in sorted(by_channel.items())
        ],
    ]
    if level is Level.PASS:
        return make_result(
            spec,
            ctx,
            level,
            msg("b3.none" if not total else "b3.few", count=len(total)),
            confidence=conf,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        level,
        msg("b3.classes", hot=len(hot_only), stuck=len(stuck_all), dead=len(dead)),
        confidence=conf,
        severity=sev,
        findings=fnd,
    )


def _mean_signal(fs: list[Frame]) -> np.ndarray:
    c0 = _cfa(fs[0])
    return np.mean([binned_signal(_cfa(f).array, c0.pattern, c0.black_level) for f in fs], axis=0)


def b4(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    small = frames_of(frames, B4_KEY)
    if not small:
        return not_tested(spec, ctx, INSUFFICIENT)
    p = ctx.params
    blobs, _rel = find_blobs(
        _mean_signal(small).astype(np.float32),
        depth_threshold=p.get("b4.blob_depth"),
        min_area=int(p.get("b4.min_area_px")),
        linear_elongation=p.get("b4.linear_elongation"),
        linear_min_len=p.get("b4.linear_min_len_px"),
    )
    wide = frames_of(frames, B2_KEY)
    conf = Confidence.MEDIUM
    if wide:
        wide_rel = relative_map(_mean_signal(wide).astype(np.float32))
        blobs = mark_sensor_side(blobs, wide_rel, ratio=p.get("b4.sensor_side_ratio"))
    else:
        conf = (
            Confidence.LOW
        )  # without the wide-aperture frames the marks cannot be placed on the sensor
    counted = [b for b in blobs if b.sensor_side is not False]
    # A linear mark counts whether or not it fades at the wide aperture: a scratch on the sensor
    # surface does not fade. Without the fade the mark could also be on the lens, so confidence drops.
    linear = [b for b in blobs if b.linear]
    if linear and not any(b.sensor_side is not False for b in linear):
        conf = Confidence.LOW
    shape = _mean_signal(small).shape
    evid = ev.marks_map(
        ctx.evidence_dir,
        "b4-marks",
        shape,
        [(b.row, b.col, max(b.major, 4.0) / 2) for b in counted],
        msg("evidence.dust_map"),
    )
    fnd = [
        finding(
            "mark",
            "b4.mark",
            row=int(b.row),
            col=int(b.col),
            area=b.area,
            depth=f"{b.depth:.2f}",
            linear=b.linear,
        )
        for b in counted
    ]
    fnd += [
        finding(
            "mark",
            "b4.mark",
            row=int(b.row),
            col=int(b.col),
            area=b.area,
            depth=f"{b.depth:.2f}",
            linear=True,
        )
        for b in linear
        if b not in counted
    ]
    out_e = [e for e in [evid] if e]
    if linear:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("b4.linear", count=len(linear)),
            confidence=conf,
            severity=Severity.HIGH,
            findings=fnd,
            evidence=out_e,
        )
    if len(counted) >= p.get("b4.heavy_count"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("b4.heavy", count=len(counted)),
            confidence=conf,
            severity=Severity.MEDIUM,
            findings=fnd,
            evidence=out_e,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("b4.pass", count=len(counted)),
        confidence=conf,
        findings=fnd,
        evidence=out_e,
    )


def b5(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    fs = frames_of(frames, B2_KEY)
    if not fs:
        return not_tested(spec, ctx, INSUFFICIENT)
    c0 = _cfa(fs[0])
    mean_arr = np.mean([_cfa(f).array for f in fs], axis=0).astype(np.float32)
    rep = analyse_uniformity(mean_arr, c0.pattern, c0.black_level)
    p = ctx.params
    issues: list[Finding] = []
    if max(rep.stripe_amp_rows, rep.stripe_amp_cols) > p.get("b5.stripe_amp"):
        issues.append(
            finding(
                "stripes", "b5.stripes", amp=f"{max(rep.stripe_amp_rows, rep.stripe_amp_cols):.3f}"
            )
        )
    if rep.colour_cast > p.get("b5.cast"):
        issues.append(finding("cast", "b5.cast", amp=f"{rep.colour_cast:.3f}"))
    if rep.asymmetry > p.get("b5.asymmetry"):
        issues.append(finding("asymmetry", "b5.asymmetry", amp=f"{rep.asymmetry:.3f}"))
    evid = ev.heat_map(ctx.evidence_dir, "b5-uniformity", rep.grid, msg("evidence.uniformity_map"))
    out_e = [e for e in [evid] if e]
    if issues:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            Message(code=issues[0].message.code, params=issues[0].message.params),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=issues,
            evidence=out_e,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("b5.pass"), confidence=Confidence.MEDIUM, evidence=out_e
    )


def b6(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    p = ctx.params
    reports = []
    for iso in B1_ISOS:
        fs = frames_of(frames, _dark(iso, B1_SHORT_S).key) or frames_of(
            frames, _dark(iso, B1_LONG_S).key
        )
        if fs:
            c0 = _cfa(fs[0])
            reports.append((iso, noise_and_banding(c0.array, c0.pattern)))
    if not reports:
        return not_tested(spec, ctx, INSUFFICIENT)
    flagged = []
    fnd: list[Finding] = []
    for iso, r in reports:
        sigma = float(np.median(list(r.sigma_dn.values())))
        fnd.append(finding("noise", "b6.noise", iso=iso, sigma=f"{sigma:.2f}"))
        for axis, got, exp in (
            ("rows", r.row_banding_dn, r.row_expected_dn),
            ("columns", r.col_banding_dn, r.col_expected_dn),
        ):
            if got >= p.get("b6.banding_ratio") * exp and got >= p.get("b6.banding_min_dn"):
                flagged.append((iso, axis))
                fnd.append(finding("banding", "b6.banding", iso=iso, axis=axis, amp=f"{got:.2f}"))
    if flagged:
        iso, axis = flagged[0]
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("b6.banding", iso=iso, axis=axis, amp=""),
            confidence=Confidence.MEDIUM,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("b6.pass"), confidence=Confidence.MEDIUM, findings=fnd
    )


B1 = FunctionCheck(
    make_spec(
        "B1", "B", SEMI_OR_UPLOAD, requirements=B1_REQ, max_shots=18, gate_rules=("G1", "G7")
    ),
    b1,
)
B2 = FunctionCheck(
    make_spec(
        "B2", "B", SEMI_OR_UPLOAD, requirements=B2_REQ, max_shots=3, gate_rules=("G1", "G2", "G3")
    ),
    b2,
)
B3 = FunctionCheck(make_spec("B3", "B", SEMI_OR_UPLOAD), b3)
B4 = FunctionCheck(
    make_spec(
        "B4", "B", SEMI_OR_UPLOAD, requirements=B4_REQ, max_shots=3, gate_rules=("G1", "G2", "G3")
    ),
    b4,
)
B5 = FunctionCheck(make_spec("B5", "B", SEMI_OR_UPLOAD), b5)
B6 = FunctionCheck(make_spec("B6", "B", SEMI_OR_UPLOAD), b6)

GROUP_B: tuple[Check, ...] = (B1, B2, B3, B4, B5, B6)
