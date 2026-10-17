"""Connected mode screens: S2 detect, S4 automatic run, S5 to S7 semi-automatic (D-25, D-34).

The app shoots, changes settings and downloads by itself. The user only does what a cable
cannot: fit a cap, aim, change a lens. A helper watches for that action; a button takes over
when the helper cannot see it or the time limit passes.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import i18n
from ...acquisition import ManualFallback
from ...backends.protocol import Disconnected
from ...domain import AutomationLevel, Level, Message
from ...helpers import HelperParams, HelperWatcher
from ...i18n import N_
from ...wizard import StepDef
from ..animations import SCENES, AnimationPanel
from ..controller import Controller
from ..i18n_helpers import tr
from ..labels import requirement_title
from ..theme import Colors
from .base import StepView, tr_code

WAITING = {
    "H1": N_("Waiting for the body cap"),
    "H2": N_("Waiting for an even bright surface"),
    "H3": N_("Waiting for the focus chart"),
    "H4": N_("Waiting for a steady camera"),
    "H5": N_("Waiting for a lens change"),
    "H6": N_("Waiting for the focus mode"),
    "H7": N_("Waiting for a card"),
}
POLL_MS = 700


class LostDialog(QDialog):
    """S14: what happened, nothing lost, reconnect or switch to upload."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Connection lost"))
        lay = QVBoxLayout(self)
        title = QLabel(tr("Camera disconnected"))
        title.setObjectName("title")
        lay.addWidget(title)
        lay.addWidget(QLabel(tr("Results so far are kept.")))
        buttons = QDialogButtonBox()
        self.reconnect = buttons.addButton(tr("Reconnect"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.upload = buttons.addButton(
            tr("Use photo upload"), QDialogButtonBox.ButtonRole.RejectRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


class ConnectedStepView(StepView):
    connectionLost = Signal()
    finished = Signal()

    def __init__(
        self, controller: Controller, colors: Colors, step: StepDef, parent: QWidget | None = None
    ) -> None:
        super().__init__(controller, colors, step, parent)
        self.auto = step.automation is AutomationLevel.AUTOMATIC
        self.manual_done: set[str] = set()
        self.running = False
        self.fallback: ManualFallback | None = None
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.anim = AnimationPanel()
        scene = SCENES.get(step.animation or "")
        if scene:
            self.anim.show_scene(scene)
        left.addWidget(self.anim, 1)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        self.indicator = QLabel("")
        self.indicator.setObjectName("section")
        self.indicator.setWordWrap(True)
        self.button = QPushButton(tr("Done"))
        self.button.setObjectName("primary")
        self.button.clicked.connect(self._button_pressed)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.notice = QLabel("")
        self.notice.setObjectName("muted")
        self.notice.setWordWrap(True)
        right.addWidget(self.indicator)
        right.addWidget(self.button)
        right.addWidget(self.progress)
        right.addWidget(self.notice)
        self.rows: dict[str, QLabel] = {}
        self.badges: dict[str, QHBoxLayout] = {}
        self.list_box = QVBoxLayout()
        for cid in step.checks:
            row = QHBoxLayout()
            name = QLabel(f"{cid}  {tr_code(f'check.{cid}.title')}")
            status = QLabel(tr("Waiting"))
            status.setObjectName("muted")
            row.addWidget(name, 1)
            row.addWidget(status)
            host = QWidget()
            host.setLayout(row)
            self.list_box.addWidget(host)
            self.rows[cid] = status
        right.addLayout(self.list_box)
        right.addStretch(1)
        body.addLayout(right, 1)
        self.root.addLayout(body, 1)
        controller.resultReady.connect(self._on_result)
        controller.jobDone.connect(self._on_job_done)
        controller.failed.connect(self._on_failed)
        self.watcher: HelperWatcher | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self._tick)
        self._start_waiting()

    # ---- waiting for the user ------------------------------------------------------------------
    def _start_waiting(self) -> None:
        w = self.controller.wizard
        assert w is not None
        if self.auto:
            self.button.setVisible(False)
            self.indicator.setText(tr_code("step.auto.instruction"))
            self._run()
            return
        helper = self.step.helper or "H2"
        self.button.setVisible(False)
        self.indicator.setText(tr(WAITING[helper]))
        self.watcher = HelperWatcher(
            helper,
            w.backend,
            HelperParams(),
            initial_lens=w.device.lens,
            initial_storage=w.device.storage,
        )
        self._tick()
        self.timer.start()

    def _tick(self) -> None:
        if self.watcher is None or self.running:
            return
        try:
            st = self.watcher.poll()
        except Disconnected:
            self.timer.stop()
            self.connectionLost.emit()
            return
        if st.unavailable:
            self.indicator.setText(tr("Helper not available. Press Done."))
        if st.button_visible:
            self.button.setVisible(True)
        if st.detected:
            self.timer.stop()
            self.indicator.setText(tr("Detected. Running."))
            self._run()

    def _button_pressed(self) -> None:
        if self.fallback is not None:
            key = self.fallback.requirement_key
            self.manual_done.add(key)
            self.fallback = None
            self.button.setVisible(False)
            self._run()
        elif self.watcher is not None:
            self.watcher.press_button()
            self._tick()

    # ---- running --------------------------------------------------------------------------------
    def _run(self) -> None:
        w = self.controller.wizard
        assert w is not None
        self.running = True
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        done = frozenset(self.manual_done)
        self.controller.run_async(lambda: w.run_connected_step(self.step.id, manual_done=done))

    def _on_result(self, result: object) -> None:
        cid = getattr(result, "check_id", "")
        level = getattr(result, "level", None)
        if cid in self.rows and isinstance(level, Level):
            self.rows[cid].setText(f"{level.value}")
            self.rows[cid].setText(i18n.render(Message(code=f"level.{level.value}")))

    def _on_job_done(self, _result: object) -> None:
        if not self.running:
            return
        self.running = False
        self.progress.setVisible(False)
        self.notice.setText(tr("Finished. Next step starts."))
        self.finished.emit()

    def _on_failed(self, text: str) -> None:
        if not self.running:
            return
        self.running = False
        self.progress.setVisible(False)
        exc = self.controller.last_error
        if isinstance(exc, ManualFallback):
            self.fallback = exc
            self.indicator.setText(tr("Do this by hand, then press Done."))
            self.notice.setText(requirement_title_for(self.step, exc.requirement_key))
            self.button.setVisible(True)
        elif isinstance(exc, Disconnected):
            self.connectionLost.emit()
        else:
            self.notice.setText(text)

    def on_leave(self) -> None:
        self.timer.stop()
        self.anim.stop()


def requirement_title_for(step: StepDef, key: str) -> str:
    for req in step.requirements:
        if req.key == key:
            return requirement_title(req)
    return ""
