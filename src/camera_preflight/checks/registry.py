"""All checks in wizard order within each group."""

from __future__ import annotations

from ..domain import AutomationLevel, Mode
from .base import Check
from .group_a import GROUP_A
from .group_b import GROUP_B
from .group_c import GROUP_C
from .group_d import GROUP_D
from .group_e import GROUP_E
from .group_f import GROUP_F

ALL_CHECKS: tuple[Check, ...] = (*GROUP_A, *GROUP_B, *GROUP_C, *GROUP_D, *GROUP_E, *GROUP_F)
BY_ID: dict[str, Check] = {c.spec.id: c for c in ALL_CHECKS}

_ORDER = {
    AutomationLevel.AUTOMATIC: 0,
    AutomationLevel.UPLOAD: 1,
    AutomationLevel.HELPER: 1,
    AutomationLevel.BUTTON: 2,
    AutomationLevel.MANUAL: 3,
}


def checks_for(mode: Mode) -> list[Check]:
    """Checks that apply in a mode, ordered by automation level (D-34)."""
    applicable = [c for c in ALL_CHECKS if mode in c.spec.automation]
    return sorted(applicable, key=lambda c: _ORDER[c.spec.automation[mode]])
