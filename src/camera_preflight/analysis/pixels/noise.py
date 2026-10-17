"""Noise level and row/column banding on dark frames (B6)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..common import local_residual, mad_sigma, split_planes


@dataclass(frozen=True)
class NoiseReport:
    sigma_dn: dict[str, float]  # per channel, robust
    row_banding_dn: float
    col_banding_dn: float
    row_expected_dn: float
    col_expected_dn: float


def noise_and_banding(array: NDArray[np.float32], pattern: str) -> NoiseReport:
    sigmas = {
        name: mad_sigma(local_residual(plane))
        / 1.07  # median-filter residual inflates sigma slightly
        for name, plane in split_planes(array, pattern).items()
    }
    sigma = float(np.median(list(sigmas.values())))
    h, w = array.shape
    # Remove each channel's mean first so colour offsets do not look like banding.
    detrended = np.empty_like(array)
    for r, c in ((0, 0), (0, 1), (1, 0), (1, 1)):
        sub = array[r::2, c::2]
        detrended[r::2, c::2] = sub - np.median(sub)
    row_means = detrended.mean(axis=1)
    col_means = detrended.mean(axis=0)
    return NoiseReport(
        sigma_dn=sigmas,
        row_banding_dn=mad_sigma(row_means),
        col_banding_dn=mad_sigma(col_means),
        row_expected_dn=sigma / float(np.sqrt(w)),
        col_expected_dn=sigma / float(np.sqrt(h)),
    )
