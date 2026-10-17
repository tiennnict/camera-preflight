"""Hot, stuck and dead pixel detection on CFA planes (B1 to B3, R-08, R-15)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from ..common import (
    label_components,
    local_residual,
    plane_to_mosaic,
    robust_sigma,
    split_planes,
)

Coord = tuple[int, int]


@dataclass(frozen=True)
class PixelDefect:
    row: int
    col: int
    channel: str
    kind: str  # "hot", "stuck_bright", "dead", "bright" (not yet classified)
    excess: float  # DN over the local median (negative for dead pixels)


def bright_outliers(
    array: NDArray[np.float32],
    pattern: str,
    *,
    k_sigma: float,
    min_excess_dn: float,
) -> dict[Coord, tuple[str, float]]:
    """Pixels brighter than their same-colour neighbours by k robust sigmas.

    Returns mosaic (row, col) -> (channel, excess in DN). The threshold per channel is
    derived from the median absolute deviation of the residual, so a few outliers do not
    inflate it.
    """
    found: dict[Coord, tuple[str, float]] = {}
    for name, plane in split_planes(array, pattern).items():
        residual = local_residual(plane)
        sigma = max(robust_sigma(residual), 1e-3)
        mask = (residual > k_sigma * sigma) & (residual > min_excess_dn)
        for r, c in np.argwhere(mask):
            mr, mc = plane_to_mosaic(name, pattern, int(r), int(c))
            found[(mr, mc)] = (name, float(residual[r, c]))
    return found


def repeated_bright(
    frames: list[NDArray[np.float32]],
    pattern: str,
    *,
    k_sigma: float,
    min_excess_dn: float,
    repeat_min: int,
) -> dict[Coord, tuple[str, float]]:
    """Bright outliers present at the same coordinates in at least ``repeat_min`` frames.

    The reported excess is the median across the frames that show the pixel.
    """
    per_frame = [
        bright_outliers(f, pattern, k_sigma=k_sigma, min_excess_dn=min_excess_dn) for f in frames
    ]
    counts: dict[Coord, list[tuple[str, float]]] = {}
    for found in per_frame:
        for coord, value in found.items():
            counts.setdefault(coord, []).append(value)
    need = min(repeat_min, len(frames))
    return {
        coord: (vals[0][0], float(np.median([v[1] for v in vals])))
        for coord, vals in counts.items()
        if len(vals) >= need
    }


def flat_outliers(
    frames: list[NDArray[np.float32]],
    pattern: str,
    black_level: float,
    *,
    rel_dev: float,
) -> tuple[dict[Coord, tuple[str, float]], dict[Coord, tuple[str, float]]]:
    """Stuck-bright and dead pixels in flat frames (B2).

    A pixel counts when it deviates from its same-colour neighbours by more than ``rel_dev``
    of the local signal in every frame. Returns (stuck_bright, dead) maps with the relative
    deviation as value.
    """
    bright: dict[Coord, list[tuple[str, float]]] = {}
    dark: dict[Coord, list[tuple[str, float]]] = {}
    for frame in frames:
        for name, plane in split_planes(frame, pattern).items():
            med = np.asarray(ndimage.median_filter(plane, size=5, mode="reflect"))
            signal = np.maximum(med - black_level, 1.0)
            rel = (plane - med) / signal
            for r, c in np.argwhere(rel > rel_dev):
                key = plane_to_mosaic(name, pattern, int(r), int(c))
                bright.setdefault(key, []).append((name, float(rel[r, c])))
            for r, c in np.argwhere(rel < -rel_dev):
                key = plane_to_mosaic(name, pattern, int(r), int(c))
                dark.setdefault(key, []).append((name, float(rel[r, c])))
    n = len(frames)
    stuck = {
        k: (v[0][0], float(np.median([x[1] for x in v]))) for k, v in bright.items() if len(v) == n
    }
    dead = {
        k: (v[0][0], float(np.median([x[1] for x in v]))) for k, v in dark.items() if len(v) == n
    }
    return stuck, dead


def cluster_defects(
    coords: list[Coord], shape: tuple[int, int], distance_px: int
) -> list[list[Coord]]:
    """Group defects that lie within ``distance_px`` of each other (cluster = adjacent defects)."""
    if not coords:
        return []
    mask = np.zeros(shape, dtype=bool)
    for r, c in coords:
        mask[r, c] = True
    grown = np.asarray(
        ndimage.binary_dilation(
            mask, structure=np.ones((3, 3), dtype=bool), iterations=max(1, distance_px // 2)
        )
    )
    labelled, n = label_components(np.asarray(grown, dtype=np.bool_))
    groups: list[list[Coord]] = [[] for _ in range(n)]
    for r, c in coords:
        groups[int(labelled[r, c]) - 1].append((r, c))
    return [g for g in groups if g]


def classify(
    short: dict[Coord, tuple[str, float]],
    long_: dict[Coord, tuple[str, float]],
    *,
    exposure_ratio: float,
    growth_ratio: float,
) -> dict[Coord, str]:
    """Hot (excess grows with exposure) versus stuck bright (excess does not) (B3).

    ``short`` and ``long_`` are bright-outlier maps of dark frames taken at two exposures with
    the same ISO; ``exposure_ratio`` is long / short exposure time.
    """
    out: dict[Coord, str] = {}
    for coord, (_, excess_long) in long_.items():
        if coord not in short:
            out[coord] = "hot"  # absent at the short exposure: grows with exposure
            continue
        excess_short = max(short[coord][1], 1e-6)
        ratio = excess_long / excess_short
        out[coord] = "hot" if ratio >= min(growth_ratio, exposure_ratio) else "stuck_bright"
    return out
