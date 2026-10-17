from camera_preflight.domain import (
    CheckResult,
    Confidence,
    ExecPath,
    Label,
    Level,
    Message,
    Param,
    ParameterSet,
)


def test_not_tested_result_has_no_confidence():
    r = CheckResult(
        check_id="B1",
        level=Level.NOT_TESTED,
        path=ExecPath.FILE_IMPORT,
        explanation=Message(code="level.not_tested"),
        not_tested_reason="skipped by user",
    )
    assert r.confidence is None and r.level is Level.NOT_TESTED


def test_parameter_set_lookup_keeps_label():
    ps = ParameterSet(id="t", params=(Param(name="a", value=2, label=Label.GUESS),))
    assert ps.get("a") == 2.0 and ps.label_of("a") is Label.GUESS


def test_message_is_hashable():
    assert hash(Message(code="x", params={"a": 1})) == hash(Message(code="x", params={"a": 1}))
    assert Confidence.HIGH.value == "high"
