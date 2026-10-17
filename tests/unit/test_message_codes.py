"""Every message code used in source is registered, so no user ever sees a raw code."""

import ast
from pathlib import Path

from camera_preflight.messages import MESSAGES

SRC = Path(__file__).resolve().parents[2] / "src" / "camera_preflight"
CALLS = {"msg": 0, "finding": 1, "Message": None, "_reject": 1, "from_code": 0}
REASONS = (
    "skipped_by_user",
    "sdk_not_configured",
    "no_reference_data",
    "insufficient_frames",
    "unreadable",
    "requires_reference_instrument",
    "not_applicable",
    "not_answered",
    "timestamp_resolution_low",
    "not_supported_by_backend",
)


def used_codes() -> set[str]:
    codes: set[str] = set()
    for path in SRC.rglob("*.py"):
        if path.name == "messages.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name not in CALLS:
                continue
            for kw in node.keywords:
                if kw.arg == "code" and isinstance(kw.value, ast.Constant):
                    codes.add(str(kw.value.value))
            idx = CALLS[name]
            if idx is not None and len(node.args) > idx:
                arg = node.args[idx]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    codes.add(arg.value)
    return codes


def test_all_used_codes_are_registered():
    missing = sorted(
        c for c in used_codes() | {f"reason.{r}" for r in REASONS} if c not in MESSAGES
    )
    assert not missing, missing


def test_step_and_check_codes_registered():
    from camera_preflight.checks import ALL_CHECKS
    from camera_preflight.domain import Mode
    from camera_preflight.wizard import build_plan

    codes = {c.spec.title for c in ALL_CHECKS}
    for mode in Mode:
        for step in build_plan(mode, sdk_available=frozenset({"sony"})):
            codes |= {step.title_code, step.instruction_code}
    codes |= {"b.hot", "b.stuck_bright", "b.dead", "manual.pass", "manual.suspect", "manual.fail"}
    missing = sorted(c for c in codes if c not in MESSAGES)
    assert not missing, missing
