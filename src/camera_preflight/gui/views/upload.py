"""S8 Upload step: required settings, per-file validation with reasons (D-26, D-29, D-30)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import i18n
from ...domain import FrameRequirement, Level, Message
from ...wizard import StepDef
from ...wizard.ingest import IngestOutcome
from ..animations import SCENES, AnimationPanel
from ..controller import Controller
from ..i18n_helpers import tr
from ..labels import requirement_rows, requirement_title
from ..theme import Colors
from ..widgets.common import LevelBadge, ParamTable
from .base import StepView, tr_code

RAW_FILTER = "RAW (*.cr2 *.cr3 *.nef *.nrw *.arw *.dng)"


class _Card(QFrame):
    def __init__(self, view: UploadView, req: FrameRequirement) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.view, self.req = view, req
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(requirement_title(req))
        title.setObjectName("section")
        self.count = QLabel("")
        self.upload_btn = QPushButton(tr("Upload photos"))
        self.upload_btn.clicked.connect(self._choose)
        head.addWidget(title, 1)
        head.addWidget(self.count)
        head.addWidget(self.upload_btn)
        lay.addLayout(head)
        lay.addWidget(ParamTable(requirement_rows(req)))
        self.focus_row: QWidget | None = None
        if req.tag.startswith("af"):
            self._add_focus_buttons(lay)

    def _add_focus_buttons(self, lay: QVBoxLayout) -> None:
        """Tier 1 report: the user says whether the camera focused for each attempt (FR-TST-06)."""
        row = QHBoxLayout()
        ok = QPushButton(tr("Focused"))
        bad = QPushButton(tr("Did not focus"))
        point = self.req.tag.split(":", 1)[1]
        lens = 2 if self.req.tag.startswith("af2") else 1
        w = self.view.controller.wizard
        assert w is not None
        ok.clicked.connect(lambda: w.report_focus(point, lens))
        bad.clicked.connect(lambda: w.report_no_focus(point, lens))
        row.addWidget(ok)
        row.addWidget(bad)
        row.addStretch(1)
        lay.addLayout(row)

    def _choose(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, tr("Upload photos"), "", RAW_FILTER)
        if names:
            self.view.upload([Path(n) for n in names], self.req.key)

    def update_count(self, accepted: int) -> None:
        self.count.setText(f"{min(accepted, self.req.count)} / {self.req.count}")


class UploadView(StepView):
    def __init__(
        self, controller: Controller, colors: Colors, step: StepDef, parent: QWidget | None = None
    ) -> None:
        super().__init__(controller, colors, step, parent)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.anim = AnimationPanel()
        scene = SCENES.get(step.animation or "")
        if scene:
            self.anim.show_scene(scene)
        left.addWidget(self.anim, 1)
        body.addLayout(left, 1)
        host = QWidget()
        self.col = QVBoxLayout(host)
        self.cards: dict[str, _Card] = {}
        for req in step.requirements:
            card = _Card(self, req)
            self.cards[req.key] = card
            self.col.addWidget(card)
        self.files_box = QVBoxLayout()
        files_title = QLabel(tr("Uploaded files"))
        files_title.setObjectName("section")
        self.col.addWidget(files_title)
        self.col.addLayout(self.files_box)
        self.results_box = QVBoxLayout()
        results_title = QLabel(tr("Results"))
        results_title.setObjectName("section")
        self.col.addWidget(results_title)
        self.col.addLayout(self.results_box)
        self.col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        body.addWidget(scroll, 2)
        self.root.addLayout(body, 1)
        controller.outcomeReady.connect(self._on_outcome)
        controller.resultReady.connect(self._on_result)
        self.refresh()

    def upload(self, files: list[Path], key: str | None) -> None:
        self.controller.upload(files, self.step.id, key)

    def _on_result(self, _result: object) -> None:
        self.refresh()

    def _on_outcome(self, outcome: object) -> None:
        assert isinstance(outcome, IngestOutcome)
        row = QHBoxLayout()
        ok = outcome.accepted
        mark = QLabel("✓" if ok else "✕")
        mark.setStyleSheet(
            f"color:{self.colors.pass_ if ok else self.colors.fail}; font-weight:700;"
        )
        name = QLabel(outcome.file.name)
        reason = QLabel(
            i18n.render(outcome.rejection.message) if outcome.rejection else tr("Accepted")
        )
        reason.setObjectName("muted")
        row.addWidget(mark)
        row.addWidget(name, 1)
        row.addWidget(reason)
        host = QWidget()
        host.setLayout(row)
        self.files_box.addWidget(host)
        self.refresh()

    def refresh(self) -> None:
        w = self.controller.wizard
        if w is None:
            return
        for key, card in self.cards.items():
            card.update_count(sum(1 for f in w.frames.get(key, []) if f.accepted))
        while self.results_box.count():
            item = self.results_box.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()
        for cid in self.step.checks:
            r = w.results.get(cid)
            if r is None:
                continue
            row = QHBoxLayout()
            title = QLabel(f"{cid}  {tr_code(f'check.{cid}.title')}")
            row.addWidget(title, 1)
            row.addWidget(LevelBadge(r.level, self.colors))
            host = QWidget()
            host.setLayout(row)
            detail = QLabel(i18n.render(r.explanation))
            detail.setObjectName("muted")
            detail.setWordWrap(True)
            self.results_box.addWidget(host)
            self.results_box.addWidget(detail)

    def on_leave(self) -> None:
        self.anim.stop()
        _ = (Qt, QGridLayout, Level, Message)
