"""Dust and mark detection on defocused flat frames (B4, R-06)."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from ..common import label_components

Map = NDArray[np.float32]


@dataclass(frozen=True)
class Blob:
    row: float  # centre, binned-pixel coordinates
    col: float
    area: int
    depth: float  # relative darkening at the darkest point
    major: float
    minor: float
    elongation: float
    linear: bool = False
    sensor_side: bool | None = None  # None until compared with the wide-aperture frame


def _poly_terms(y: NDArray[np.float64], x: NDArray[np.float64], degree: int) -> NDArray[np.float64]:
    cols = [(y**i) * (x**j) for i in range(degree + 1) for j in range(degree + 1 - i)]
    return np.stack(cols, axis=-1)


def trend_surface(signal: Map, degree: int = 4, step: int = 4) -> Map:
    """Slowly varying brightness (vignetting) as a polynomial surface fitted robustly."""
    h, w = signal.shape
    yy, xx = np.mgrid[0:h:step, 0:w:step]
    ys = (yy / max(h - 1, 1) * 2 - 1).astype(np.float64)
    xs = (xx / max(w - 1, 1) * 2 - 1).astype(np.float64)
    sub = signal[::step, ::step].astype(np.float64)
    design = _poly_terms(ys, xs, degree).reshape(-1, (degree + 1) * (degree + 2) // 2)
    target = sub.reshape(-1)
    keep = np.ones(target.size, dtype=bool)
    coef = np.zeros(design.shape[1])
    for _ in range(3):
        coef, *_rest = np.linalg.lstsq(design[keep], target[keep], rcond=None)
        resid = target - design @ coef
        keep = resid > -2.5 * float(np.std(resid[keep]))  # marks are darker than the trend
    fy, fx = np.mgrid[0:h, 0:w]
    full = _poly_terms(
        (fy / max(h - 1, 1) * 2 - 1).astype(np.float64),
        (fx / max(w - 1, 1) * 2 - 1).astype(np.float64),
        degree,
    )
    return np.asarray(full @ coef, dtype=np.float32)


def relative_map(signal: Map, smooth_sigma: float = 1.5) -> Map:
    """Signal divided by its trend, lightly smoothed: 1.0 = no mark."""
    smooth = ndimage.gaussian_filter(signal, smooth_sigma)
    trend = np.maximum(trend_surface(signal), 1e-6)
    return np.asarray(smooth / trend, dtype=np.float32)


def find_blobs(
    signal: Map,
    *,
    depth_threshold: float,
    min_area: int,
    linear_elongation: float,
    linear_min_len: float,
) -> tuple[list[Blob], Map]:
    """Dark marks in ``signal`` (binned flat frame). Returns blobs and the relative map."""
    rel = relative_map(signal)
    mask = rel < (1.0 - depth_threshold)
    labelled, n = label_components(mask)
    blobs: list[Blob] = []
    for idx in range(1, n + 1):
        ys, xs = np.nonzero(labelled == idx)
        area = int(ys.size)
        if area < min_area:
            continue
        depth = float(1.0 - rel[ys, xs].min())
        cy, cx = float(ys.mean()), float(xs.mean())
        if area >= 3:
            cov = np.cov(np.vstack([ys, xs]))
            eig = np.sort(np.maximum(np.linalg.eigvalsh(cov), 1e-9))[::-1]
            major, minor = float(4 * np.sqrt(eig[0])), float(4 * np.sqrt(eig[1]))
        else:
            major = minor = float(np.sqrt(area))
        elong = major / max(minor, 1e-6)
        linear = elong >= linear_elongation and major >= linear_min_len
        blobs.append(Blob(cy, cx, area, depth, major, minor, elong, linear))
    return blobs, rel


def mark_sensor_side(
    small_aperture: list[Blob], wide_rel: Map, *, ratio: float, radius: int = 3
) -> list[Blob]:
    """Compare depth at the same place in the wide-aperture frame (sensor-side marks fade)."""
    out: list[Blob] = []
    h, w = wide_rel.shape
    for b in small_aperture:
        r0, r1 = max(int(b.row) - radius, 0), min(int(b.row) + radius + 1, h)
        c0, c1 = max(int(b.col) - radius, 0), min(int(b.col) + radius + 1, w)
        wide_depth = float(1.0 - wide_rel[r0:r1, c0:c1].min())
        sensor_side = wide_depth < ratio * b.depth
        out.append(
            Blob(
                b.row, b.col, b.area, b.depth, b.major, b.minor, b.elongation, b.linear, sensor_side
            )
        )
    return out


def region_counts(
    blobs: list[Blob], shape: tuple[int, int], grid: tuple[int, int] = (3, 3)
) -> NDArray[np.int32]:
    """Number of marks per region of a grid (for the region map)."""
    out = np.zeros(grid, dtype=np.int32)
    h, w = shape
    for b in blobs:
        gr = min(int(b.row / h * grid[0]), grid[0] - 1)
        gc = min(int(b.col / w * grid[1]), grid[1] - 1)
        out[gr, gc] += 1
    return out
