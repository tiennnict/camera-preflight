"""Burst rhythm from capture timestamps (C1)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BurstReport:
    intervals_s: tuple[float, ...]
    median_s: float
    fps: float
    cv: float
    max_ratio: float  # longest interval over the median
    resolution_s: float  # smallest non-zero timestamp step seen


def burst_rhythm(timestamps: list[float]) -> BurstReport | None:
    """Intervals between consecutive captures. None when fewer than two timestamps."""
    if len(timestamps) < 2:
        return None
    ts = np.sort(np.asarray(timestamps, dtype=np.float64))
    gaps = np.diff(ts)
    median = float(np.median(gaps))
    nonzero = gaps[gaps > 0]
    resolution = float(nonzero.min()) if nonzero.size else float("inf")
    cv = float(gaps.std() / gaps.mean()) if gaps.mean() > 0 else float("inf")
    ratio = float(gaps.max() / median) if median > 0 else float("inf")
    fps = 1.0 / median if median > 0 else float("inf")
    return BurstReport(tuple(float(g) for g in gaps), median, fps, cv, ratio, resolution)
