"""Events the wizard emits for the GUI and the CLI."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import CheckResult
from .ingest import IngestOutcome


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class StepChanged(Event):
    step_id: str


@dataclass(frozen=True)
class FrameIngested(Event):
    outcome: IngestOutcome


@dataclass(frozen=True)
class ResultReady(Event):
    result: CheckResult


@dataclass(frozen=True)
class ModeChanged(Event):
    mode: str


@dataclass(frozen=True)
class DeviceIdentified(Event):
    model: str


@dataclass(frozen=True)
class Finished(Event):
    pass
