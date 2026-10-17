from pathlib import Path

import numpy as np

from camera_preflight.domain import DEFAULT_1, CfaData, Confidence, Frame, FrameKind, FrameMeta
from camera_preflight.gate import GateProfile, check_provenance, evaluate, lower
from camera_preflight.gate.format import fmt_exposure
from camera_preflight.synth import Defects, SensorSpec, synth_dark, synth_flat

SPEC = SensorSpec()


def _frame(arr, **meta):
    cfa = CfaData(arr, SPEC.pattern, SPEC.black_level, SPEC.white_level)
    return Frame("f", "0" * 64, Path("a.dng"), FrameMeta(**meta), cfa=cfa)


def _flat(level=0.6, **kw):
    arr = synth_flat(
        SPEC,
        Defects(**kw),
        iso=100,
        exposure_s=1 / 250,
        aperture=8,
        level=level,
        rng=np.random.default_rng(0),
    )
    return arr


def test_exposure_rejection_states_found_and_needed():
    f = _frame(
        synth_dark(SPEC, Defects(), iso=1600, exposure_s=1 / 60, rng=np.random.default_rng(0)),
        iso=1600,
        exposure_s=1 / 60,
    )
    rej = evaluate(f, GateProfile(FrameKind.DARK, iso=1600, exposure_s=30.0), DEFAULT_1)
    assert rej and rej.rule == "G1" and rej.message.code == "gate.exposure"
    assert rej.message.params == {"found": "1/60 s", "needed": "30 s"}


def test_dark_frame_accepted_and_light_leak_rejected():
    dark = synth_dark(SPEC, Defects(), iso=1600, exposure_s=0.5, rng=np.random.default_rng(0))
    prof = GateProfile(FrameKind.DARK, iso=1600, exposure_s=0.5, check_dark=True)
    assert evaluate(_frame(dark, iso=1600, exposure_s=0.5), prof, DEFAULT_1) is None
    leaky = dark.copy()
    leaky[:, : leaky.shape[1] // 2] += 400
    rej = evaluate(_frame(leaky, iso=1600, exposure_s=0.5), prof, DEFAULT_1)
    assert rej and rej.rule == "G7"
    bright = dark + 3000
    assert evaluate(_frame(bright, iso=1600, exposure_s=0.5), prof, DEFAULT_1).rule == "G7"


def test_flat_histogram_and_clipping():
    prof = GateProfile(FrameKind.FLAT, check_histogram=True, check_clipping=True)
    assert evaluate(_frame(_flat(0.6), iso=100), prof, DEFAULT_1) is None
    assert evaluate(_frame(_flat(0.2), iso=100), prof, DEFAULT_1).message.code == "gate.too_dark"
    assert evaluate(_frame(_flat(0.95), iso=100), prof, DEFAULT_1).rule in {"G2", "G3"}


def test_flicker_rejected_at_fast_speed_only():
    prof = GateProfile(FrameKind.FLAT, exposure_s=1 / 250, check_flicker=True)
    assert evaluate(_frame(_flat(), iso=100, exposure_s=1 / 250), prof, DEFAULT_1) is None
    flick = _flat(flicker_amplitude=0.05)
    assert evaluate(_frame(flick, iso=100, exposure_s=1 / 250), prof, DEFAULT_1).rule == "G4"
    slow = GateProfile(FrameKind.FLAT, exposure_s=1 / 30, check_flicker=True)
    assert evaluate(_frame(flick, iso=100, exposure_s=1 / 30), slow, DEFAULT_1) is None


def test_serial_mismatch_and_not_raw():
    arr = _flat()
    prof = GateProfile(FrameKind.FLAT)
    f = _frame(arr, serial="B")
    assert evaluate(f, prof, DEFAULT_1, reference_serial="A").rule == "G5"
    jpg = Frame("j", "0" * 64, Path("a.jpg"), FrameMeta(), cfa=None)
    assert evaluate(jpg, prof, DEFAULT_1).message.code == "gate.not_raw"


def test_provenance_flags_and_confidence_cap():
    a = _frame(_flat(), serial="S1", software="Adobe Photoshop 25")
    r = check_provenance([a])
    assert r.confidence_cap is Confidence.LOW and r.issues
    none = check_provenance([_frame(_flat())])
    assert none.issues[0].code == "provenance.no_serial"
    assert lower(Confidence.HIGH, Confidence.MEDIUM) is Confidence.MEDIUM
    assert lower(Confidence.LOW, Confidence.MEDIUM) is Confidence.LOW
    assert fmt_exposure(30.0) == "30 s" and fmt_exposure(1 / 250) == "1/250 s"
