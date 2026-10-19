"""S1 Home: start a check. No history of past sessions (D-32, FR-SES-08)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from ...wizard import StepDef
from ..controller import Controller
from ..i18n_helpers import tr
from ..theme import Colors
from .base import StepView


class StartView(StepView):
    startRequested = Signal(str)  # entered serial, may be empty
    settingsRequested = Signal()
    demoRequested = Signal(str)

    def __init__(
        self, controller: Controller, colors: Colors, step: StepDef, parent: QWidget | None = None
    ) -> None:
        super().__init__(controller, colors, step, parent)
        self.title.setText(tr("Check a used camera"))
        self.instruction.setText(tr("Enter the serial if you wish."))
        label = QLabel(tr("Serial (optional)"))
        label.setObjectName("muted")
        self.serial = QLineEdit()
        self.serial.setPlaceholderText(tr("Printed on the camera"))
        self.serial.setMaximumWidth(320)
        self.serial.setAccessibleName(tr("Serial (optional)"))
        self.start_btn = QPushButton(tr("Start"))
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(lambda: self.startRequested.emit(self.serial.text().strip()))
        self.demo_btn = QPushButton(tr("Try demo"))
        self.demo_btn.clicked.connect(lambda: self.demoRequested.emit(self.serial.text().strip()))
        self.settings_btn = QPushButton(tr("Settings"))
        self.settings_btn.clicked.connect(self.settingsRequested)
        row = QHBoxLayout()
        row.addWidget(self.start_btn)
        row.addWidget(self.demo_btn)
        row.addWidget(self.settings_btn)
        row.addStretch(1)
        self.root.addWidget(label)
        self.root.addWidget(self.serial)
        self.root.addLayout(row)
        self.root.addStretch(1)
        self.start_btn.setDefault(True)
        self.serial.returnPressed.connect(self.start_btn.click)

    def set_busy(self, busy: bool) -> None:
        """While the camera is looked for, starting again is not possible."""
        for w in (self.start_btn, self.demo_btn, self.settings_btn, self.serial):
            w.setEnabled(not busy)
