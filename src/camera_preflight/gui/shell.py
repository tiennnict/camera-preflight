"""Main window: top bar, checklist, step views and bottom bar (UX section 4, D-49)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..domain import AutomationLevel, CheckResult, Level, Message, Mode, Phase
from ..wizard import StepDef
from . import settings as store
from .controller import Controller
from .i18n_helpers import tr
from .settings import UserSettings
from .theme import GLYPH, Colors, apply_theme, level_color
from .views.about import AboutDialog
from .views.base import StepView, tr_code
from .views.connected import ConnectedStepView, LostDialog
from .views.manual import ManualView
from .views.results import ResultsView
from .views.settings_dialogs import SettingsDialog
from .views.start import StartView
from .views.upload import UploadView
from .widgets.common import level_text


class _Bridge(QObject):
    """Carries a worker thread's result to the GUI thread."""

    detected = Signal(object)


_ORDER = {Level.NOT_TESTED: 0, Level.PASS: 1, Level.SUSPECT: 2, Level.FAIL: 3}


class MainWindow(QMainWindow):
    def __init__(
        self, settings: UserSettings, controller: Controller | None = None, settings_store=None
    ) -> None:  # type: ignore[no-untyped-def]
        super().__init__()
        self.settings = settings
        self._store = settings_store
        self.controller = controller or Controller(self)
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        self.colors: Colors = apply_theme(app)
        self.resize(1180, 760)
        self.view: StepView | None = None
        self._detecting = False
        self._bridge = _Bridge(self)
        self._bridge.detected.connect(self._on_detected)
        self._build()
        self.controller.resultReady.connect(self._on_result)
        self.controller.deviceIdentified.connect(self._on_device)
        self.controller.failed.connect(self._on_failed)
        self.controller.modeChanged.connect(lambda _m: self._rebuild_tree())
        self.show_home()

    # ---- layout ----------------------------------------------------------------------------
    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # top bar
        bar = QWidget()
        bar.setObjectName("panel")
        top = QHBoxLayout(bar)
        self.app_label = QLabel("camera-preflight")
        self.app_label.setObjectName("section")
        self.camera_label = QLabel("")
        self.mode_label = QLabel("")
        self.mode_label.setObjectName("muted")
        self.lang_box = QComboBox()
        self.lang_box.addItem("English", "en")
        self.lang_box.addItem("Tiếng Việt", "vi")
        self.lang_box.setCurrentIndex(0 if i18n.current_language() == "en" else 1)
        self.lang_box.currentIndexChanged.connect(self._language_changed)
        self.lang_box.setAccessibleName(tr("Language"))
        self.settings_btn = QPushButton(tr("Settings"))
        self.settings_btn.clicked.connect(self.open_settings)
        self.about_btn = QPushButton(tr("About"))
        self.about_btn.clicked.connect(lambda: AboutDialog(self).exec())
        top.addWidget(self.app_label)
        top.addWidget(self.camera_label, 1)
        top.addWidget(self.mode_label)
        top.addWidget(self.lang_box)
        top.addWidget(self.settings_btn)
        top.addWidget(self.about_btn)
        outer.addWidget(bar)
        # body
        split = QSplitter()
        # One flat checklist: no phase groups and no automation labels (D-49).
        self.tree = QListWidget()
        self.tree.setMinimumWidth(240)
        self.tree.setAccessibleName(tr("Checklist"))
        self.tree.itemActivated.connect(self._tree_clicked)
        self.tree.itemClicked.connect(self._tree_clicked)
        self.stack = QStackedWidget()
        split.addWidget(self.tree)
        split.addWidget(self.stack)
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)
        # bottom bar
        foot = QWidget()
        foot.setObjectName("panel")
        bottom = QHBoxLayout(foot)
        self.back_btn = QPushButton(tr("Back"))
        self.skip_btn = QPushButton(tr("Skip"))
        self.next_btn = QPushButton(tr("Next"))
        self.next_btn.setObjectName("primary")
        self.busy_label = QLabel("")
        self.busy_label.setObjectName("muted")
        self.back_btn.clicked.connect(self.go_back)
        self.skip_btn.clicked.connect(self.skip_current)
        self.next_btn.clicked.connect(self.go_next)
        bottom.addWidget(self.back_btn)
        bottom.addWidget(self.busy_label, 1)
        bottom.addWidget(self.skip_btn)
        bottom.addWidget(self.next_btn)
        outer.addWidget(foot)
        self.controller.busyChanged.connect(
            lambda b: self.busy_label.setText(tr("Working") if b else "")
        )
        self._apply_text()

    def _apply_text(self) -> None:
        self.setWindowTitle(tr("Camera check"))
        self.settings_btn.setText(tr("Settings"))
        self.about_btn.setText(tr("About"))
        self.back_btn.setText(tr("Back"))
        self.skip_btn.setText(tr("Skip"))
        self.next_btn.setText(tr("Next"))
        self.mode_label.setText(self._mode_text())

    def _mode_text(self) -> str:
        w = self.controller.wizard
        if w is None:
            return ""
        return i18n.render(Message(code=f"mode.{w.mode.value}"))

    # ---- navigation ------------------------------------------------------------------------
    def show_home(self) -> None:
        self.controller.wizard = None
        self.tree.clear()
        self.camera_label.setText("")
        self._clear_view()
        from ..wizard import build_plan

        home = build_plan(Mode.UPLOAD)[0]
        view = StartView(self.controller, self.colors, home)
        view.startRequested.connect(self.start_session)
        view.demoRequested.connect(lambda serial: self.start_session(serial, demo=True))
        view.settingsRequested.connect(self.open_settings)
        self._set_view(view)
        for b in (self.back_btn, self.skip_btn, self.next_btn):
            b.setEnabled(False)
        self.mode_label.setText("")

    def _sdk_available(self) -> frozenset[str]:
        return frozenset(
            b.lower()
            for b, p in ((b, self.settings.sdk_path(b)) for b in store.BRANDS)
            if p.is_dir() and any(p.iterdir())
        )

    def start_session(self, serial: str, demo: bool = False) -> None:
        """Detect a camera: connected mode when found, upload mode otherwise (D-23).

        Detection and opening the camera run on a worker thread; the window stays responsive.
        """
        if self._detecting:
            return
        import tempfile

        self._detecting = True
        self.busy_label.setText(tr("Looking for camera"))
        if isinstance(self.view, StartView):
            self.view.set_busy(True)
        work = Path(tempfile.mkdtemp(prefix="cp-cam-"))
        sdk_dirs = {b.lower(): self.settings.sdk_path(b) for b in store.BRANDS}

        def job() -> None:
            from ..backends.client import BackendClient
            from ..backends.discovery import DetectResult, detect
            from ..backends.protocol import BackendError

            client = None
            try:
                found = detect(prefer="sim" if demo else None, workdir=work, sdk_dirs=sdk_dirs)
                if found.found and found.spec:
                    client = BackendClient(found.spec, sdk_dir=found.sdk_dir, workdir=work)
                    try:
                        client.open()
                    except BackendError:
                        client.close()
                        client = None
                        found = DetectResult(
                            False, hint_code="detect.failed", seen_brand=found.brand
                        )
            except Exception:
                found = DetectResult(False)
            self._bridge.detected.emit((serial, demo, work, found, client))

        threading.Thread(target=job, daemon=True).start()

    def _on_detected(self, payload: object) -> None:
        serial, demo, work, found, client = payload  # type: ignore[misc]
        self._detecting = False
        self.busy_label.setText("")
        if isinstance(self.view, StartView):
            self.view.set_busy(False)
        sdk = self._sdk_available()
        if client is not None:
            self.controller.begin_connected(
                found.spec,
                self.settings.sessions_path(),
                language=i18n.current_language(),
                entered_serial=serial,
                workdir=work,
                sdk_available=sdk,
                client=client,
            )
            self.camera_label.setText(found.camera)
        else:
            if not demo and found.seen_brand and not self._ask_upload(found):
                return
            self.controller.begin(
                Mode.UPLOAD,
                self.settings.sessions_path(),
                language=i18n.current_language(),
                entered_serial=serial,
                sdk_available=sdk,
            )
        self._rebuild_tree()
        self._apply_text()
        self.show_step("blocker")

    def _ask_upload(self, found: object) -> bool:
        """A camera is on USB but cannot be controlled. True: continue with photo upload."""
        brand = str(getattr(found, "seen_brand", "")).capitalize()
        no_sdk = getattr(found, "hint_code", "") == "detect.no_sdk"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("Camera found"))
        if no_sdk:
            box.setText(
                tr("{brand} camera found. Set its SDK folder to control it.").format(brand=brand)
            )
            retry = box.addButton(tr("Settings"), QMessageBox.ButtonRole.ActionRole)
        else:
            box.setText(
                tr(
                    "Cannot control the {brand} camera. Close other camera apps and try again."
                ).format(brand=brand)
            )
            retry = box.addButton(tr("Try again"), QMessageBox.ButtonRole.ActionRole)
        upload = box.addButton(tr("Use photo upload"), QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(retry)
        box.exec()
        if box.clickedButton() is upload:
            return True
        if no_sdk:
            self.open_settings()
        return False

    def _rebuild_tree(self) -> None:
        w = self.controller.wizard
        self.tree.clear()
        if w is None:
            return
        self._items: dict[str, QListWidgetItem] = {}
        for step in w.plan:
            if step.phase is Phase.START:
                continue
            item = QListWidgetItem("")
            item.setData(Qt.ItemDataRole.UserRole, step.id)
            self.tree.addItem(item)
            self._items[step.id] = item
            self._update_item(step)
        self._mark_current()
        self._apply_text()

    def _update_item(self, step: StepDef) -> None:
        w = self.controller.wizard
        item = self._items.get(step.id)
        if w is None or item is None:
            return
        results = [w.results[c] for c in step.checks if c in w.results]
        glyph = "·"
        color = self.colors.muted
        if results and len(results) == len(step.checks):
            worst = max((r.level for r in results), key=lambda lv: _ORDER[lv])
            glyph = GLYPH[worst]
            color = level_color(self.colors, worst)
            item.setToolTip(level_text(worst))
        item.setText(f"{glyph}  {tr_code(step.title_code)}")
        from PySide6.QtGui import QBrush, QColor

        item.setForeground(QBrush(QColor(color)))

    def _mark_current(self) -> None:
        w = self.controller.wizard
        if w is None:
            return
        item = self._items.get(w.step.id)
        if item:
            self.tree.setCurrentItem(item)

    def _tree_clicked(self, item: QListWidgetItem) -> None:
        step_id = item.data(Qt.ItemDataRole.UserRole)
        if step_id and self.controller.wizard:
            self.show_step(str(step_id))

    def show_step(self, step_id: str) -> None:
        w = self.controller.wizard
        if w is None:
            return
        if self.view is not None:
            self.view.on_leave()
        w.go_to(step_id)
        step = w.step
        self._clear_view()
        if step.phase is Phase.RESULTS:
            view: StepView = ResultsView(self.controller, self.colors, step)
        elif step.phase in (Phase.BLOCKER, Phase.MANUAL):
            view = ManualView(self.controller, self.colors, step)
            if step.phase is Phase.BLOCKER:
                view.blockerFound.connect(self._blocker_found)  # type: ignore[attr-defined]
        elif w.mode is Mode.CONNECTED and step.automation in (
            AutomationLevel.AUTOMATIC,
            AutomationLevel.HELPER,
        ):
            view = ConnectedStepView(self.controller, self.colors, step)
            view.connectionLost.connect(self._connection_lost)  # type: ignore[attr-defined]
            view.finished.connect(self._auto_advance)  # type: ignore[attr-defined]
        elif step.is_shooting:
            view = UploadView(self.controller, self.colors, step)
        else:
            view = ManualView(self.controller, self.colors, step)
        self._set_view(view)
        self._mark_current()
        index = w.index
        self.back_btn.setEnabled(index > 1)
        is_last = step.phase is Phase.RESULTS
        self.skip_btn.setEnabled(not is_last and bool(step.checks))
        self.next_btn.setEnabled(not is_last)
        if isinstance(view, ResultsView):
            view.start()

    def _set_view(self, view: StepView) -> None:
        self.view = view
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)

    def _clear_view(self) -> None:
        while self.stack.count():
            w = self.stack.widget(0)
            if w is None:
                break
            self.stack.removeWidget(w)
            w.deleteLater()
        self.view = None

    def go_next(self) -> None:
        w = self.controller.wizard
        if w is None:
            return
        if w.index < len(w.plan) - 1:
            self.show_step(w.plan[w.index + 1].id)

    def go_back(self) -> None:
        w = self.controller.wizard
        if w is not None and w.index > 1:
            self.show_step(w.plan[w.index - 1].id)

    def skip_current(self) -> None:
        w = self.controller.wizard
        if w is None:
            return
        w.skip_step(w.step.id)
        self.go_next()

    def _auto_advance(self) -> None:
        """After an automatic or helper-started run the next step begins by itself (S4)."""
        w = self.controller.wizard
        if w is None:
            return
        current = w.step.id
        QTimer.singleShot(1200, lambda: self._advance_if_still(current))

    def _advance_if_still(self, step_id: str) -> None:
        w = self.controller.wizard
        if w is not None and w.step.id == step_id:
            self.go_next()

    def _connection_lost(self) -> None:
        dlg = LostDialog(self)
        if dlg.exec():
            w = self.controller.wizard
            if w is not None:
                self.show_step(w.step.id)  # try the same step again
        else:
            w = self.controller.wizard
            if w is not None:
                w.switch_to_upload()
                self._rebuild_tree()
                self._apply_text()
                self.show_step(w.step.id)

    def _blocker_found(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(tr("Severe problem"))
        box.setText(tr("A severe problem was found."))
        stop = box.addButton(tr("Stop and save report"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Continue"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is stop:
            self.show_step("results")

    # ---- events ---------------------------------------------------------------------------
    def _on_result(self, result: object) -> None:
        assert isinstance(result, CheckResult)
        w = self.controller.wizard
        if w is None:
            return
        for step in w.plan:
            if result.check_id in step.checks:
                self._update_item(step)

    def _on_device(self, model: str) -> None:
        self.camera_label.setText(model)

    def _on_failed(self, text: str) -> None:
        QMessageBox.warning(self, tr("Something went wrong"), text)

    # ---- settings and language ----------------------------------------------------------------
    def _language_changed(self) -> None:
        lang = str(self.lang_box.currentData())
        self.apply_language(lang)

    def apply_language(self, lang: str) -> None:
        i18n.set_language(lang)
        self.settings.language = lang
        store.save(self.settings, self._store)
        self.lang_box.blockSignals(True)
        self.lang_box.setCurrentIndex(0 if lang == "en" else 1)
        self.lang_box.blockSignals(False)
        self._apply_text()
        w = self.controller.wizard
        if w is None:
            self.show_home()
        else:
            self._rebuild_tree()
            self.show_step(w.step.id)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            new = dlg.result_settings()
            self.settings = new
            store.save(new, self._store)
            self.apply_language(new.language or i18n.detect_language())
