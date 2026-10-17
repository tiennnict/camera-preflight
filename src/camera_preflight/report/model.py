"""Input of the report renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..domain import Camera, CheckResult, ParameterSet


@dataclass
class SourceFile:
    id: str
    name: str
    sha256: str


@dataclass
class ReportData:
    camera: Camera
    results: list[CheckResult]
    parameters: ParameterSet
    app_version: str
    kb_version: str = ""
    created: datetime = field(default_factory=datetime.now)
    sources: list[SourceFile] = field(default_factory=list)
    evidence_dir: Path | None = None
    session_issues: list[tuple[str, dict[str, str]]] = field(default_factory=list)
