"""Results of manual checks come from the user's answer (FR-TST-07)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ..domain import (
    CheckResult,
    CheckSpec,
    Confidence,
    EvidenceRef,
    Finding,
    Level,
    Message,
    Severity,
)
from .base import NOT_ANSWERED, CheckContext, make_result, not_tested

BLOCKER_IDS = frozenset({"F1", "F2", "F3", "F4"})


def from_answer(spec: CheckSpec, ctx: CheckContext) -> CheckResult:
    answer = ctx.manual.get(spec.id)
    if answer is None or answer.level is Level.NOT_TESTED:
        return not_tested(spec, ctx, NOT_ANSWERED)
    severity: Severity | None = None
    if answer.level in (Level.SUSPECT, Level.FAIL):
        if spec.id in BLOCKER_IDS:
            severity = Severity.BLOCKER
        elif answer.level is Level.FAIL:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM
    findings = []
    if answer.notes:
        findings.append(
            Finding(kind="note", message=Message(code="manual.note", params={"text": answer.notes}))
        )
    evidence: list[EvidenceRef] = []
    if answer.photo and ctx.evidence_dir is not None:
        src = Path(answer.photo)
        if src.is_file():
            ctx.evidence_dir.mkdir(parents=True, exist_ok=True)
            dest = ctx.evidence_dir / f"{spec.id}-photo{src.suffix.lower()}"
            shutil.copyfile(src, dest)
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            evidence.append(
                EvidenceRef(
                    path=dest.name, caption=Message(code="evidence.manual_photo"), sha256=digest
                )
            )
    return make_result(
        spec,
        ctx,
        answer.level,
        Message(code=f"manual.{answer.level.value}"),
        confidence=Confidence.MEDIUM,
        severity=severity,
        findings=findings,
        evidence=evidence,
        cap_confidence=False,
    )
