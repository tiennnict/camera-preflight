import numpy as np

from camera_preflight.analysis.common import binned_signal
from camera_preflight.analysis.dust import find_blobs, mark_sensor_side
from camera_preflight.analysis.uniformity import analyse_uniformity
from camera_preflight.synth import Defects, SensorSpec, synth_flat

KW = dict(depth_threshold=0.05, min_area=6, linear_elongation=6.0, linear_min_len=25)


def _flat(spec, d, aperture, seed=0, **kw):
    return synth_flat(
        spec, d, iso=100, exposure_s=0.01, aperture=aperture, rng=np.random.default_rng(seed), **kw
    )


def test_clean_flat_has_no_marks():
    spec = SensorSpec()
    sig = binned_signal(_flat(spec, Defects(), 22), spec.pattern, spec.black_level)
    blobs, _ = find_blobs(sig, **KW)
    assert blobs == []


def test_dust_found_and_sensor_side():
    spec = SensorSpec()
    d = Defects(dust=[(100, 150, 8.0), (200, 330, 8.0)])
    s22 = binned_signal(_flat(spec, d, 22), spec.pattern, spec.black_level)
    s8 = binned_signal(_flat(spec, d, 8, seed=1), spec.pattern, spec.black_level)
    blobs, _ = find_blobs(s22, **KW)
    _, rel8 = find_blobs(s8, **KW)
    assert len(blobs) == 2
    marked = mark_sensor_side(blobs, rel8, ratio=0.5)
    assert all(b.sensor_side for b in marked)
    assert not any(b.linear for b in marked)


def test_scratch_is_linear():
    spec = SensorSpec(width=640, height=480)
    d = Defects(scratch=(40, 60, 420, 120), scratch_depth=0.3)
    sig = binned_signal(_flat(spec, d, 22), spec.pattern, spec.black_level)
    blobs, _ = find_blobs(sig, **KW)
    assert any(b.linear for b in blobs)


def test_uniformity_reports_stripes_and_cast_free_flat():
    spec = SensorSpec()
    clean = analyse_uniformity(_flat(spec, Defects(), 8), spec.pattern, spec.black_level)
    banded = analyse_uniformity(
        _flat(spec, Defects(row_banding_dn=120.0), 8), spec.pattern, spec.black_level
    )
    assert clean.stripe_amp_rows < 0.01 and clean.asymmetry < 0.04 and clean.colour_cast < 0.03
    assert banded.stripe_amp_rows > 0.01
