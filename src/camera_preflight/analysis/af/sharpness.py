"""Sharpness measures for autofocus checks (D3, D4)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from ..common import binned_signal


@dataclass(frozen=True)
class AfPoint:
    """An AF point in normalised frame coordinates (0..1) with a half-size window."""

    name: str
    x: float
    y: float
    half: float = 0.06
    is_centre: bool = False


def region_sharpness(
    array: NDArray[np.float32], pattern: str, black: float, point: AfPoint
) -> float:
    """Mean gradient energy inside the window around ``point``, relative to local signal."""
    sig = binned_signal(array, pattern, black).astype(np.float64)
    h, w = sig.shape
    r0, r1 = max(int((point.y - point.half) * h), 0), min(int((point.y + point.half) * h), h)
    c0, c1 = max(int((point.x - point.half) * w), 0), min(int((point.x + point.half) * w), w)
    win = sig[r0:r1, c0:c1]
    if win.size < 16:
        return 0.0
    gy = ndimage.sobel(win, axis=0)
    gx = ndimage.sobel(win, axis=1)
    energy = float(np.mean(gx * gx + gy * gy))
    scale = max(float(win.mean()), 1e-6) ** 2
    return energy / scale


def sharpness_map(
    array: NDArray[np.float32], pattern: str, black: float, grid: tuple[int, int] = (6, 8)
) -> NDArray[np.float32]:
    """Sharpness per region of a grid (D6)."""
    gr, gc = grid
    out = np.zeros(grid, dtype=np.float32)
    for i in range(gr):
        for j in range(gc):
            p = AfPoint(f"{i},{j}", (j + 0.5) / gc, (i + 0.5) / gr, half=0.5 / max(gr, gc))
            out[i, j] = region_sharpness(array, pattern, black, p)
    return out


def coefficient_of_variation(values: list[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size < 2 or arr.mean() <= 0:
        return 0.0
    return float(arr.std() / arr.mean())
