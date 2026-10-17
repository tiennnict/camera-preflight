"""S3 Blocker check and S9 Manual checks: look, then answer (D-35, FR-TST-07, FR-GUI-07)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...checks import ManualAnswer
from ...domain import Level
from ...i18n import N_
from ...wizard import StepDef
from ..animations import SCENES, AnimationPanel
from ..controller import Controller
from ..i18n_helpers import tr
from ..reference import photos_for
from ..theme import GLYPH, Colors
from ..widgets.common import ReferenceStrip, level_text
from .base import StepView, tr_code

BLOCKER_QUESTIONS = {
    "F1": N_("Does it power on normally?"),
    "F2": N_("Is it free of cracks and large dents?"),
    "F3": N_("Is the lens mount undamaged?"),
    "F4": N_("Does the mirror move freely?"),
}
_YES_NO = (
    (Level.PASS, N_("Yes")),
    (Level.FAIL, N_("No")),
    (Level.SUSPECT, N_("Not sure")),
)
_LEVELS = (Level.PASS, Level.SUSPECT, Level.FAIL, Level.NOT_TESTED)


class _Question(QWidget):
    """One check: a prompt, level buttons, a short note and an optional photo."""

    answered = Signal(str, object)

    def __init__(
        self,
        check_id: str,
        prompt: str,
        options: tuple[tuple[Level, str], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.check_id = check_id
        self.photo: str | None = None
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 4, 0, 4)
        label = QLabel(prompt)
        label.setObjectName("section")
        label.setWordWrap(True)
        col.addWidget(label)
        row = QHBoxLayout()
        self._buttons: dict[Level, QPushButton] = {}
        for level, text in options:
            b = QPushButton(f"{GLYPH[level]}  {text}")
            b.setCheckable(True)
            b.setAccessibleName(f"{prompt} {text}")
            self._group.addButton(b)
            b.clicked.connect(lambda _=False, lv=level: self._emit(lv))
            row.addWidget(b)
            self._buttons[level] = b
        row.addStretch(1)
        col.addLayout(row)
        self.note = QLineEdit()
        self.note.setPlaceholderText(tr("Note"))
        self.note.setMaxLength(200)
        self.photo_btn = QPushButton(tr("Attach photo"))
        self.photo_btn.clicked.connect(self._pick_photo)
        nrow = QHBoxLayout()
        nrow.addWidget(self.note, 1)
        nrow.addWidget(self.photo_btn)
        col.addLayout(nrow)
        self.note.editingFinished.connect(self._resubmit)

    def _emit(self, level: Level) -> None:
        self.current = level
        self.answered.emit(self.check_id, ManualAnswer(level, self.note.text(), self.photo))

    def _resubmit(self) -> None:
        for lv, b in self._buttons.items():
            if b.isChecked():
                self._emit(lv)

    def _pick_photo(self) -> None:
        name, _ = QFileDialog.getOpenFileName(
            self, tr("Attach photo"), "", tr("Images") + " (*.png *.jpg *.jpeg)"
        )
        if name:
            self.photo = name
            self.photo_btn.setText(Path(name).name)
            self._resubmit()

    def select(self, level: Level) -> None:
        if level in self._buttons:
            self._buttons[level].setChecked(True)


class ManualView(StepView):
    blockerFound = Signal()

    def __init__(
        self, controller: Controller, colors: Colors, step: StepDef, parent: QWidget | None = None
    ) -> None:
        super().__init__(controller, colors, step, parent)
        self.is_blocker = step.id == "blocker"
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.anim = AnimationPanel()
        scene = SCENES.get(step.animation or "")
        if scene:
            self.anim.show_scene(scene)
        left.addWidget(self.anim, 1)
        topic = step.checks[0]
        left.addWidget(ReferenceStrip(photos_for(topic)))
        body.addLayout(left, 1)
        host = QWidget()
        self.col = QVBoxLayout(host)
        self.questions: dict[str, _Question] = {}
        for cid in step.checks:
            if self.is_blocker:
                q = _Question(
                    cid, tr(BLOCKER_QUESTIONS[cid]), tuple((lv, tr(t)) for lv, t in _YES_NO)
                )
            else:
                q = _Question(
                    cid,
                    tr_code(f"check.{cid}.title"),
                    tuple((lv, level_text(lv)) for lv in _LEVELS),
                )
            q.answered.connect(self._on_answer)
            self.questions[cid] = q
            self.col.addWidget(q)
        self.col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        body.addWidget(scroll, 1)
        self.root.addLayout(body, 1)

    def _on_answer(self, check_id: str, answer: ManualAnswer) -> None:
        result = self.controller.answer(check_id, answer)
        if self.is_blocker and result.severity is not None and result.severity.value == "blocker":
            self.blockerFound.emit()

    def on_leave(self) -> None:
        self.anim.stop()
        _ = Qt
