"""About: version, licence and the credits of every reference photo (UX section 7, CON-08)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from ... import __version__
from ..i18n_helpers import tr
from ..reference import all_credits


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("About"))
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        title = QLabel(f"camera-preflight {__version__}")
        title.setObjectName("title")
        lay.addWidget(title)
        lay.addWidget(QLabel("Apache-2.0"))
        lay.addWidget(QLabel(tr("No network access. No data leaves this computer.")))
        credits_title = QLabel(tr("Photo credits"))
        credits_title.setObjectName("section")
        lay.addWidget(credits_title)
        host = QWidget()
        col = QVBoxLayout(host)
        credits = all_credits()
        if not credits:
            col.addWidget(QLabel(tr("No reference photos yet")))
        for p in credits:
            label = QLabel(f"{p.topic}: {p.author}, {p.licence}\n{p.source}")
            label.setWordWrap(True)
            col.addWidget(label)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Close"))
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
