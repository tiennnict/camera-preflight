"""Curtain travel gradients and exposure repeatability (C2, C3, C4)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..common import binned_signal


@dataclass(frozen=True)
class CurtainReport:
    gradient_rows: float  # relative brightness change from first to last row, after reference
    gradient_cols: float


def _profiles(
    array: NDArray[np.float32], pattern: str, black: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    sig = binned_signal(array, pattern, black).astype(np.float64)
    mean = max(float(sig.mean()), 1e-6)
    return sig.mean(axis=1) / mean, sig.mean(axis=0) / mean


def _slope_change(profile: NDArray[np.float64]) -> float:
    """Linear fit change across the profile (end minus start)."""
    x = np.linspace(0.0, 1.0, profile.size)
    slope = np.polyfit(x, profile, 1)[0]
    return float(slope)


def curtain_gradient(
    fast: list[NDArray[np.float32]],
    reference: list[NDArray[np.float32]],
    pattern: str,
    black: float,
) -> CurtainReport:
    """Gradient of a fast-speed set relative to a slow reference set (R-05).

    Profiles are averaged over the frames of each set, the reference profile is subtracted
    (it holds the lens and light-source falloff), and the remaining linear trend along each
    axis is the gradient.
    """
    f_rows = np.mean([_profiles(a, pattern, black)[0] for a in fast], axis=0)
    f_cols = np.mean([_profiles(a, pattern, black)[1] for a in fast], axis=0)
    r_rows = np.mean([_profiles(a, pattern, black)[0] for a in reference], axis=0)
    r_cols = np.mean([_profiles(a, pattern, black)[1] for a in reference], axis=0)
    return CurtainReport(
        gradient_rows=_slope_change(f_rows - r_rows),
        gradient_cols=_slope_change(f_cols - r_cols),
    )


def level_spread_ev(
    frames: list[NDArray[np.float32]], pattern: str, black: float
) -> tuple[float, tuple[float, ...]]:
    """Range of mean signal across identical frames, in EV (C3)."""
    levels = [float(binned_signal(a, pattern, black).mean()) for a in frames]
    ev = np.log2(np.maximum(levels, 1e-6))
    return float(ev.max() - ev.min()), tuple(levels)
