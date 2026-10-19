"""Light theme only (D-48) and the result level look (NFR-15: never colour alone)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
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
QComboBox {{ padding: 4px 8px; min-height: 22px; }}
QComboBox QAbstractItemView {{ background: {c.bg}; selection-background-color: {c.accent}; selection-color: {c.accent_fg}; }}
QLineEdit {{ padding: 5px 8px; }}
QScrollBar:vertical {{ background: {c.bg}; width: 10px; margin: 2px; border: none; }}
QScrollBar:horizontal {{ background: {c.bg}; height: 10px; margin: 2px; border: none; }}
QScrollBar::handle {{ background: {c.line}; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: {c.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""


def apply_theme(app: QApplication, _name: str = "light") -> Colors:
    """Apply the light theme. The app has no dark theme (D-48); a dark OS setting is ignored,
    including for native dialogs where Qt allows it."""
    hints = app.styleHints()
    set_scheme = getattr(hints, "setColorScheme", None)  # Qt 6.8 and later
    if set_scheme is not None:
        set_scheme(Qt.ColorScheme.Light)
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")  # the native Windows 11 style draws dark controls in dark mode
    colors = LIGHT
    pal = QPalette()
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        pal.setColor(group, QPalette.ColorRole.Window, QColor(colors.bg))
        pal.setColor(group, QPalette.ColorRole.WindowText, QColor(colors.fg))
        pal.setColor(group, QPalette.ColorRole.Base, QColor(colors.bg))
        pal.setColor(group, QPalette.ColorRole.AlternateBase, QColor(colors.panel))
        pal.setColor(group, QPalette.ColorRole.Text, QColor(colors.fg))
        pal.setColor(group, QPalette.ColorRole.Button, QColor(colors.panel))
        pal.setColor(group, QPalette.ColorRole.ButtonText, QColor(colors.fg))
        pal.setColor(group, QPalette.ColorRole.Highlight, QColor(colors.accent))
        pal.setColor(group, QPalette.ColorRole.HighlightedText, QColor(colors.accent_fg))
        pal.setColor(group, QPalette.ColorRole.ToolTipBase, QColor(colors.panel))
        pal.setColor(group, QPalette.ColorRole.ToolTipText, QColor(colors.fg))
        pal.setColor(group, QPalette.ColorRole.PlaceholderText, QColor(colors.muted))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.muted))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(colors))
    return colors
