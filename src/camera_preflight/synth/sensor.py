"""Synthetic CFA frame generator with defect injection and ground truth (WP-05, NFR-02).

Noise model: electrons follow Poisson statistics, converted to digital numbers (DN) with an
ISO-dependent gain, plus Gaussian read noise. Values are parameters of the simulation, not
claims about real cameras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from ..analysis.common.cfa import site_of

Array = NDArray[np.float32]


@dataclass
class SensorSpec:
    width: int = 480
    height: int = 320
    pattern: str = "RGGB"
    black_level: float = 512.0
    white_level: float = 16383.0
    base_iso: int = 100
    e_per_dn_base: float = 4.0
    read_noise_dn: float = 1.6
    dark_current_e_s: float = 0.2
    vignetting: float = 0.25


@dataclass
class Defects:
    """Defects to inject; coordinates are mosaic (row, col)."""

    hot: list[tuple[int, int]] = field(default_factory=list)
    hot_rate_e_s: float = 400.0
    stuck_bright: list[tuple[int, int]] = field(default_factory=list)
    dead: list[tuple[int, int]] = field(default_factory=list)
    cluster: list[tuple[int, int]] = field(default_factory=list)
    dust: list[tuple[int, int, float]] = field(default_factory=list)  # row, col, radius px
    dust_depth: float = 0.45
    scratch: tuple[int, int, int, int] | None = None  # r0, c0, r1, c1
    scratch_depth: float = 0.25
    row_banding_dn: float = 0.0
    col_banding_dn: float = 0.0
    curtain_gradient: float = 0.0  # relative brightness change across the frame height
    flicker_amplitude: float = 0.0
    flicker_period_rows: float = 40.0
    flicker_phase: float = 0.0


def _gain(spec: SensorSpec, iso: int) -> float:
    """Electrons per DN at the given ISO."""
    return spec.e_per_dn_base * spec.base_iso / max(iso, 1)


def _dust_attenuation(spec: SensorSpec, d: Defects, aperture: float) -> Array:
    h, w = spec.height, spec.width
    att = np.ones((h, w), dtype=np.float32)
    if not d.dust:
        return att
    yy, xx = np.mgrid[0:h, 0:w]
    # Shadows are sharper and darker when the lens is stopped down.
    sharp = float(np.clip(aperture / 22.0, 0.15, 1.0))
    softness = 1.5 + 14.0 * (1.0 - sharp)
    for r, c, rad in d.dust:
        dist = np.hypot(yy - r, xx - c)
        profile = 1.0 / (1.0 + np.exp(np.clip((dist - rad) / (softness * 0.35), -50, 50)))
        att *= 1.0 - d.dust_depth * sharp * profile.astype(np.float32)
    return att


def _scratch_attenuation(spec: SensorSpec, d: Defects) -> Array:
    h, w = spec.height, spec.width
    att = np.ones((h, w), dtype=np.float32)
    if d.scratch is None:
        return att
    r0, c0, r1, c1 = d.scratch
    n = int(max(abs(r1 - r0), abs(c1 - c0)) * 2) + 2
    line = np.zeros((h, w), dtype=np.float32)
    rr = np.clip(np.linspace(r0, r1, n).round().astype(int), 0, h - 1)
    cc = np.clip(np.linspace(c0, c1, n).round().astype(int), 0, w - 1)
    line[rr, cc] = 1.0
    line = ndimage.gaussian_filter(line, 1.0)
    line /= max(float(line.max()), 1e-6)
    return (1.0 - d.scratch_depth * line).astype(np.float32)


def _apply_pixel_defects(
    dn: Array, spec: SensorSpec, d: Defects, exposure_s: float, iso: int
) -> None:
    e_per_dn = _gain(spec, iso)
    hot_dn = d.hot_rate_e_s * exposure_s / e_per_dn
    for r, c in [*d.hot, *d.cluster]:
        dn[r, c] += hot_dn
    for r, c in d.stuck_bright:
        dn[r, c] = spec.white_level * 0.97
    for r, c in d.dead:
        dn[r, c] = spec.black_level


def synth_dark(
    spec: SensorSpec,
    defects: Defects,
    *,
    iso: int,
    exposure_s: float,
    rng: np.random.Generator,
) -> Array:
    """Body-cap frame."""
    h, w = spec.height, spec.width
    e_per_dn = _gain(spec, iso)
    electrons = rng.poisson(spec.dark_current_e_s * exposure_s + 0.0, size=(h, w)).astype(
        np.float32
    )
    dn = spec.black_level + electrons / e_per_dn + rng.normal(0, spec.read_noise_dn, (h, w))
    dn = dn.astype(np.float32)
    if defects.row_banding_dn:
        dn += rng.normal(0, defects.row_banding_dn, (h, 1)).astype(np.float32)
    if defects.col_banding_dn:
        dn += rng.normal(0, defects.col_banding_dn, (1, w)).astype(np.float32)
    _apply_pixel_defects(dn, spec, defects, exposure_s, iso)
    return np.clip(dn, 0, spec.white_level).astype(np.float32)


def synth_flat(
    spec: SensorSpec,
    defects: Defects,
    *,
    iso: int,
    exposure_s: float,
    aperture: float,
    level: float = 0.6,
    rng: np.random.Generator,
    shift: tuple[float, float] = (0.0, 0.0),
) -> Array:
    """Even grey target. ``level`` is the mean signal as a fraction of the usable range."""
    h, w = spec.height, spec.width
    e_per_dn = _gain(spec, iso)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy, cx = h / 2 + shift[0], w / 2 + shift[1]
    rmax = np.hypot(h / 2, w / 2)
    vign = 1.0 - spec.vignetting * (np.hypot(yy - cy, xx - cx) / rmax) ** 2
    illum = vign * _dust_attenuation(spec, defects, aperture) * _scratch_attenuation(spec, defects)
    if defects.curtain_gradient:
        illum = illum * (1.0 + defects.curtain_gradient * (yy / h - 0.5))
    if defects.flicker_amplitude:
        illum = illum * (
            1.0
            + defects.flicker_amplitude
            * np.sin(2 * np.pi * yy / defects.flicker_period_rows + defects.flicker_phase)
        )
    usable = spec.white_level - spec.black_level
    mean_e = level * usable * e_per_dn * illum
    electrons = rng.poisson(np.maximum(mean_e, 0)).astype(np.float32)
    dn = spec.black_level + electrons / e_per_dn + rng.normal(0, spec.read_noise_dn, (h, w))
    dn = dn.astype(np.float32)
    if defects.row_banding_dn:
        dn += rng.normal(0, defects.row_banding_dn, (h, 1)).astype(np.float32)
    if defects.col_banding_dn:
        dn += rng.normal(0, defects.col_banding_dn, (1, w)).astype(np.float32)
    _apply_pixel_defects(dn, spec, defects, exposure_s, iso)
    return np.clip(dn, 0, spec.white_level).astype(np.float32)


def synth_chart(
    spec: SensorSpec,
    *,
    iso: int,
    blur_sigma: float | dict[tuple[int, int], float] = 0.0,
    grid: tuple[int, int] = (3, 3),
    rng: np.random.Generator,
    seed_texture: int = 7,
) -> Array:
    """High-contrast texture; ``blur_sigma`` can differ per grid cell (row, col)."""
    h, w = spec.height, spec.width
    tex_rng = np.random.default_rng(seed_texture)
    base = tex_rng.random((h // 4 + 1, w // 4 + 1)) > 0.5
    tex = np.kron(base, np.ones((4, 4)))[:h, :w].astype(np.float32)
    if isinstance(blur_sigma, dict):
        out = tex.copy()
        gh, gw = grid
        for (gr, gc), sig in blur_sigma.items():
            r0, r1 = gr * h // gh, (gr + 1) * h // gh
            c0, c1 = gc * w // gw, (gc + 1) * w // gw
            if sig > 0:
                out[r0:r1, c0:c1] = ndimage.gaussian_filter(tex, sig)[r0:r1, c0:c1]
    else:
        out = ndimage.gaussian_filter(tex, blur_sigma) if blur_sigma > 0 else tex
    e_per_dn = _gain(spec, iso)
    usable = spec.white_level - spec.black_level
    mean_e = (0.15 + 0.5 * out) * usable * e_per_dn
    electrons = rng.poisson(mean_e).astype(np.float32)
    dn = spec.black_level + electrons / e_per_dn + rng.normal(0, spec.read_noise_dn, (h, w))
    return np.clip(dn, 0, spec.white_level).astype(np.float32)


def truth(spec: SensorSpec, d: Defects) -> dict[str, Any]:
    """Ground truth in mosaic coordinates with the colour site of each pixel defect."""

    def site(rc: tuple[int, int]) -> str:
        from ..analysis.common.cfa import channel_names

        names = channel_names(spec.pattern)
        idx = [site_of(n, spec.pattern) for n in names].index((rc[0] % 2, rc[1] % 2))
        return names[idx]

    return {
        "hot": [{"row": r, "col": c, "channel": site((r, c))} for r, c in d.hot],
        "cluster": [{"row": r, "col": c, "channel": site((r, c))} for r, c in d.cluster],
        "stuck_bright": [{"row": r, "col": c} for r, c in d.stuck_bright],
        "dead": [{"row": r, "col": c} for r, c in d.dead],
        "dust": [{"row": r, "col": c, "radius": rad} for r, c, rad in d.dust],
        "scratch": list(d.scratch) if d.scratch else None,
    }
