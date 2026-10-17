"""Exposure and linearity analysis for the E group."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2

import numpy as np


def exposure_value(aperture: float, exposure_s: float, iso: float) -> float:
    """EV at ISO 100: log2(N^2 / t) - log2(ISO / 100)."""
    return log2(aperture**2 / exposure_s) - log2(iso / 100.0)


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float
    max_residual: float
    residuals: tuple[float, ...]


def linear_fit(x: list[float], y: list[float]) -> LinearFit:
    xa, ya = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if xa.size < 2 or float(np.ptp(xa)) == 0.0:
        return LinearFit(0.0, float(ya[0]) if ya.size else 0.0, 0.0, ())
    slope, intercept = np.polyfit(xa, ya, 1)
    resid = ya - (slope * xa + intercept)
    return LinearFit(
        float(slope), float(intercept), float(np.abs(resid).max()), tuple(float(r) for r in resid)
    )


def spread(values: list[float]) -> float:
    return float(max(values) - min(values)) if values else 0.0


def log2_levels(levels: list[float]) -> list[float]:
    return [float(np.log2(max(v, 1e-6))) for v in levels]
