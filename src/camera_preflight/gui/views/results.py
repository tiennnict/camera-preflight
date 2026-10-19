"""S10 Results, S11 Check detail, S12 Report (FR-REP-03, D-27)."""

from __future__ import annotations

import shutil

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import i18n
from ...checks.verdict import summarise
from ...domain import CheckResult, Level, Message
from ...wizard import StepDef, Wizard
from ..controller import Controller
from ..i18n_helpers import tr
from ..theme import Colors
from ..widgets.common import LevelBadge, ParamTable
from .base import StepView, tr_code


def _msg(code: str) -> str:
    return i18n.render(Message(code=code))


class DetailDialog(QDialog):
    """S11: explanation, evidence, method and thresholds for one check."""

    def __init__(
        self,
        controller: Controller,
        colors: Colors,
        result: CheckResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{result.check_id}  {tr_code(f'check.{result.check_id}.title')}")
        self.resize(640, 640)
        w = controller.wizard
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        title = QLabel(f"{result.check_id}  {tr_code(f'check.{result.check_id}.title')}")
        title.setObjectName("title")
        head.addWidget(title, 1)
        head.addWidget(LevelBadge(result.level, colors))
        lay.addLayout(head)
        rows: list[tuple[str, str]] = []
        if result.confidence:
            rows.append((tr("Confidence"), _msg(f"confidence.{result.confidence.value}")))
        if result.severity:
            rows.append((tr("Severity"), _msg(f"severity.{result.severity.value}")))
        rows.append((tr("Path"), _msg(f"path.{result.path.value}")))
        lay.addWidget(ParamTable(rows))
        text = QLabel(i18n.render(result.explanation))
        text.setWordWrap(True)
        lay.addWidget(text)
        host = QWidget()
        col = QVBoxLayout(host)
        if result.findings:
            col.addWidget(self._section(tr("Details")))
            for f in result.findings[:40]:
                item = QLabel("• " + i18n.render(f.message))
                item.setWordWrap(True)
                col.addWidget(item)
        if w is not None:
            for e in result.evidence:
                p = w.session.evidence_dir / e.path
                if p.exists():
                    col.addWidget(self._section(i18n.render(e.caption)))
                    img = QLabel()
                    img.setPixmap(
                        QPixmap(str(p)).scaledToWidth(
                            560, Qt.TransformationMode.SmoothTransformation
                        )
                    )
                    col.addWidget(img)
            col.addWidget(self._section(tr("Method")))
            prefix = result.check_id.lower() + "."
            params = [p for p in w.params.params if p.name.startswith(prefix)]
            col.addWidget(ParamTable([(tr("Parameter set"), w.params.id)]))
            if params:
                col.addWidget(
                    ParamTable([(p.name, f"{p.value}  ({tr(p.label.value)})") for p in params])
                )
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Close"))
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label


class ResultsView(StepView):
    def __init__(
        self, controller: Controller, colors: Colors, step: StepDef, parent: QWidget | None = None
    ) -> None:
        super().__init__(controller, colors, step, parent)
        self.status = QLabel(tr("Analysing"))
        self.status.setObjectName("muted")
        self.root.addWidget(self.status)
        self.host = QWidget()
        self.body = QVBoxLayout(self.host)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.host)
        self.root.addWidget(scroll, 1)
        self.report_lang = QComboBox()
        self.report_lang.addItem("English", "en")
        self.report_lang.addItem("Tiếng Việt", "vi")
        self.report_lang.setCurrentIndex(0 if i18n.current_language() == "en" else 1)
        self.save_btn = QPushButton(tr("Save report"))
        self.save_btn.setObjectName("primary")
        self.open_btn = QPushButton(tr("Open report"))
        self.save_btn.clicked.connect(self.save_report)
        self.open_btn.clicked.connect(self.open_report)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Report language")))
        row.addWidget(self.report_lang)
        row.addStretch(1)
        row.addWidget(self.open_btn)
        row.addWidget(self.save_btn)
        self.root.addLayout(row)
        self._set_buttons(False)
        controller.finished.connect(self.populate)
        self._started = False
        self.restored: bool | None = None

    def _set_buttons(self, enabled: bool) -> None:
        self.save_btn.setEnabled(enabled)
        self.open_btn.setEnabled(enabled)

    def start(self) -> None:
        """Run the final analysis once when the user reaches this step."""
        if self._started:
            return
        self._started = True
        w = self.controller.wizard
        assert w is not None
        if w.mode.value == "connected":
            self.controller.run_async(self._finish_connected)
        else:
            self.controller.finalize()

    def _finish_connected(self) -> bool:
        """Restore the camera settings the app changed, then run the final analysis (FR-ACQ-06)."""
        w = self.controller.wizard
        assert w is not None
        restored = w.finish_connected()
        w.finalize()
        self.restored = restored
        return restored

    def populate(self) -> None:
        w = self.controller.wizard
        if w is None:
            return
        if self.restored is None:
            self.status.setText("")
        else:
            self.status.setText(
                tr("Camera settings restored")
                if self.restored
                else tr("Camera settings not restored")
            )
        while self.body.count():
            item = self.body.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()
        summary = summarise(w.ordered_results())
        counts = QHBoxLayout()
        for lv in (Level.PASS, Level.SUSPECT, Level.FAIL, Level.NOT_TESTED):
            box = QFrame()
            box.setObjectName("panel")
            box.setMinimumHeight(80)
            col = QVBoxLayout(box)
            col.addWidget(LevelBadge(lv, self.colors))
            num = QLabel(str(summary.counts[lv]))
            num.setStyleSheet("font-size:26px; font-weight:600;")
            col.addWidget(num)
            counts.addWidget(box)
        host = QWidget()
        host.setLayout(counts)
        self.body.addWidget(host)
        self._known_issues(w)
        self._section(tr("Blockers"), summary.blockers)
        blocker_ids = {r.check_id for r in summary.blockers}
        self._section(
            tr("Suspect and fail results"),
            [r for r in summary.flagged if r.check_id not in blocker_ids],
        )
        self._section(tr("Not tested"), summary.not_tested, reasons=True)
        passed = [r for r in w.ordered_results() if r.level is Level.PASS]
        self._section(tr("Passed"), passed)
        self.body.addStretch(1)
        self._set_buttons(True)

    def _known_issues(self, w: Wizard) -> None:
        """Documented faults of this model to look at; a warning, never a verdict (FR-VER-04)."""
        notes = w.known_issue_notes(i18n.current_language())
        if not notes:
            return
        label = QLabel(tr("Known issues of this model"))
        label.setObjectName("section")
        self.body.addWidget(label)
        for code, params in notes:
            text = QLabel(i18n.render(Message(code=code, params=params)))
            text.setWordWrap(True)
            self.body.addWidget(text)

    def _section(self, title: str, results: list[CheckResult], reasons: bool = False) -> None:
        if not results:
            return
        label = QLabel(title)
        label.setObjectName("section")
        self.body.addWidget(label)
        for r in results:
            box = QFrame()
            box.setObjectName("panel")
            box.setMinimumHeight(54)
            lay = QHBoxLayout(box)
            name = QLabel(f"{r.check_id}  {tr_code(f'check.{r.check_id}.title')}")
            name.setMinimumWidth(220)
            lay.addWidget(name)
            lay.addWidget(LevelBadge(r.level, self.colors))
            why = QLabel(i18n.render(r.explanation))
            why.setObjectName("muted")
            why.setWordWrap(True)
            lay.addWidget(why, 1)
            if r.confidence:
                lay.addWidget(QLabel(_msg(f"confidence.{r.confidence.value}")))
            btn = QPushButton(tr("Details"))
            btn.clicked.connect(
                lambda _=False, res=r: DetailDialog(self.controller, self.colors, res, self).exec()
            )
            lay.addWidget(btn)
            self.body.addWidget(box)
        _ = reasons

    def _render(self) -> str | None:
        w = self.controller.wizard
        if w is None:
            return None
        lang = str(self.report_lang.currentData())
        return str(w.save_report(lang))

    def save_report(self) -> None:
        path = self._render()
        if not path:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, tr("Save report"), "report.html", "HTML (*.html)"
        )
        if target:
            shutil.copyfile(path, target)

    def open_report(self) -> None:
        path = self._render()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
