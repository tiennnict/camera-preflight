import numpy as np
import rawpy

from camera_preflight.synth import Defects, SensorSpec, synth_dark, synth_flat, truth, write_dng
from camera_preflight.synth.dng import DngMeta


def test_dark_has_black_level_and_injected_hot_pixel():
    spec = SensorSpec()
    rng = np.random.default_rng(0)
    d = Defects(hot=[(40, 50)])
    frame = synth_dark(spec, d, iso=1600, exposure_s=30, rng=rng)
    expected = spec.black_level + spec.dark_current_e_s * 30 * 1600 / (
        spec.base_iso * spec.e_per_dn_base
    )
    assert abs(float(np.median(frame)) - expected) < 5
    assert frame[40, 50] > spec.black_level + 100


def test_flat_level_and_vignetting():
    spec = SensorSpec()
    frame = synth_flat(
        spec,
        Defects(),
        iso=100,
        exposure_s=0.01,
        aperture=8,
        level=0.6,
        rng=np.random.default_rng(1),
    )
    centre = frame[150:170, 220:260].mean()
    corner = frame[:20, :20].mean()
    assert centre > corner
    expected = spec.black_level + 0.6 * (spec.white_level - spec.black_level)
    assert abs(centre - expected) / expected < 0.08


def test_dust_is_darker_and_sharper_when_stopped_down():
    spec = SensorSpec()
    d = Defects(dust=[(100, 100, 6.0)])
    f8 = synth_flat(spec, d, iso=100, exposure_s=0.01, aperture=8, rng=np.random.default_rng(2))
    f22 = synth_flat(spec, d, iso=100, exposure_s=0.01, aperture=22, rng=np.random.default_rng(2))
    ref = f22[60:80, 60:80].mean()
    assert f22[100, 100] < f8[100, 100] < ref


def test_truth_lists_channels():
    t = truth(SensorSpec(), Defects(hot=[(10, 11)]))
    assert t["hot"][0]["channel"] in {"R", "G1", "G2", "B"}


def test_dng_roundtrip_through_libraw(tmp_path):
    spec = SensorSpec()
    frame = synth_dark(spec, Defects(), iso=100, exposure_s=0.01, rng=np.random.default_rng(3))
    path = write_dng(tmp_path / "a.dng", frame, DngMeta())
    with rawpy.imread(str(path)) as raw:
        assert raw.raw_image.shape == frame.shape
        assert np.array_equal(raw.raw_image, np.rint(frame).astype(np.uint16))
