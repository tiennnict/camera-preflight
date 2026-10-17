"""Small widgets shared by the views: level badge, parameter table, reference strip."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ... import i18n
from ...domain import Level, Message
from ..i18n_helpers import tr
from ..reference import ReferencePhoto
from ..theme import GLYPH, Colors, level_color


def level_text(level: Level) -> str:
    return i18n.render(Message(code=f"level.{level.value}"))


class LevelBadge(QLabel):
    """Glyph plus text: the level is never shown by colour alone (NFR-15)."""

    def __init__(self, level: Level, colors: Colors, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_level(level, colors)

    def set_level(self, level: Level, colors: Colors) -> None:
        color = level_color(colors, level)
        self.setText(f"{GLYPH[level]}  {level_text(level)}")
        self.setStyleSheet(f"color:{color}; font-weight:600; background:transparent;")
        self.setAccessibleName(level_text(level))


class ParamTable(QWidget):
    """A key and value table with no prose (UX section 9)."""

    def __init__(self, rows: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        for i, (k, v) in enumerate(rows):
            key = QLabel(k)
            key.setObjectName("muted")
            grid.addWidget(key, i, 0)
            grid.addWidget(QLabel(v), i, 1)
        grid.setColumnStretch(2, 1)


class ReferenceStrip(QWidget):
    """Up to four reference photos, each with its credit under it (FR-GUI-07)."""

    def __init__(self, photos: list[ReferencePhoto], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        if not photos:
            note = QLabel(tr("No reference photo yet"))
            note.setObjectName("muted")
            row.addWidget(note)
            row.addStretch(1)
            return
        for p in photos:
            col = QVBoxLayout()
            img = QLabel()
            pix = QPixmap(str(p.path))
            img.setPixmap(pix.scaledToHeight(110, Qt.TransformationMode.SmoothTransformation))
            img.setToolTip(f"{p.credit}\n{p.source}")
            credit = QLabel(p.credit)
            credit.setObjectName("muted")
            credit.setWordWrap(True)
            credit.setMaximumWidth(150)
            col.addWidget(img)
            col.addWidget(credit)
            row.addLayout(col)
        row.addStretch(1)


def panel() -> QFrame:
    f = QFrame()
    f.setObjectName("panel")
    return f
