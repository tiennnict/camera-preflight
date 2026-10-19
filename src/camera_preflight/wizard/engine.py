"""Wizard engine: UI-independent state, upload handling, checks and report (WP-30).

The engine knows nothing about Qt. The GUI and the CLI drive it and listen to its events.
No resume and no history (D-36): one engine instance is one session.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .. import __version__
from ..acquisition import ConnectedRunner
from ..backends.protocol import BackendError, CameraBackend
from ..checks import BY_ID, AfAttempt, CheckContext, ManualAnswer, checks_for, not_tested
from ..checks.base import REQUIRES_INSTRUMENT, SKIPPED
from ..checks.group_d import faulty_points, points_for
from ..domain import (
    DEFAULT_1,
    Camera,
    CheckResult,
    DeviceInfo,
    Frame,
    FrameRequirement,
    Level,
    Mode,
    ParameterSet,
    Phase,
    Session,
)
from ..gate import check_provenance
from ..io import MetadataReader, SessionFolder, default_reader
from ..knowledge import KnowledgeBase, ModelEntry, derive_record
from ..report import ReportData, SourceFile, render_report
from . import events as ev
from .ingest import IngestOutcome, ingest_file
from .plan import StepDef, build_plan

Listener = Callable[[ev.Event], None]


@dataclass
class StepState:
    step: StepDef
    done: bool = False
    skipped: bool = False
    uploads: int = 0


@dataclass
class Wizard:
    mode: Mode
    sessions_root: Path
    params: ParameterSet = DEFAULT_1
    kb: KnowledgeBase | None = None
    reader: MetadataReader | None = None
    entered_serial: str | None = None
    sdk_available: frozenset[str] = frozenset()
    language: str = "en"
    started: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self.reader = self.reader or default_reader()
        if self.kb is None:
            from ..knowledge import default_kb

            self.kb = default_kb()
        self.session = SessionFolder.create(self.sessions_root, self.started)
        self.plan: list[StepDef] = build_plan(self.mode, sdk_available=self.sdk_available)
        self.states: dict[str, StepState] = {s.id: StepState(s) for s in self.plan}
        self.index = 0
        self.frames: dict[str, list[Frame]] = {}
        self.all_frames: list[Frame] = []
        self.results: dict[str, CheckResult] = {}
        self.manual: dict[str, ManualAnswer] = {}
        self.af_attempts: dict[str, list[AfAttempt]] = {}
        self.af_attempts2: dict[str, list[AfAttempt]] = {}
        self.device = DeviceInfo()
        self.entry: ModelEntry | None = None
        self.camera = Camera()
        self._listeners: list[Listener] = []
        self.backend: CameraBackend
        self.runner: ConnectedRunner
        self._counter = 0

    # ---- observers -------------------------------------------------------------------
    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def _emit(self, event: ev.Event) -> None:
        for fn in list(self._listeners):
            fn(event)

    # ---- navigation ------------------------------------------------------------------
    @property
    def step(self) -> StepDef:
        return self.plan[self.index]

    def go_to(self, step_id: str) -> None:
        self.index = next(i for i, s in enumerate(self.plan) if s.id == step_id)
        self._emit(ev.StepChanged(step_id))

    def next(self) -> StepDef:
        if self.index < len(self.plan) - 1:
            self.index += 1
            self._emit(ev.StepChanged(self.step.id))
        return self.step

    def back(self) -> StepDef:
        if self.index > 0:
            self.index -= 1
            self._emit(ev.StepChanged(self.step.id))
        return self.step

    def steps_in(self, phase: Phase) -> list[StepDef]:
        return [s for s in self.plan if s.phase is phase]

    def switch_to_upload(self) -> None:
        """Connection lost or user choice: continue in upload mode, keeping what exists (S14)."""
        if self.mode is Mode.UPLOAD:
            return
        self.mode = Mode.UPLOAD
        self.plan = build_plan(self.mode, sdk_available=self.sdk_available)
        old = self.states
        self.states = {s.id: old.get(s.id, StepState(s)) for s in self.plan}
        for s in self.plan:
            self.states[s.id].step = s
        self._emit(ev.ModeChanged(self.mode.value))
        pending = next((i for i, s in enumerate(self.plan) if not self.is_done(s)), 0)
        self.index = pending
        self._emit(ev.StepChanged(self.step.id))

    # ---- status ------------------------------------------------------------------------
    def is_done(self, step: StepDef) -> bool:
        st = self.states[step.id]
        if st.skipped or st.done:
            return True
        return bool(step.checks) and all(c in self.results for c in step.checks)

    def status_of(self, check_id: str) -> str:
        r = self.results.get(check_id)
        return r.level.value if r else "waiting"

    # ---- context ------------------------------------------------------------------------
    def _accepted(self) -> list[Frame]:
        return [f for f in self.all_frames if f.accepted]

    def _lens_label(self, prefix: str) -> str:
        for key, fs in self.frames.items():
            if key.startswith(f"chart/{prefix}:"):
                for f in fs:
                    if f.accepted and f.meta.lens:
                        return f.meta.lens
        return ""

    def context(self) -> CheckContext:
        accepted = self._accepted()
        ctx = CheckContext(
            params=self.params,
            mode=self.mode,
            device=self.device,
            kb=self.entry,
            derived=derive_record(accepted, self.device),
            provenance=check_provenance(accepted, self.entered_serial),
            entered_serial=self.entered_serial,
            manual=dict(self.manual),
            af_attempts=dict(self.af_attempts),
            sdk_available=self.sdk_available,
            skipped=frozenset(c for s in self.states.values() if s.skipped for c in s.step.checks),
            evidence_dir=self.session.evidence_dir,
            lens_label=self.device.lens or "",
        )
        lens_a, lens_b = self._lens_label("af"), self._lens_label("af2")
        if lens_a and lens_b and lens_a != lens_b:
            ctx.af_by_lens = {
                lens_a: faulty_points(self.frames, ctx, self.af_attempts, "af"),
                lens_b: faulty_points(self.frames, ctx, self.af_attempts2, "af2"),
            }
        return ctx

    # ---- upload ---------------------------------------------------------------------------
    def reference_serial(self) -> str | None:
        if self.entered_serial:
            return self.entered_serial
        for f in self._accepted():
            if f.meta.serial:
                return f.meta.serial
        return None

    def upload(
        self,
        files: Sequence[Path],
        step_id: str | None = None,
        requirement_key: str | None = None,
    ) -> list[IngestOutcome]:
        """Validate and store the files the user chose for one step (FR-ACQ-01, FR-ACQ-02).

        ``requirement_key`` narrows the target to one part of the step, for example one AF point.
        """
        step = self.states[step_id].step if step_id else self.step
        reqs = step.requirements
        if requirement_key:
            reqs = tuple(r for r in reqs if r.key == requirement_key)
        outcomes: list[IngestOutcome] = []
        assert self.reader is not None
        for path in files:
            self._counter += 1
            outcome = ingest_file(
                path,
                self.session,
                self.reader,
                f"{self._counter:04d}",
                reqs,
                self.params,
                self.reference_serial(),
            )
            self._register(outcome)
            outcomes.append(outcome)
            self._emit(ev.FrameIngested(outcome))
        self.states[step.id].uploads += len(outcomes)
        if self._step_complete(step):
            self.run_step(step.id)
        self._persist()
        return outcomes

    def upload_for_checks(
        self, files: Sequence[Path], check_ids: Sequence[str]
    ) -> list[IngestOutcome]:
        """Command-line use: route files to the requirements of the chosen checks."""
        from .plan import requirements_of

        reqs = requirements_of(tuple(check_ids))
        assert self.reader is not None
        outcomes = []
        for path in files:
            self._counter += 1
            outcome = ingest_file(
                path,
                self.session,
                self.reader,
                f"{self._counter:04d}",
                reqs,
                self.params,
                self.reference_serial(),
            )
            self._register(outcome)
            outcomes.append(outcome)
            self._emit(ev.FrameIngested(outcome))
        self._persist()
        return outcomes

    # ---- connected mode ---------------------------------------------------------------------
    def use_backend(self, backend: CameraBackend, workdir: Path | None = None) -> None:
        """Attach an opened backend; the plan becomes the connected plan (FR-CON-01)."""
        self.backend = backend
        self.runner = ConnectedRunner(backend, self, ingest_file, workdir=workdir)
        info = backend.device_info()
        self.device = info
        self.camera = Camera(
            brand=info.brand,
            model=info.model,
            serial_read=info.serial,
            serial_entered=self.entered_serial,
            firmware=info.firmware,
            lens=info.lens,
            shutter_count_before=info.shutter_count,
        )
        if self.kb:
            self.entry = self.kb.find(info.brand, info.model)
        self.session.identify(info.model, info.serial)
        if self.mode is not Mode.CONNECTED:
            self.mode = Mode.CONNECTED
            self.plan = build_plan(self.mode, sdk_available=self.sdk_available)
            self.states = {s.id: StepState(s) for s in self.plan}
            self.index = 0
            self._emit(ev.ModeChanged(self.mode.value))
        self._emit(ev.DeviceIdentified(info.model or ""))

    def next_frame_id(self) -> str:
        self._counter += 1
        return f"{self._counter:04d}"

    def register(self, outcome: IngestOutcome) -> None:  # type: ignore[override]
        self._register(outcome)
        self._emit(ev.FrameIngested(outcome))

    def record_attempt(self, point: str, focused: bool, lens: int) -> None:
        store = self.af_attempts if lens == 1 else self.af_attempts2
        store.setdefault(point, []).append(AfAttempt(focused, "tethered"))

    def run_connected_step(
        self,
        step_id: str,
        *,
        manual_done: frozenset[str] = frozenset(),
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> list[CheckResult]:
        """Run one connected step: shoot what it needs, then its checks (D-25, D-34).

        Raises ``ManualFallback`` when a command fails twice; the caller shows the guided
        manual step and calls again with ``manual_done`` holding that requirement key.
        """
        step = self.states[step_id].step
        runner = self.runner
        if on_progress:
            runner.progress = on_progress
        if step_id == "auto":
            self._run_automatic(runner, manual_done)
        else:
            for req in step.requirements:
                have = sum(1 for f in self.frames.get(req.key, []) if f.accepted)
                if have >= req.count:
                    continue
                runner.run_requirement(req, manual_done=req.key in manual_done)
        results = self.run_checks(step.checks)
        self.states[step_id].done = True
        self._persist()
        return results

    def _run_automatic(self, runner: ConnectedRunner, manual_done: frozenset[str]) -> None:
        for req in step_requirements(self, "auto"):
            if req.key in manual_done:
                continue
            runner.run_requirement(req)
        self.device = self.backend.device_info()

    def finish_connected(self) -> bool:
        """Restore every camera setting the app changed and read the final shutter count."""
        ok = self.runner.restore()
        try:
            self.camera.shutter_count_after = self.backend.device_info().shutter_count
        except BackendError:
            pass
        return ok

    def add_frame(self, outcome: IngestOutcome) -> None:
        """Register a frame obtained by the connected backend (same path as an upload)."""
        self._register(outcome)
        self._emit(ev.FrameIngested(outcome))

    def _register(self, outcome: IngestOutcome) -> None:
        frame = outcome.frame
        self.all_frames.append(frame)
        if outcome.requirement_key:
            self.frames.setdefault(outcome.requirement_key, []).append(frame)
        if frame.accepted and not self.device.model:
            self._identify(frame)
        elif frame.accepted:
            self._merge_device(frame)
        if frame.accepted:
            self._update_shutter_counts()

    def _identify(self, frame: Frame) -> None:
        m = frame.meta
        self.device = DeviceInfo(
            brand=m.make,
            model=m.model,
            serial=m.serial,
            firmware=m.firmware,
            lens=m.lens,
            shutter_count=m.shutter_count,
            af_fine_tune=m.af_fine_tune,
        )
        if self.kb:
            self.entry = self.kb.find(m.make, m.model)
        self.session.identify(m.model, m.serial)
        self.camera = Camera(
            brand=m.make,
            model=m.model,
            serial_read=m.serial,
            serial_entered=self.entered_serial,
            firmware=m.firmware,
            lens=m.lens,
        )
        self._emit(ev.DeviceIdentified(m.model or ""))

    def _merge_device(self, frame: Frame) -> None:
        m, d = frame.meta, self.device
        self.device = d.model_copy(
            update={
                "serial": d.serial or m.serial,
                "firmware": d.firmware or m.firmware,
                "lens": d.lens or m.lens,
                "af_fine_tune": d.af_fine_tune if d.af_fine_tune is not None else m.af_fine_tune,
                "shutter_count": d.shutter_count
                if d.shutter_count is not None
                else m.shutter_count,
            }
        )

    def _update_shutter_counts(self) -> None:
        """Shutter count before and after the session, from the earliest and latest frames (D-37)."""
        temps = [f.meta.temperature_c for f in self._accepted() if f.meta.temperature_c is not None]
        if temps:
            self.camera.temperature_c = temps[
                -1
            ]  # recorded when the metadata exposes it (FR-META-05)
        counted = [(f.meta.capture_seconds(), f.meta.shutter_count) for f in self._accepted()]
        counted = [(t, n) for t, n in counted if t is not None and n is not None]
        if counted:
            counted.sort()
            if self.camera.shutter_count_before is None:
                self.camera.shutter_count_before = counted[0][1]
            self.camera.shutter_count_after = counted[-1][1]

    def report_no_focus(self, point: str, lens: int = 1) -> None:
        """The user pressed 'camera did not focus' for one attempt (tier 1, FR-TST-06)."""
        store = self.af_attempts if lens == 1 else self.af_attempts2
        store.setdefault(point, []).append(AfAttempt(False, "user"))

    def report_focus(self, point: str, lens: int = 1) -> None:
        store = self.af_attempts if lens == 1 else self.af_attempts2
        store.setdefault(point, []).append(AfAttempt(True, "user"))

    def _step_complete(self, step: StepDef) -> bool:
        if not step.requirements:
            return False
        for req in step.requirements:
            have = sum(1 for f in self.frames.get(req.key, []) if f.accepted)
            if have < req.count:
                return False
        return True

    # ---- checks ----------------------------------------------------------------------------
    def answer(self, check_id: str, answer: ManualAnswer) -> CheckResult:
        self.manual[check_id] = answer
        return self.run_checks([check_id])[0]

    def skip_step(self, step_id: str) -> None:
        st = self.states[step_id]
        st.skipped = True
        for cid in st.step.checks:
            self._store(not_tested(BY_ID[cid].spec, self.context(), SKIPPED))
        self._persist()

    def run_checks(self, check_ids: Sequence[str]) -> list[CheckResult]:
        ctx = self.context()
        out: list[CheckResult] = []
        for cid in check_ids:
            result = BY_ID[cid].analyse(self.frames, ctx)
            self._store(result)
            out.append(result)
        return out

    def run_step(self, step_id: str) -> list[CheckResult]:
        step = self.states[step_id].step
        results = self.run_checks(step.checks)
        self.states[step_id].done = True
        self._persist()
        return results

    def _store(self, result: CheckResult) -> None:
        self.results[result.check_id] = result
        self._emit(ev.ResultReady(result))

    def finalize(self) -> list[CheckResult]:
        """Final analysis of every check in the plan on all frames; adds C5 (never measured)."""
        ctx = self.context()
        ids: list[str] = []
        for s in self.plan:
            for cid in s.checks:
                if cid not in ids:
                    ids.append(cid)
        for check in checks_for(self.mode):
            if check.spec.id == "C5":
                ids.append("C5")
        for cid in ids:
            if cid == "C5":
                self._store(not_tested(BY_ID["C5"].spec, ctx, REQUIRES_INSTRUMENT))
            else:
                self._store(BY_ID[cid].analyse(self.frames, ctx))
        self._persist()
        self._emit(ev.Finished())
        return self.ordered_results()

    def ordered_results(self) -> list[CheckResult]:
        order = {c.spec.id: i for i, c in enumerate(checks_for(self.mode))}
        return sorted(self.results.values(), key=lambda r: order.get(r.check_id, 999))

    # ---- output ------------------------------------------------------------------------------
    def report_data(self, language: str | None = None) -> ReportData:
        ctx = self.context()
        issues = [(m.code, {k: str(v) for k, v in m.params.items()}) for m in ctx.provenance.issues]
        return ReportData(
            camera=self.camera,
            results=self.ordered_results(),
            parameters=self.params,
            app_version=__version__,
            kb_version="2026.1" if self.kb and self.kb.entries else "none",
            created=datetime.now(),
            sources=[SourceFile(f.id, f.source.name, f.sha256) for f in self.all_frames],
            evidence_dir=self.session.evidence_dir,
            session_issues=issues,
            known_issues=self.known_issue_notes(language),
        )

    def known_issue_notes(self, language: str | None = None) -> list[tuple[str, dict[str, str]]]:
        """Known issues of the curated entry that may concern this unit: a warning only, never a
        verdict (FR-VER-04). Issues the serial or firmware rules out are left out."""
        if self.entry is None:
            return []
        serial = self.camera.serial_read or self.camera.serial_entered
        notes: list[tuple[str, dict[str, str]]] = []
        for i in self.entry.known_issues:
            match = i.match(serial, self.camera.firmware)
            if match == "not_applicable":
                continue
            lang = language or self.language
            text = i.description_vi if lang == "vi" and i.description_vi else i.description
            if i.confidence.value == "low":
                code = "kb.reported_issue"  # owner reports, not a manufacturer notice
            elif match == "applies":
                code = "kb.known_issue"
            else:
                code = "kb.known_issue_maybe"
            params = {"description": text, "check": i.confirming_test}
            notes.append((code, params))
            if i.serviced_mark:
                notes.append(("kb.serviced_mark", {"mark": i.serviced_mark}))
        return notes

    def render_report(self, language: str | None = None) -> str:
        return render_report(self.report_data(language), language or self.language)

    def save_report(self, language: str | None = None, path: Path | None = None) -> Path:
        html = self.render_report(language)
        target = path or (self.session.path / "report.html")
        target.write_text(html, encoding="utf-8")
        return target

    def _persist(self) -> None:
        """Atomic writes after every check (ARCHITECTURE section 7)."""
        s = Session(
            id=self.session.path.name,
            started=self.started,
            mode=self.mode,
            camera=self.camera,
            app_version=__version__,
            parameter_set=self.params.id,
            results=self.ordered_results(),
        )
        self.session.write_json("session.json", s.model_dump(mode="json", exclude={"results"}))
        self.session.write_json("results.json", [r.model_dump(mode="json") for r in s.results])
        self.session.write_frames_index(self.all_frames)

    def close(self) -> None:
        if self.reader:
            self.reader.close()


__all__ = ["FrameRequirement", "Level", "StepState", "Wizard", "points_for"]


def step_requirements(wizard: Wizard, step_id: str) -> tuple[FrameRequirement, ...]:
    return wizard.states[step_id].step.requirements
