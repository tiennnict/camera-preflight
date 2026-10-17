"""Bridge between the wizard engine and Qt: worker threads and signals (NFR-04)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from ..checks import ManualAnswer
from ..domain import CheckResult, Mode
from ..io import MetadataReader
from ..knowledge import KnowledgeBase
from ..wizard import Wizard
from ..wizard import events as ev
from ..wizard.ingest import IngestOutcome


class _Job(QRunnable):
    def __init__(
        self, fn: Callable[[], Any], done: Callable[[Any], None], fail: Callable[[str], None]
    ) -> None:
        super().__init__()
        self._fn, self._done, self._fail = fn, done, fail

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            self._fail(str(exc) or exc.__class__.__name__)
        else:
            self._done(result)


class Controller(QObject):
    stepChanged = Signal(str)
    resultReady = Signal(object)
    outcomeReady = Signal(object)
    deviceIdentified = Signal(str)
    busyChanged = Signal(bool)
    modeChanged = Signal(str)
    finished = Signal()
    failed = Signal(str)
    jobDone = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.wizard: Wizard | None = None
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)  # the engine is not thread safe: one job at a time
        self._busy = 0

    # ---- session -------------------------------------------------------------------------
    def begin(
        self,
        mode: Mode,
        sessions_dir: Path,
        *,
        language: str,
        entered_serial: str | None,
        kb: KnowledgeBase | None = None,
        reader: MetadataReader | None = None,
        sdk_available: frozenset[str] = frozenset(),
    ) -> Wizard:
        if self.wizard:
            self.wizard.close()
        sessions_dir.mkdir(parents=True, exist_ok=True)
        self.wizard = Wizard(
            mode,
            sessions_dir,
            kb=kb,
            reader=reader,
            entered_serial=entered_serial or None,
            language=language,
            sdk_available=sdk_available,
        )
        self.wizard.subscribe(self._on_event)
        return self.wizard

    def _on_event(self, event: ev.Event) -> None:
        if isinstance(event, ev.StepChanged):
            self.stepChanged.emit(event.step_id)
        elif isinstance(event, ev.ResultReady):
            self.resultReady.emit(event.result)
        elif isinstance(event, ev.FrameIngested):
            self.outcomeReady.emit(event.outcome)
        elif isinstance(event, ev.DeviceIdentified):
            self.deviceIdentified.emit(event.model)
        elif isinstance(event, ev.ModeChanged):
            self.modeChanged.emit(event.mode)
        elif isinstance(event, ev.Finished):
            self.finished.emit()

    # ---- jobs ------------------------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._busy > 0

    def run_async(self, fn: Callable[[], Any]) -> None:
        self._busy += 1
        self.busyChanged.emit(True)
        job = _Job(fn, self._job_done, self._job_failed)
        self._pool.start(job)

    def _job_done(self, result: Any) -> None:
        self._busy -= 1
        if self._busy == 0:
            self.busyChanged.emit(False)
        self.jobDone.emit(result)

    def _job_failed(self, text: str) -> None:
        self._busy -= 1
        if self._busy == 0:
            self.busyChanged.emit(False)
        self.failed.emit(text)

    def wait(self, timeout_ms: int = 60000) -> bool:
        return self._pool.waitForDone(timeout_ms)

    # ---- actions -----------------------------------------------------------------------------
    def upload(self, files: Sequence[Path], step_id: str, requirement_key: str | None) -> None:
        w = self._require()
        self.run_async(lambda: w.upload(list(files), step_id, requirement_key))

    def finalize(self) -> None:
        w = self._require()
        self.run_async(w.finalize)

    def answer(self, check_id: str, answer: ManualAnswer) -> CheckResult:
        return self._require().answer(check_id, answer)

    def _require(self) -> Wizard:
        if self.wizard is None:
            raise RuntimeError("no session")
        return self.wizard

    def outcome_text(self, outcome: IngestOutcome) -> str:
        from .. import i18n

        return i18n.render(outcome.rejection.message) if outcome.rejection else ""
