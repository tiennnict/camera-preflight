"""Application start: settings, language, theme, first-run SDK setup (S0)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .. import i18n
from . import settings as store
from .shell import MainWindow
from .views.settings_dialogs import SdkSetupDialog


def run(language: str | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    assert isinstance(app, QApplication)
    app.setApplicationName("camera-preflight")
    settings = store.load()
    i18n.set_language(language or settings.language or None)
    window = MainWindow(settings)
    window.show()
    if not settings.sdk_setup_seen:
        dlg = SdkSetupDialog(settings, window)
        if dlg.exec():
            settings.sdk_dirs = dlg.result_dirs()
        settings.sdk_setup_seen = True
        store.save(settings)
    return app.exec()
