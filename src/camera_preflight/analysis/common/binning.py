"""Luminance-like map from a CFA frame: the mean of the four colour planes, black removed."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .cfa import split_planes


def binned_signal(
    array: NDArray[np.float32], pattern: str, black_level: float
) -> NDArray[np.float32]:
    """Half-resolution map of signal above black (mean of R, G1, G2, B)."""
    planes = list(split_planes(array, pattern).values())
    stack = np.stack(planes, axis=0)
    return np.asarray(stack.mean(axis=0) - black_level, dtype=np.float32)
