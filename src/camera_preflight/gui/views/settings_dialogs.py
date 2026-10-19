"""S13 Settings and S0 first-run SDK setup (D-24, D-48, FR-CON-06, FR-SET-01 to FR-SET-03)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...i18n import N_
from ..i18n_helpers import tr
from ..settings import BRANDS, UserSettings, default_sdk_dir

SDK_INFO = {
    "Canon": N_("Adds focus control and newer bodies."),
    "Nikon": N_("Adds AF point selection and focus check."),
    "Sony": N_("Adds remote AF area and focus check."),
}


class _FolderRow(QWidget):
    def __init__(self, value: str, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(value)
        self.edit.setPlaceholderText(placeholder)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        btn = QPushButton(tr("Choose folder"))
        btn.clicked.connect(self._choose)
        row.addWidget(self.edit, 1)
        row.addWidget(self.status)
        row.addWidget(btn)
        self.edit.textChanged.connect(self._update_status)
        self._update_status()

    def _choose(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("Choose folder"), self.edit.text())
        if d:
            self.edit.setText(d)

    def _update_status(self) -> None:
        text = self.edit.text() or self.edit.placeholderText()
        p = Path(text)
        found = p.is_dir() and any(p.iterdir()) if p.exists() else False
        self.status.setText(tr("Found") if found else tr("Not found"))

    def value(self) -> str:
        return self.edit.text().strip()


def sdk_form(settings: UserSettings) -> tuple[QFormLayout, dict[str, _FolderRow]]:
    form = QFormLayout()
    rows: dict[str, _FolderRow] = {}
    for brand in BRANDS:
        row = _FolderRow((settings.sdk_dirs or {}).get(brand, ""), str(default_sdk_dir(brand)))
        info = QLabel(tr(SDK_INFO[brand]))
        info.setObjectName("muted")
        col = QVBoxLayout()
        col.addWidget(row)
        col.addWidget(info)
        box = QWidget()
        box.setLayout(col)
        form.addRow(brand, box)
        rows[brand] = row
    return form, rows


class SettingsDialog(QDialog):
    def __init__(self, settings: UserSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self.resize(640, 520)
        self.settings = settings
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.lang = QComboBox()
        self.lang.addItem(tr("Follow system"), "")
        self.lang.addItem("English", "en")
        self.lang.addItem("Tiếng Việt", "vi")
        self.lang.setCurrentIndex(max(self.lang.findData(settings.language), 0))
        self.motion = QCheckBox(tr("Reduce motion"))
        self.motion.setChecked(settings.reduced_motion)
        self.sessions = _FolderRow(settings.sessions_dir, str(settings.sessions_path()))
        form.addRow(tr("Language"), self.lang)
        form.addRow("", self.motion)
        form.addRow(tr("Sessions folder"), self.sessions)
        lay.addLayout(form)
        title = QLabel(tr("Camera SDK folders"))
        title.setObjectName("section")
        lay.addWidget(title)
        sdk, self.sdk_rows = sdk_form(settings)
        lay.addLayout(sdk)
        lay.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def result_settings(self) -> UserSettings:
        s = self.settings
        return UserSettings(
            language=str(self.lang.currentData()),
            reduced_motion=self.motion.isChecked(),
            sessions_dir=self.sessions.value(),
            sdk_dirs={b: r.value() for b, r in self.sdk_rows.items()},
            sdk_setup_seen=s.sdk_setup_seen,
        )


class SdkSetupDialog(QDialog):
    """S0: shown once on first run. Continuing without an SDK is always possible."""

    def __init__(self, settings: UserSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Camera SDK"))
        self.resize(640, 440)
        self.settings = settings
        lay = QVBoxLayout(self)
        title = QLabel(tr("Set up camera SDKs"))
        title.setObjectName("title")
        note = QLabel(tr("Optional. Without an SDK some checks are skipped."))
        note.setWordWrap(True)
        lay.addWidget(title)
        lay.addWidget(note)
        form, self.rows = sdk_form(settings)
        lay.addLayout(form)
        lay.addStretch(1)
        buttons = QDialogButtonBox()
        self.skip = buttons.addButton(
            tr("Continue without SDK"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.ok = buttons.addButton(tr("Save"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def result_dirs(self) -> dict[str, str]:
        return {b: r.value() for b, r in self.rows.items()}
