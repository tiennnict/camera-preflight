"""Group A: identification and camera data (TEST-CATALOGUE section 3)."""

from __future__ import annotations

import re

from ..domain import CheckResult, CheckSpec, Confidence, Level, Severity
from ..knowledge import resolve_rated_life
from .base import (
    NO_REFERENCE,
    UNREADABLE,
    Check,
    CheckContext,
    FrameSet,
    FunctionCheck,
    finding,
    make_result,
    msg,
    not_tested,
)
from .manual import from_answer
from .plausibility import plausibility_notes
from .specs import AUTO_OR_UPLOAD, CONNECTED_AUTO, FROM_FIRST_FRAME, MANUAL_BOTH, make_spec


def _all_frames(frames: FrameSet):
    return [f for fs in frames.values() for f in fs]


def _device(ctx: CheckContext, frames: FrameSet):
    """Device facts: from the backend, else merged from the first frame with metadata."""
    from ..domain import DeviceInfo

    dev = ctx.device or DeviceInfo()
    first = next((f for f in _all_frames(frames) if f.meta.model or f.meta.serial), None)
    if first is None:
        return dev
    m = first.meta
    return DeviceInfo(
        brand=dev.brand or m.make,
        model=dev.model or m.model,
        serial=dev.serial or m.serial,
        firmware=dev.firmware or m.firmware,
        lens=dev.lens or m.lens,
        battery_percent=dev.battery_percent,
        shutter_count=dev.shutter_count if dev.shutter_count is not None else m.shutter_count,
        storage=dev.storage,
        af_fine_tune=dev.af_fine_tune if dev.af_fine_tune is not None else m.af_fine_tune,
        usb_mode=dev.usb_mode,
    )


def _suffix(serial: str | None) -> str:
    return (serial or "")[-4:]


def a1(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    dev = _device(ctx, frames)
    if not (dev.model or dev.brand):
        return not_tested(spec, ctx, UNREADABLE)
    problems = []
    if not dev.serial:
        problems.append(finding("serial", "a1.serial_unreadable"))
    elif ctx.entered_serial and _norm(ctx.entered_serial) != _norm(dev.serial):
        problems.append(
            finding(
                "serial",
                "a1.serial_mismatch",
                read=_suffix(dev.serial),
                entered=_suffix(ctx.entered_serial),
            )
        )
    if problems:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg(problems[0].message.code, **problems[0].data),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
            findings=problems,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("a1.pass", model=dev.model or "", serial=_suffix(dev.serial)),
        confidence=Confidence.HIGH if dev.serial else Confidence.MEDIUM,
    )


def _norm(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text).lower()


def a2(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    dev = _device(ctx, frames)
    if dev.battery_percent is None:
        return not_tested(spec, ctx, UNREADABLE)
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("a2.recorded", percent=dev.battery_percent),
        confidence=Confidence.HIGH,
    )


def a3(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    dev = _device(ctx, frames)
    count = dev.shutter_count
    if count is None:
        return not_tested(spec, ctx, UNREADABLE)  # "unreadable", never 0
    rated = resolve_rated_life(ctx.kb)
    notes = plausibility_notes(count, _all_frames(frames), ctx.kb)
    fnd = [finding("count", "a3.count", count=count)] + [
        finding("plausibility", n.code, **n.params) for n in notes
    ]
    if rated.value is None:
        res = not_tested(spec, ctx, NO_REFERENCE)
        return res.model_copy(
            update={"findings": tuple(fnd), "explanation": msg("a3.count_only", count=count)}
        )
    life = float(rated.value)  # type: ignore[arg-type]
    share = count / life
    conf = rated.confidence_cap or Confidence.MEDIUM
    if share >= 1.0:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("a3.over_rated", count=count, share=f"{share:.0%}"),
            confidence=conf,
            severity=Severity.MEDIUM,
            findings=fnd,
        )
    if share >= ctx.params.get("count.rated_share_warn"):
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("a3.near_rated", count=count, share=f"{share:.0%}"),
            confidence=conf,
            severity=Severity.LOW,
            findings=fnd,
        )
    return make_result(
        spec,
        ctx,
        Level.PASS,
        msg("a3.within", count=count, share=f"{share:.0%}"),
        confidence=conf,
        findings=fnd,
    )


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def a4(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    dev = _device(ctx, frames)
    if not dev.firmware:
        return not_tested(spec, ctx, UNREADABLE)
    latest = ctx.kb.firmware_latest if ctx.kb else None
    if latest is None:
        return not_tested(spec, ctx, NO_REFERENCE)
    if _version_key(dev.firmware) < _version_key(latest.version):
        # Older firmware is a warning, not Suspect (TEST-CATALOGUE A4).
        return make_result(
            spec,
            ctx,
            Level.PASS,
            msg("a4.older", found=dev.firmware, latest=latest.version),
            confidence=Confidence.MEDIUM,
            findings=[finding("warning", "a4.older", found=dev.firmware, latest=latest.version)],
        )
    return make_result(
        spec, ctx, Level.PASS, msg("a4.current", version=dev.firmware), confidence=Confidence.MEDIUM
    )


def a5(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    dev = _device(ctx, frames)
    if not dev.storage:
        return not_tested(spec, ctx, UNREADABLE)
    bad = [s for s in dev.storage if s.startswith("!")]
    if bad:
        return make_result(
            spec,
            ctx,
            Level.SUSPECT,
            msg("a5.slot_fault", slot=bad[0].lstrip("!")),
            confidence=Confidence.MEDIUM,
            severity=Severity.MEDIUM,
        )
    return make_result(
        spec, ctx, Level.PASS, msg("a5.pass", count=len(dev.storage)), confidence=Confidence.HIGH
    )


def a6(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    dev = _device(ctx, frames)
    if not dev.lens:
        return not_tested(spec, ctx, UNREADABLE)
    return make_result(
        spec, ctx, Level.PASS, msg("a6.recorded", lens=dev.lens), confidence=Confidence.HIGH
    )


def manual_result(spec: CheckSpec, frames: FrameSet, ctx: CheckContext) -> CheckResult:
    """A manual check takes its result from the user's answer (FR-TST-07)."""
    return from_answer(spec, ctx)


A1 = FunctionCheck(make_spec("A1", "A", FROM_FIRST_FRAME, kb_fields=("model",)), a1)
A2 = FunctionCheck(make_spec("A2", "A", CONNECTED_AUTO), a2)
A3 = FunctionCheck(make_spec("A3", "A", FROM_FIRST_FRAME, kb_fields=("rated_life",)), a3)
A4 = FunctionCheck(make_spec("A4", "A", FROM_FIRST_FRAME, kb_fields=("firmware_latest",)), a4)
A5 = FunctionCheck(make_spec("A5", "A", CONNECTED_AUTO), a5)
A6 = FunctionCheck(make_spec("A6", "A", FROM_FIRST_FRAME), a6)
A7 = FunctionCheck(make_spec("A7", "A", MANUAL_BOTH), manual_result)

GROUP_A: tuple[Check, ...] = (A1, A2, A3, A4, A5, A6, A7)
_ = AUTO_OR_UPLOAD
