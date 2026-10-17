import pytest

from camera_preflight.checks import ALL_CHECKS, BY_ID, CheckContext, ManualAnswer, checks_for
from camera_preflight.domain import (
    DEFAULT_1,
    Confidence,
    DeviceInfo,
    Level,
    Mode,
    Severity,
)
from camera_preflight.gate import check_provenance
from camera_preflight.i18n import render
from camera_preflight.knowledge import ModelEntry
from camera_preflight.synth import Defects, SynthCamera, af_attempts, build_frames


_CACHE: dict[str, object] = {}


def _frames(cam):
    key = repr(cam)
    if key not in _CACHE:
        _CACHE[key] = build_frames(cam)
    return _CACHE[key]


def run(cam, check_id, mode=Mode.UPLOAD, **ctx_kw):
    frames = _frames(cam)
    allf = [f for v in frames.values() for f in v]
    ctx = CheckContext(
        params=DEFAULT_1,
        mode=mode,
        provenance=check_provenance(allf),
        af_attempts=af_attempts(cam),
        **ctx_kw,
    )
    return BY_ID[check_id].analyse(frames, ctx)


@pytest.fixture(scope="module")
def healthy():
    cam = SynthCamera()
    frames = build_frames(cam)
    allf = [f for v in frames.values() for f in v]
    ctx = CheckContext(
        params=DEFAULT_1,
        mode=Mode.UPLOAD,
        provenance=check_provenance(allf),
        af_attempts=af_attempts(cam),
    )
    return {c.spec.id: c.analyse(frames, ctx) for c in ALL_CHECKS}


@pytest.mark.parametrize(
    "cid",
    [
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "B6",
        "C1",
        "C2",
        "C3",
        "C4",
        "D2",
        "D3",
        "D4",
        "D5",
        "E1",
        "E2",
        "E3",
        "E5",
        "E6",
        "E7",
    ],
)
def test_healthy_camera_passes(healthy, cid):
    assert healthy[cid].level is Level.PASS, (cid, render(healthy[cid].explanation))
    assert healthy[cid].confidence in (Confidence.MEDIUM, Confidence.LOW, Confidence.HIGH)


def test_no_pass_without_frames():
    """NFR-01: a check that did not run on accepted frames is never Pass."""
    ctx = CheckContext(params=DEFAULT_1, mode=Mode.UPLOAD)
    for c in ALL_CHECKS:
        if not c.spec.requirements:
            continue
        r = c.analyse({}, ctx)
        assert r.level is Level.NOT_TESTED, c.spec.id
        assert r.not_tested_reason


def test_hot_pixel_cluster_is_high():
    d = Defects(hot=[(100, 100), (100, 102), (102, 100), (102, 102)], hot_rate_e_s=2000.0)
    r = run(SynthCamera(defects=d), "B1")
    assert r.level is Level.SUSPECT and r.severity is Severity.HIGH
    assert r.evidence == () or r.evidence[0].path.endswith(".png")


def test_stuck_and_dead_found_in_flat():
    d = Defects(stuck_bright=[(50, 60)], dead=[(150, 200)])
    r = run(SynthCamera(defects=d), "B2")
    assert {f.kind for f in r.findings} >= {"stuck_bright", "dead"}


def test_dust_and_scratch():
    heavy = Defects(dust=[(60 + 20 * i, 60 + 30 * j, 5.0) for i in range(6) for j in range(6)])
    r = run(SynthCamera(defects=heavy), "B4")
    assert r.level is Level.SUSPECT and r.severity is Severity.MEDIUM
    scratch = run(SynthCamera(defects=Defects(scratch=(20, 30, 300, 90), scratch_depth=0.3)), "B4")
    assert scratch.level is Level.SUSPECT and scratch.severity is Severity.HIGH


def test_banding_reported():
    r = run(SynthCamera(defects=Defects(row_banding_dn=2.0)), "B6")
    assert r.level is Level.SUSPECT and r.severity is Severity.LOW


def test_burst_stall():
    r = run(SynthCamera(burst_stall_after=4), "C1")
    assert r.level is Level.SUSPECT


def test_curtain_mechanical_only():
    cam = SynthCamera(fast_curtain_gradient=0.08)
    assert run(cam, "C2").level is Level.SUSPECT
    assert (
        "curtain" in render(run(cam, "C4").explanation).lower()
        or run(cam, "C4").level is Level.SUSPECT
    )
    both = SynthCamera(fast_curtain_gradient=0.08, electronic_curtain_gradient=0.08)
    assert run(both, "C4").explanation.code == "c4.sensor_or_light"


def test_af_soft_edge_point_and_fail_to_focus():
    soft = run(SynthCamera(af_soft_points={"left": 3.0}), "D3")
    assert soft.level is Level.SUSPECT and soft.severity is Severity.LOW
    centre = run(SynthCamera(af_soft_points={"centre": 3.0}), "D3")
    assert centre.severity is Severity.HIGH
    nofocus = run(SynthCamera(af_fail_points=frozenset({"right"})), "D2")
    assert nofocus.level is Level.SUSPECT and nofocus.confidence is not Confidence.HIGH


def test_af_never_fail_from_one_lens():
    ctx = dict(af_by_lens={"A": {"left"}, "B": set()})
    r = run(SynthCamera(), "D10", **ctx)
    assert r.level is Level.SUSPECT
    both = run(SynthCamera(), "D10", af_by_lens={"A": {"left"}, "B": {"left"}})
    assert both.level is Level.FAIL


def test_metering_faults():
    assert run(SynthCamera(exposure_jitter_ev=0.6), "E1").level is Level.SUSPECT
    assert run(SynthCamera(spot_follows=False), "E3").level is Level.SUSPECT
    assert run(SynthCamera(comp_nonlinear_ev=0.6), "E5").level is Level.SUSPECT
    assert run(SynthCamera(iso_jump_ev=0.6), "E6").level is Level.SUSPECT


def test_group_a_from_first_frame_and_serial_mismatch():
    ok = run(SynthCamera(), "A1")
    assert ok.level is Level.PASS
    bad = run(SynthCamera(), "A1", entered_serial="XX9999")
    assert bad.level is Level.SUSPECT and bad.severity is Severity.MEDIUM


def test_shutter_count_never_zero_when_unreadable():
    r = run(SynthCamera(shutter_count=None), "A3")
    assert r.level is Level.NOT_TESTED and r.not_tested_reason == "unreadable"


def test_shutter_count_against_rated_life():
    kb = ModelEntry.model_validate(
        {
            "brand": "Canon",
            "model": "SC-1",
            "shutter": {
                "rated_life": {
                    "value": 100000,
                    "source": "https://example.test/spec",
                    "confidence": "medium",
                }
            },
            "firmware_latest": {"version": "1.2.0", "source": "https://example.test/fw"},
        }
    )
    near = run(SynthCamera(shutter_count=90000), "A3", kb=kb)
    assert near.level is Level.SUSPECT and near.severity is Severity.LOW
    fine = run(SynthCamera(shutter_count=2000), "A3", kb=kb)
    assert fine.level is Level.PASS
    fw = run(SynthCamera(), "A4", kb=kb)
    assert fw.level is Level.PASS and any(
        f.kind == "warning" for f in fw.findings
    )  # older firmware


def test_unknown_rated_life_is_not_tested_with_count_reported():
    r = run(SynthCamera(), "A3")
    assert r.level is Level.NOT_TESTED and r.not_tested_reason == "no_reference_data"
    assert any(f.kind == "count" for f in r.findings)


def test_manual_checks_use_answers_and_blocker_severity():
    ctx = CheckContext(
        params=DEFAULT_1,
        mode=Mode.UPLOAD,
        manual={"F2": ManualAnswer(Level.FAIL, "big crack"), "F6": ManualAnswer(Level.SUSPECT)},
    )
    assert BY_ID["F2"].analyse({}, ctx).severity is Severity.BLOCKER
    assert BY_ID["F6"].analyse({}, ctx).severity is Severity.MEDIUM
    assert BY_ID["F7"].analyse({}, ctx).level is Level.NOT_TESTED


def test_skip_and_sdk_rules():
    ctx = CheckContext(params=DEFAULT_1, mode=Mode.CONNECTED, skipped=frozenset({"B1"}))
    assert BY_ID["B1"].analyse({}, ctx).not_tested_reason == "skipped_by_user"
    assert BY_ID["D6"].analyse({}, ctx).not_tested_reason == "sdk_not_configured"


def test_provenance_lowers_confidence():
    cam = SynthCamera()
    frames = build_frames(cam)
    allf = [f for v in frames.values() for f in v]
    for f in allf[:3]:
        f.meta = f.meta.model_copy(update={"software": "Adobe Photoshop"})
    ctx = CheckContext(params=DEFAULT_1, mode=Mode.UPLOAD, provenance=check_provenance(allf))
    r = BY_ID["B5"].analyse(frames, ctx)
    assert r.confidence is Confidence.LOW


def test_checks_for_orders_by_automation():
    order = [c.spec.id for c in checks_for(Mode.CONNECTED)]
    assert order.index("A1") < order.index("B1") < order.index("F5")
    assert "A2" not in [c.spec.id for c in checks_for(Mode.UPLOAD)]
    assert DeviceInfo().model is None
