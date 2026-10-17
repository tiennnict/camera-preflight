"""Check framework: context, protocol and result helpers (FR-TST-01 to FR-TST-05, NFR-01)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..domain import (
    AutomationLevel,
    CheckResult,
    CheckSpec,
    Confidence,
    DeviceInfo,
    EvidenceRef,
    ExecPath,
    Finding,
    Frame,
    Level,
    Message,
    Mode,
    ParameterSet,
    Severity,
)
from ..gate import ProvenanceReport, lower
from ..knowledge import DerivedRecord, ModelEntry

FrameSet = Mapping[str, Sequence[Frame]]

# Reasons a check was not tested; resolved to text through ``reason.<code>``.
SKIPPED = "skipped_by_user"
SDK_NOT_CONFIGURED = "sdk_not_configured"
NO_REFERENCE = "no_reference_data"
INSUFFICIENT = "insufficient_frames"
UNREADABLE = "unreadable"
REQUIRES_INSTRUMENT = "requires_reference_instrument"
NOT_APPLICABLE = "not_applicable"
NOT_ANSWERED = "not_answered"
RESOLUTION_LOW = "timestamp_resolution_low"
NOT_SUPPORTED = "not_supported_by_backend"


@dataclass(frozen=True)
class ManualAnswer:
    level: Level
    notes: str = ""
    photo: str | None = None


@dataclass(frozen=True)
class AfAttempt:
    """One focus attempt at one AF point (D2)."""

    focused: bool
    source: str = "tethered"  # "tethered" (timeout or focus failure) or "user" (reported)


@dataclass
class CheckContext:
    params: ParameterSet
    mode: Mode
    device: DeviceInfo | None = None
    kb: ModelEntry | None = None
    derived: DerivedRecord | None = None
    provenance: ProvenanceReport = field(default_factory=ProvenanceReport)
    entered_serial: str | None = None
    manual: dict[str, ManualAnswer] = field(default_factory=dict)
    af_attempts: dict[str, list[AfAttempt]] = field(default_factory=dict)
    sdk_available: frozenset[str] = frozenset()
    sdk_data: dict[str, object] = field(default_factory=dict)
    skipped: frozenset[str] = frozenset()
    lens_label: str = ""
    af_by_lens: dict[str, set[str]] = field(default_factory=dict)
    evidence_dir: Path | None = None


class Check(Protocol):
    @property
    def spec(self) -> CheckSpec: ...

    def analyse(self, frames: FrameSet, ctx: CheckContext) -> CheckResult: ...


@dataclass(frozen=True)
class FunctionCheck:
    """A check built from a spec and an analysis function."""

    spec: CheckSpec
    fn: Callable[[CheckSpec, FrameSet, CheckContext], CheckResult]

    def analyse(self, frames: FrameSet, ctx: CheckContext) -> CheckResult:
        if self.spec.id in ctx.skipped:
            return not_tested(self.spec, ctx, SKIPPED)
        missing_sdk = self.spec.needs_sdk - ctx.sdk_available
        if self.spec.needs_sdk and missing_sdk == self.spec.needs_sdk:
            return not_tested(self.spec, ctx, SDK_NOT_CONFIGURED)
        return self.fn(self.spec, frames, ctx)


def exec_path(spec: CheckSpec, ctx: CheckContext) -> ExecPath:
    level = spec.automation.get(ctx.mode, AutomationLevel.MANUAL)
    return {
        AutomationLevel.AUTOMATIC: ExecPath.TETHERED,
        AutomationLevel.HELPER: ExecPath.SEMI_AUTOMATIC,
        AutomationLevel.BUTTON: ExecPath.SEMI_AUTOMATIC,
        AutomationLevel.UPLOAD: ExecPath.FILE_IMPORT,
        AutomationLevel.MANUAL: ExecPath.MANUAL,
    }[level]


def not_tested(spec: CheckSpec, ctx: CheckContext, reason: str) -> CheckResult:
    """Never Pass (NFR-01, FR-TST-03)."""
    return CheckResult(
        check_id=spec.id,
        level=Level.NOT_TESTED,
        path=exec_path(spec, ctx),
        explanation=Message(code=f"reason.{reason}"),
        not_tested_reason=reason,
        parameters=ctx.params.id,
    )


def make_result(
    spec: CheckSpec,
    ctx: CheckContext,
    level: Level,
    explanation: Message,
    *,
    confidence: Confidence = Confidence.MEDIUM,
    severity: Severity | None = None,
    findings: Sequence[Finding] = (),
    evidence: Sequence[EvidenceRef] = (),
    cap_confidence: bool = True,
) -> CheckResult:
    """Build a result; provenance problems lower the confidence (FR-GATE-07)."""
    if level is Level.NOT_TESTED:
        raise ValueError("use not_tested()")
    if level in (Level.SUSPECT, Level.FAIL) and severity is None:
        severity = Severity.MEDIUM
    if level in (Level.PASS,):
        severity = None
    final = lower(confidence, ctx.provenance.confidence_cap) if cap_confidence else confidence
    return CheckResult(
        check_id=spec.id,
        level=level,
        confidence=final,
        severity=severity,
        path=exec_path(spec, ctx),
        findings=tuple(findings),
        evidence=tuple(evidence),
        parameters=ctx.params.id,
        explanation=explanation,
    )


def frames_of(frames: FrameSet, key: str) -> list[Frame]:
    """Accepted frames for a requirement key."""
    return [f for f in frames.get(key, ()) if f.accepted and f.cfa is not None]


def msg(code: str, **params: object) -> Message:
    return Message(code=code, params=dict(params))


def finding(kind: str, code: str, **data: object) -> Finding:
    return Finding(
        kind=kind,
        message=Message(code=code, params={k: str(v) for k, v in data.items()}),
        data={k: v for k, v in data.items()},
    )
