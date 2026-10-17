"""Common base for step views."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...wizard import StepDef
from ..controller import Controller
from ..i18n_helpers import tr
from ..theme import Colors


class StepView(QWidget):
    """A screen for one step. ``refresh`` is called when results or frames change."""

    def __init__(
        self, controller: Controller, colors: Colors, step: StepDef, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.colors = colors
        self.step = step
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(20, 16, 20, 16)
        self.root.setSpacing(12)
        self.title = QLabel(tr_code(step.title_code))
        self.title.setObjectName("title")
        self.title.setWordWrap(True)
        self.instruction = QLabel(tr_code(step.instruction_code))
        self.instruction.setWordWrap(True)
        self.root.addWidget(self.title)
        self.root.addWidget(self.instruction)

    def refresh(self) -> None:
        return None

    def on_leave(self) -> None:
        return None


def tr_code(code: str) -> str:
    from ... import i18n
    from ...domain import Message

    return i18n.render(Message(code=code))


_ = tr
