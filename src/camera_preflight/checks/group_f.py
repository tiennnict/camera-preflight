"""Group F: physical and manual checks, including the blocker check (D-35)."""

from __future__ import annotations

from .base import Check, FunctionCheck
from .manual import from_answer
from .specs import MANUAL_BOTH, make_spec

# F1 to F4 form the blocker check; F5 to F12 are the manual checks at the end of the wizard.
BLOCKER_IDS = ("F1", "F2", "F3", "F4")
MANUAL_IDS = ("F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12")

GROUP_F: tuple[Check, ...] = tuple(
    FunctionCheck(make_spec(i, "F", MANUAL_BOTH), lambda spec, _f, ctx: from_answer(spec, ctx))
    for i in (*BLOCKER_IDS, *MANUAL_IDS)
)
