"""Brightness uniformity of a flat frame (B5)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..common import split_planes

Map = NDArray[np.float32]


@dataclass(frozen=True)
class UniformityReport:
    grid: Map  # brightness grid, relative to the frame mean
    stripe_amp_rows: float
    stripe_amp_cols: float
    colour_cast: float  # largest deviation of R/G or B/G from its frame mean, relative
    asymmetry: float  # left-right difference after mirroring, relative


def _profile_amplitude(profile: NDArray[np.floating]) -> float:
    """Amplitude of a 1-D profile after removing a quadratic trend (vignetting)."""
    x = np.linspace(-1, 1, profile.size)
    coeffs = np.polyfit(x, profile, 2)
    resid = profile - np.polyval(coeffs, x)
    return float(np.percentile(np.abs(resid), 98))


def analyse_uniformity(
    array: NDArray[np.float32], pattern: str, black_level: float, grid: tuple[int, int] = (6, 8)
) -> UniformityReport:
    planes = {k: v - black_level for k, v in split_planes(array, pattern).items()}
    mean_plane = np.mean(np.stack(list(planes.values())), axis=0)
    mean = float(mean_plane.mean())
    mean = max(mean, 1e-6)
    h, w = mean_plane.shape
    gr, gc = grid
    cells = np.zeros(grid, dtype=np.float32)
    for i in range(gr):
        for j in range(gc):
            cells[i, j] = mean_plane[
                i * h // gr : (i + 1) * h // gr, j * w // gc : (j + 1) * w // gc
            ].mean()
    rows = mean_plane.mean(axis=1) / mean
    cols = mean_plane.mean(axis=0) / mean
    green = (planes.get("G1", mean_plane) + planes.get("G2", mean_plane)) / 2
    green = np.maximum(green, 1e-6)
    cast = 0.0
    for name in ("R", "B"):
        if name in planes:
            ratio = planes[name] / green
            ratio_grid = np.array(
                [
                    [
                        ratio[
                            i * h // gr : (i + 1) * h // gr, j * w // gc : (j + 1) * w // gc
                        ].mean()
                        for j in range(gc)
                    ]
                    for i in range(gr)
                ]
            )
            cast = max(cast, float(np.abs(ratio_grid / ratio_grid.mean() - 1).max()))
    left = cells[:, : gc // 2]
    right = cells[:, gc - gc // 2 :][:, ::-1]
    asym = float(np.abs(left - right).max() / mean)
    return UniformityReport(
        grid=(cells / mean).astype(np.float32),
        stripe_amp_rows=_profile_amplitude(rows),
        stripe_amp_cols=_profile_amplitude(cols),
        colour_cast=cast,
        asymmetry=asym,
    )
