"""Helpers to declare checks (FR-TST-01)."""

from __future__ import annotations

from ..domain import (
    AutomationLevel,
    CheckSpec,
    ExecPath,
    FrameRequirement,
    Mode,
)

_PATH = {
    AutomationLevel.AUTOMATIC: ExecPath.TETHERED,
    AutomationLevel.HELPER: ExecPath.SEMI_AUTOMATIC,
    AutomationLevel.BUTTON: ExecPath.SEMI_AUTOMATIC,
    AutomationLevel.UPLOAD: ExecPath.FILE_IMPORT,
    AutomationLevel.MANUAL: ExecPath.MANUAL,
}

C, U = Mode.CONNECTED, Mode.UPLOAD
A, H, B, UP, M = (
    AutomationLevel.AUTOMATIC,
    AutomationLevel.HELPER,
    AutomationLevel.BUTTON,
    AutomationLevel.UPLOAD,
    AutomationLevel.MANUAL,
)

AUTO_OR_UPLOAD = {C: A, U: UP}
SEMI_OR_UPLOAD = {C: H, U: UP}
BUTTON_OR_UPLOAD = {C: B, U: UP}
CONNECTED_AUTO = {C: A}
CONNECTED_SEMI = {C: H}
MANUAL_BOTH = {C: M, U: M}
FROM_FIRST_FRAME = {C: A, U: A}  # read from the device (connected) or the first frame (upload)


def make_spec(
    check_id: str,
    group: str,
    automation: dict[Mode, AutomationLevel],
    *,
    requirements: tuple[FrameRequirement, ...] = (),
    max_shots: int = 0,
    needs_sdk: frozenset[str] = frozenset(),
    kb_fields: tuple[str, ...] = (),
    gate_rules: tuple[str, ...] = (),
) -> CheckSpec:
    return CheckSpec(
        id=check_id,
        group=group,
        title=f"check.{check_id}.title",
        paths=frozenset(_PATH[a] for a in automation.values()),
        automation=automation,
        requirements=requirements,
        max_shots=max_shots,
        needs_sdk=needs_sdk,
        kb_fields=kb_fields,
        gate_rules=gate_rules,
    )
