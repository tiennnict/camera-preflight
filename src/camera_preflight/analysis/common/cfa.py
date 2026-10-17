"""CFA helpers: split the mosaic into same-colour planes (R-08)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Plane = NDArray[np.float32]

# Offsets (row, col) of each of the four sites in a 2x2 block, for the CFA pattern string.
_SITES = ((0, 0), (0, 1), (1, 0), (1, 1))


def channel_names(pattern: str) -> tuple[str, str, str, str]:
    """Names such as ``R``, ``G1``, ``G2``, ``B`` for the sites of a 4-letter pattern."""
    if len(pattern) != 4 or set(pattern) - set("RGB"):
        raise ValueError(f"unsupported CFA pattern: {pattern!r}")
    seen_g = 0
    names: list[str] = []
    for ch in pattern:
        if ch == "G":
            seen_g += 1
            names.append(f"G{seen_g}")
        else:
            names.append(ch)
    return names[0], names[1], names[2], names[3]


def split_planes(array: NDArray[np.float32], pattern: str) -> dict[str, Plane]:
    """Quarter-resolution plane per colour site. Trims odd rows or columns."""
    h, w = array.shape
    h -= h % 2
    w -= w % 2
    names = channel_names(pattern)
    return {
        name: array[r:h:2, c:w:2].astype(np.float32, copy=False)
        for name, (r, c) in zip(names, _SITES, strict=True)
    }


def site_of(name: str, pattern: str) -> tuple[int, int]:
    return _SITES[channel_names(pattern).index(name)]


def plane_to_mosaic(name: str, pattern: str, row: int, col: int) -> tuple[int, int]:
    """Convert a coordinate in a colour plane back to mosaic (row, col)."""
    r, c = site_of(name, pattern)
    return row * 2 + r, col * 2 + c
