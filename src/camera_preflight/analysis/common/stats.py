"""Robust statistics used by the pixel analysis (R-15)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

_MAD_TO_SIGMA = 1.4826


def mad_sigma(values: NDArray[np.floating]) -> float:
    """Standard deviation estimated from the median absolute deviation."""
    arr = np.asarray(values, dtype=np.float64).ravel()
    if arr.size == 0:
        return 0.0
    med = float(np.median(arr))
    return float(np.median(np.abs(arr - med)) * _MAD_TO_SIGMA)


def local_residual(plane: NDArray[np.float32], size: int = 5) -> NDArray[np.float32]:
    """Plane minus its local median (same-colour neighbours)."""
    med = np.asarray(ndimage.median_filter(plane, size=size, mode="reflect"))
    return np.asarray(plane - med, dtype=np.float32)


def robust_z(residual: NDArray[np.float32]) -> NDArray[np.float32]:
    sigma = mad_sigma(residual)
    if sigma <= 0:
        sigma = 1e-6
    return (residual / sigma).astype(np.float32)


def label_components(mask: NDArray[np.bool_]) -> tuple[NDArray[np.int32], int]:
    labelled = np.zeros(mask.shape, dtype=np.int32)
    ndimage.label(mask, structure=np.ones((3, 3), dtype=int), output=labelled)
    return labelled, int(labelled.max())
