"""Summary of results: counts per level, blockers first, no aggregate score (FR-VER-01, FR-VER-02)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..domain import CheckResult, Level, Message, Severity

_SEVERITY_RANK = {
    Severity.BLOCKER: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    None: 4,
}


@dataclass
class Summary:
    counts: dict[Level, int] = field(default_factory=dict)
    blockers: list[CheckResult] = field(default_factory=list)
    flagged: list[CheckResult] = field(default_factory=list)  # Suspect and Fail, worst first
    not_tested: list[CheckResult] = field(default_factory=list)


def summarise(results: Iterable[CheckResult]) -> Summary:
    items = list(results)
    out = Summary(counts={lv: 0 for lv in Level})
    for r in items:
        out.counts[r.level] += 1
    out.blockers = [r for r in items if r.severity is Severity.BLOCKER]
    out.flagged = sorted(
        (r for r in items if r.level in (Level.SUSPECT, Level.FAIL)),
        key=lambda r: (_SEVERITY_RANK[r.severity], r.level is not Level.FAIL, r.check_id),
    )
    out.not_tested = [r for r in items if r.level is Level.NOT_TESTED]
    return out


def seller_questions(results: Iterable[CheckResult]) -> list[Message]:
    """One question per flagged group, in plain neutral wording (FR-REP-03)."""
    groups: dict[str, list[str]] = {}
    for r in results:
        if r.level in (Level.SUSPECT, Level.FAIL):
            group = "".join(ch for ch in r.check_id if ch.isalpha())
            groups.setdefault(group, []).append(r.check_id)
    return [
        Message(code=f"ask.{g}", params={"checks": ", ".join(ids)})
        for g, ids in sorted(groups.items())
        if g in "ABCDEF"
    ]
