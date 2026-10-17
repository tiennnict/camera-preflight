import numpy as np

from camera_preflight.analysis.af import (
    AfPoint,
    coefficient_of_variation,
    region_sharpness,
    sharpness_map,
)
from camera_preflight.analysis.metering import exposure_value, linear_fit, spread
from camera_preflight.analysis.shutter import burst_rhythm, curtain_gradient, level_spread_ev
from camera_preflight.synth import Defects, SensorSpec, synth_chart, synth_flat


def _flat(spec, d, seed=0, level=0.6):
    return synth_flat(
        spec, d, iso=100, exposure_s=0.01, aperture=8, level=level, rng=np.random.default_rng(seed)
    )


def test_burst_regular_versus_stall():
    regular = burst_rhythm([i * 0.1 for i in range(10)])
    assert regular and regular.cv < 0.01 and abs(regular.fps - 10) < 0.01
    stalled = burst_rhythm([0, 0.1, 0.2, 0.3, 0.9, 1.0, 1.1, 1.2])
    assert stalled and stalled.max_ratio > 2.5


def test_curtain_gradient_detected():
    spec = SensorSpec()
    ref = [_flat(spec, Defects(), i) for i in range(2)]
    fine = [_flat(spec, Defects(), 10 + i) for i in range(2)]
    bad = [_flat(spec, Defects(curtain_gradient=0.08), 20 + i) for i in range(2)]
    ok = curtain_gradient(fine, ref, spec.pattern, spec.black_level)
    gr = curtain_gradient(bad, ref, spec.pattern, spec.black_level)
    assert abs(ok.gradient_rows) < 0.02
    assert abs(gr.gradient_rows) > 0.05


def test_repeatability_spread():
    spec = SensorSpec()
    frames = [_flat(spec, Defects(), i) for i in range(10)]
    ev, _ = level_spread_ev(frames, spec.pattern, spec.black_level)
    assert ev < 0.02
    mixed = frames[:5] + [_flat(spec, Defects(), 99, level=0.45) for _ in range(5)]
    ev2, _ = level_spread_ev(mixed, spec.pattern, spec.black_level)
    assert ev2 > 0.3


def test_exposure_value_and_fit():
    assert abs(exposure_value(8, 1 / 100, 100) - 12.64) < 0.01
    assert abs(exposure_value(8, 1 / 100, 400) - 10.64) < 0.01
    fit = linear_fit([-2, -1, 0, 1, 2], [-2, -1, 0, 1.4, 2])
    assert fit.max_residual > 0.1 and abs(spread([1, 1.2, 0.9]) - 0.3) < 1e-9


def test_sharpness_drops_with_blur():
    spec = SensorSpec(width=480, height=320)
    rng = np.random.default_rng(0)
    sharp = synth_chart(spec, iso=100, rng=rng)
    soft = synth_chart(spec, iso=100, blur_sigma=3.0, rng=np.random.default_rng(0))
    p = AfPoint("c", 0.5, 0.5)
    assert region_sharpness(sharp, spec.pattern, spec.black_level, p) > 4 * region_sharpness(
        soft, spec.pattern, spec.black_level, p
    )
    assert sharpness_map(sharp, spec.pattern, spec.black_level).shape == (6, 8)
    assert coefficient_of_variation([1, 1, 1]) == 0
