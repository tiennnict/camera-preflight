"""Light and dark themes (FR-SET-03) and the result level look (NFR-15: never colour alone)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ..domain import Level


@dataclass(frozen=True)
class Colors:
    bg: str
    panel: str
    fg: str
    muted: str
    line: str
    accent: str
    accent_fg: str
    pass_: str
    suspect: str
    fail: str
    not_tested: str


LIGHT = Colors(
    "#ffffff",
    "#f3f4f8",
    "#1b1c20",
    "#575a66",
    "#d5d7e0",
    "#2457d6",
    "#ffffff",
    "#16722f",
    "#8a5a00",
    "#b3261e",
    "#575a66",
)
DARK = Colors(
    "#16171b",
    "#1f2026",
    "#ececf1",
    "#a4a7b3",
    "#33353f",
    "#7aa2ff",
    "#10131a",
    "#56d364",
    "#e3b341",
    "#ff7b72",
    "#a4a7b3",
)

GLYPH = {
    Level.PASS: "✓",
    Level.SUSPECT: "!",
    Level.FAIL: "✕",
    Level.NOT_TESTED: "–",
}


def level_color(colors: Colors, level: Level) -> str:
    return {
        Level.PASS: colors.pass_,
        Level.SUSPECT: colors.suspect,
        Level.FAIL: colors.fail,
        Level.NOT_TESTED: colors.not_tested,
    }[level]


def stylesheet(c: Colors) -> str:
    return f"""
* {{ font-size: 14px; }}
QWidget {{ background: {c.bg}; color: {c.fg}; }}
QLabel {{ background: transparent; }}
QFrame#panel, QWidget#panel {{ background: {c.panel}; border: 1px solid {c.line}; border-radius: 8px; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#muted {{ color: {c.muted}; }}
QLabel#section {{ font-size: 15px; font-weight: 600; }}
QPushButton {{ background: {c.panel}; border: 1px solid {c.line}; border-radius: 6px; padding: 7px 16px; }}
QPushButton:hover {{ border-color: {c.accent}; }}
QPushButton:focus {{ border: 2px solid {c.accent}; }}
QPushButton:disabled {{ color: {c.muted}; }}
QPushButton#primary {{ background: {c.accent}; color: {c.accent_fg}; border-color: {c.accent}; font-weight: 600; }}
QPushButton#primary:disabled {{ background: {c.line}; color: {c.muted}; }}
QTreeWidget, QListWidget, QTableWidget, QTextEdit, QLineEdit, QComboBox, QScrollArea {{
  background: {c.bg}; border: 1px solid {c.line}; border-radius: 6px; }}
QTreeWidget::item, QListWidget::item {{ padding: 4px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {c.accent}; color: {c.accent_fg}; }}
QTreeWidget:focus, QListWidget:focus, QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border: 2px solid {c.accent}; }}
QHeaderView::section {{ background: {c.panel}; border: none; border-bottom: 1px solid {c.line}; padding: 4px; }}
QProgressBar {{ border: 1px solid {c.line}; border-radius: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {c.accent}; }}
QToolTip {{ background: {c.panel}; color: {c.fg}; border: 1px solid {c.line}; }}
"""


def apply_theme(app: QApplication, name: str) -> Colors:
    """``name`` is ``light``, ``dark`` or ``system``."""
    if name == "system":
        scheme = app.styleHints().colorScheme()
        name = "dark" if scheme.name == "Dark" else "light"
    colors = DARK if name == "dark" else LIGHT
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(colors.bg))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(colors.fg))
    pal.setColor(QPalette.ColorRole.Base, QColor(colors.bg))
    pal.setColor(QPalette.ColorRole.Text, QColor(colors.fg))
    pal.setColor(QPalette.ColorRole.Button, QColor(colors.panel))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(colors.fg))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(colors))
    return colors
