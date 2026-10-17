import numpy as np

from camera_preflight.analysis.pixels import (
    classify,
    cluster_defects,
    flat_outliers,
    noise_and_banding,
    repeated_bright,
)
from camera_preflight.synth import Defects, SensorSpec, synth_dark, synth_flat, truth


def _dark_set(spec, d, iso, t, n=3, seed=0):
    return [
        synth_dark(spec, d, iso=iso, exposure_s=t, rng=np.random.default_rng(seed + i))
        for i in range(n)
    ]


def test_hot_pixels_detected_with_few_false_positives():
    spec = SensorSpec()
    rng = np.random.default_rng(5)
    hot = [
        (int(r), int(c))
        for r, c in zip(rng.integers(10, 300, 12), rng.integers(10, 460, 12), strict=True)
    ]
    d = Defects(hot=hot, hot_rate_e_s=400.0)
    frames = _dark_set(spec, d, 1600, 0.5)
    found = repeated_bright(frames, spec.pattern, k_sigma=6, min_excess_dn=8, repeat_min=2)
    hits = sum(1 for p in hot if p in found)
    false = [p for p in found if p not in hot]
    assert hits >= 11
    assert len(false) <= 1  # NFR-02: at most 1 false defect per 10 megapixels is scaled to 0.15 MP
    assert truth(spec, d)["hot"][0]["channel"] == found[hot[0]][0] if hot[0] in found else True


def test_no_defects_gives_no_detections():
    spec = SensorSpec()
    frames = _dark_set(spec, Defects(), 1600, 0.5)
    assert repeated_bright(frames, spec.pattern, k_sigma=6, min_excess_dn=8, repeat_min=2) == {}


def test_cluster_grouping():
    groups = cluster_defects([(10, 10), (10, 12), (100, 100)], (200, 200), 2)
    assert sorted(len(g) for g in groups) == [1, 2]


def test_flat_stuck_and_dead():
    spec = SensorSpec()
    d = Defects(stuck_bright=[(50, 60)], dead=[(80, 90)])
    frames = [
        synth_flat(
            spec,
            d,
            iso=100,
            exposure_s=0.01,
            aperture=8,
            rng=np.random.default_rng(i),
            shift=(i, i),
        )
        for i in range(3)
    ]
    stuck, dead = flat_outliers(frames, spec.pattern, spec.black_level, rel_dev=0.25)
    assert (50, 60) in stuck and (80, 90) in dead
    assert len(stuck) + len(dead) <= 4


def test_classify_hot_versus_stuck():
    spec = SensorSpec()
    d = Defects(hot=[(40, 40)], stuck_bright=[(60, 60)], hot_rate_e_s=2000.0)
    short = repeated_bright(
        _dark_set(spec, d, 400, 0.05), spec.pattern, k_sigma=6, min_excess_dn=8, repeat_min=2
    )
    long_ = repeated_bright(
        _dark_set(spec, d, 400, 0.5), spec.pattern, k_sigma=6, min_excess_dn=8, repeat_min=2
    )
    kinds = classify(short, long_, exposure_ratio=10, growth_ratio=1.5)
    assert kinds[(40, 40)] == "hot" and kinds[(60, 60)] == "stuck_bright"


def test_banding_detected_only_when_present():
    spec = SensorSpec()
    clean = synth_dark(spec, Defects(), iso=1600, exposure_s=0.01, rng=np.random.default_rng(1))
    banded = synth_dark(
        spec, Defects(row_banding_dn=1.0), iso=1600, exposure_s=0.01, rng=np.random.default_rng(1)
    )
    a = noise_and_banding(clean, spec.pattern)
    b = noise_and_banding(banded, spec.pattern)
    assert a.row_banding_dn < 3 * a.row_expected_dn
    assert b.row_banding_dn > 3 * b.row_expected_dn
