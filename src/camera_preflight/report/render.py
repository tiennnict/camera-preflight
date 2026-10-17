"""Self-contained HTML report in the chosen language (FR-REP-02 to FR-REP-06, D-27, D-37)."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import i18n
from ..checks.verdict import seller_questions, summarise
from ..domain import CheckResult, Level, Message
from .labels import LABELS
from .model import ReportData

_TEMPLATES = Path(__file__).parent / "templates"
_GLYPH = {
    Level.PASS: "&#10003;",
    Level.SUSPECT: "<span>!</span>",
    Level.FAIL: "&#10005;",
    Level.NOT_TESTED: "&ndash;",
}
MAX_FINDINGS = 12


def _t(message: Message) -> str:
    return i18n.render(message)


def _level_name(level: Level) -> str:
    return _t(Message(code=f"level.{level.value}"))


def _check_view(r: CheckResult, data: ReportData) -> dict[str, object]:
    evidence = []
    for e in r.evidence:
        src = ""
        if data.evidence_dir is not None and (data.evidence_dir / e.path).exists():
            raw = (data.evidence_dir / e.path).read_bytes()
            src = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        evidence.append({"caption": _t(e.caption), "src": src})
    findings = [_t(f.message) for f in r.findings]
    return {
        "id": r.check_id,
        "title": _t(Message(code=f"check.{r.check_id}.title")),
        "key": r.level.value,
        "glyph": _GLYPH[r.level],
        "level": _level_name(r.level),
        "confidence": _t(Message(code=f"confidence.{r.confidence.value}")) if r.confidence else "",
        "severity": _t(Message(code=f"severity.{r.severity.value}")) if r.severity else "",
        "path": _t(Message(code=f"path.{r.path.value}")),
        "explanation": _t(r.explanation),
        "findings": findings[:MAX_FINDINGS],
        "more": max(len(findings) - MAX_FINDINGS, 0),
        "evidence": evidence,
        "reason": _t(r.explanation) if r.level is Level.NOT_TESTED else "",
    }


def render_report(data: ReportData, language: str | None = None) -> str:
    """Render the report; the previous UI language is restored afterwards."""
    previous = i18n.current_language()
    lang = i18n.set_language(language or previous)
    try:
        return _render(data, lang)
    finally:
        i18n.set_language(previous)


def _render(data: ReportData, lang: str) -> str:
    L = {k: i18n._(v) for k, v in LABELS.items()}
    summary = summarise(data.results)
    views = {r.check_id: _check_view(r, data) for r in data.results}
    cam = data.camera
    unknown = L["unknown"]

    def val(x: object | None) -> str:
        return str(x) if x not in (None, "") else unknown

    serial = (cam.serial_read or "")[-4:]
    rows = [
        (L["brand"], val(cam.brand)),
        (L["model"], val(cam.model)),
        (L["serial"], val(serial)),
        (L["firmware"], val(cam.firmware)),
        (L["lens"], val(cam.lens)),
        (L["count_before"], val(cam.shutter_count_before)),
        (L["count_after"], val(cam.shutter_count_after)),
    ]
    levels = [
        {"key": lv.value, "glyph": _GLYPH[lv], "name": _level_name(lv), "count": summary.counts[lv]}
        for lv in (Level.PASS, Level.SUSPECT, Level.FAIL, Level.NOT_TESTED)
    ]
    flagged_ids = {r.check_id for r in summary.flagged}
    blocker_ids = {r.check_id for r in summary.blockers}
    tested = [r for r in data.results if r.level is not Level.NOT_TESTED]
    evidence_hashes = []
    if data.evidence_dir is not None:
        for r in data.results:
            for e in r.evidence:
                p = data.evidence_dir / e.path
                if p.exists():
                    evidence_hashes.append(
                        {"name": e.path, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    )
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(
        lang=lang,
        L=L,
        created=data.created.strftime("%Y-%m-%d %H:%M"),
        camera_rows=rows,
        levels=levels,
        blockers=[views[r.check_id] for r in summary.blockers],
        flagged=[views[r.check_id] for r in summary.flagged if r.check_id not in blocker_ids],
        passed=[views[r.check_id] for r in tested if r.check_id not in flagged_ids | blocker_ids],
        not_tested=[views[r.check_id] for r in summary.not_tested],
        questions=[_t(q) for q in seller_questions(data.results)],
        session_issues=[_t(Message(code=c, params=p)) for c, p in data.session_issues],
        app_version=data.app_version,
        kb_version=data.kb_version,
        parameter_set=data.parameters.id,
        params=[
            {"name": p.name, "value": p.value, "label": L[f"label.{p.label.value}"]}
            for p in data.parameters.params
        ],
        sources=data.sources,
        evidence_hashes=evidence_hashes,
    )
