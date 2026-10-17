"""The wizard plan: phases, steps and the checks each step feeds (D-26, D-28, D-34, D-35).

There are no profiles. Every check that applies to the body is in the plan, ordered by
automation level: automatic, then semi-automatic (helper or button), then manual.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..checks import BY_ID
from ..checks.group_b import B1_REQ, B2_REQ, B4_REQ
from ..checks.group_c import C1_REQ, C2_FAST, C2_REF, C3_REQ, C4_FAST
from ..checks.group_d import GENERIC_POINTS, af_requirements
from ..checks.group_e import E1_REQ, E2_REQ, E3_REQ, E5_REQ, E6_REQ, E7_REQ
from ..domain import AutomationLevel, FrameKind, FrameRequirement, Mode, Phase

FIRST_REQ = FrameRequirement(FrameKind.OTHER, 1, tag="first")
AF_REQ = af_requirements(GENERIC_POINTS, 3)
AF_REQ2 = af_requirements(GENERIC_POINTS, 3, prefix="af2")


@dataclass(frozen=True)
class StepDef:
    id: str
    phase: Phase
    checks: tuple[str, ...]
    requirements: tuple[FrameRequirement, ...] = ()
    automation: AutomationLevel = AutomationLevel.MANUAL
    helper: str | None = None  # "H1" to "H7"
    animation: str | None = None
    group: bool = False  # connected group run: one trigger, many checks

    @property
    def instruction_code(self) -> str:
        if self.id in _SPECIFIC_INSTRUCTION:
            return f"step.{self.id}.instruction"
        if self.phase is Phase.MANUAL:
            return "step.manual.instruction"
        return "step.upload.instruction"

    @property
    def title_code(self) -> str:
        if self.phase is Phase.MANUAL:
            return f"check.{self.checks[0]}.title"
        return f"step.{self.id}.title"

    @property
    def needs_user(self) -> bool:
        return self.automation is not AutomationLevel.AUTOMATIC

    @property
    def is_shooting(self) -> bool:
        return bool(self.requirements)


_SPECIFIC_INSTRUCTION = frozenset(
    {"start", "blocker", "auto", "first", "burst", "dark", "flat", "chart", "lens2", "results"}
)


def _uniq(reqs: tuple[FrameRequirement, ...]) -> tuple[FrameRequirement, ...]:
    seen: dict[str, FrameRequirement] = {}
    for r in reqs:
        seen.setdefault(r.key, r)
    return tuple(seen.values())


def requirements_of(check_ids: tuple[str, ...]) -> tuple[FrameRequirement, ...]:
    return _uniq(tuple(r for cid in check_ids for r in BY_ID[cid].spec.requirements))


_UP, _H, _A, _M = (
    AutomationLevel.UPLOAD,
    AutomationLevel.HELPER,
    AutomationLevel.AUTOMATIC,
    AutomationLevel.MANUAL,
)

MANUAL_CHECKS = ("F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "C6", "A7")
MANUAL_ANIMATION = {
    "F5": "tilt_mount",
    "F6": "press_buttons",
    "F7": "solid_colours",
    "F8": "diopter",
    "F9": "mount_play",
    "F10": "popup_flash",
    "F11": "plug_usb",
    "F12": "change_lens",
    "C6": "half_press",
    "A7": "power_on",
}


def build_plan(mode: Mode, *, sdk_available: frozenset[str] = frozenset()) -> list[StepDef]:
    """Ordered steps for the mode. Steps that no check needs in this mode are left out."""
    steps: list[StepDef] = [StepDef("start", Phase.START, ())]
    steps.append(StepDef("blocker", Phase.BLOCKER, ("F1", "F2", "F3", "F4"), animation="power_on"))
    sdk_checks = tuple(c for c in ("D6", "D7", "D8") if sdk_available)
    if mode is Mode.CONNECTED:
        steps.append(
            StepDef(
                "auto",
                Phase.AUTOMATIC,
                ("A1", "A2", "A3", "A4", "A5", "A6", "D9", "C1"),
                requirements=C1_REQ,
                automation=_A,
                animation="plug_usb",
            )
        )
        steps.append(
            StepDef("dark", Phase.SEMI_AUTOMATIC, ("B1", "B6"), B1_REQ, _H, "H1", "body_cap")
        )
        flat_checks = ("B2", "B3", "B4", "B5", "C2", "C3", "C4", "E1", "E2", "E4", "E5", "E6", "E7")
        steps.append(
            StepDef(
                "flat",
                Phase.SEMI_AUTOMATIC,
                flat_checks,
                requirements_of(flat_checks),
                _H,
                "H2",
                "aim_flat",
                group=True,
            )
        )
        chart_checks = ("D1", "D2", "D3", "D4", "D5", "E3", *sdk_checks)
        steps.append(
            StepDef(
                "chart",
                Phase.SEMI_AUTOMATIC,
                chart_checks,
                requirements_of(chart_checks),
                _H,
                "H3",
                "tripod_chart",
                group=True,
            )
        )
        steps.append(
            StepDef("lens2", Phase.SEMI_AUTOMATIC, ("D10",), AF_REQ2, _H, "H5", "change_lens")
        )
    else:
        steps.append(
            StepDef(
                "first",
                Phase.AUTOMATIC,
                ("A1", "A3", "A4", "A6", "D9"),
                (FIRST_REQ,),
                _UP,
                animation="aim_flat",
            )
        )
        steps.append(
            StepDef("burst", Phase.AUTOMATIC, ("C1",), C1_REQ, _UP, animation="hold_shutter")
        )
        steps.append(
            StepDef("dark", Phase.SEMI_AUTOMATIC, ("B1", "B6"), B1_REQ, _UP, animation="body_cap")
        )
        steps.append(
            StepDef(
                "flat8", Phase.SEMI_AUTOMATIC, ("B2", "B3", "B5"), B2_REQ, _UP, animation="aim_flat"
            )
        )
        steps.append(
            StepDef("flat22", Phase.SEMI_AUTOMATIC, ("B4",), B4_REQ, _UP, animation="aim_flat")
        )
        steps.append(
            StepDef(
                "curtain",
                Phase.SEMI_AUTOMATIC,
                ("C2", "C4"),
                _uniq((C2_REF, *C2_FAST, *C4_FAST)),
                _UP,
                animation="aim_flat",
            )
        )
        steps.append(
            StepDef("repeat", Phase.SEMI_AUTOMATIC, ("C3",), C3_REQ, _UP, animation="aim_flat")
        )
        steps.append(
            StepDef(
                "meter",
                Phase.SEMI_AUTOMATIC,
                ("E1", "E2", "E4"),
                _uniq((*E1_REQ, *E2_REQ)),
                _UP,
                animation="aim_flat",
            )
        )
        steps.append(
            StepDef("comp", Phase.SEMI_AUTOMATIC, ("E5",), E5_REQ, _UP, animation="command_dial")
        )
        steps.append(
            StepDef("iso", Phase.SEMI_AUTOMATIC, ("E6",), E6_REQ, _UP, animation="command_dial")
        )
        steps.append(
            StepDef(
                "aperture", Phase.SEMI_AUTOMATIC, ("E7",), E7_REQ, _UP, animation="command_dial"
            )
        )
        steps.append(
            StepDef(
                "af",
                Phase.SEMI_AUTOMATIC,
                ("D1", "D2", "D3", "D4", "D5"),
                AF_REQ,
                _UP,
                animation="tripod_chart",
            )
        )
        steps.append(
            StepDef("spot", Phase.SEMI_AUTOMATIC, ("E3",), E3_REQ, _UP, animation="move_spot")
        )
        steps.append(
            StepDef("lens2", Phase.SEMI_AUTOMATIC, ("D10",), AF_REQ2, _UP, animation="change_lens")
        )
    for cid in MANUAL_CHECKS:
        steps.append(
            StepDef(
                f"m-{cid}", Phase.MANUAL, (cid,), automation=_M, animation=MANUAL_ANIMATION[cid]
            )
        )
    steps.append(StepDef("results", Phase.RESULTS, ()))
    return steps


def phase_of(step: StepDef) -> Phase:
    return step.phase
