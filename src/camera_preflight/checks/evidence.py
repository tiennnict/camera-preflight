"""Evidence images (PNG) written into the session folder (FR-REP-03)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from ..domain import EvidenceRef, Message

_MAX_SIDE = 800


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scale(shape: tuple[int, int]) -> float:
    return min(1.0, _MAX_SIDE / max(shape))


def pixel_map(
    out_dir: Path | None,
    name: str,
    shape: tuple[int, int],
    coords: Iterable[tuple[int, int]],
    caption: Message,
) -> EvidenceRef | None:
    """Defect locations drawn on a dark frame outline (coordinates are mosaic row, col)."""
    if out_dir is None:
        return None
    s = _scale(shape)
    w, h = max(int(shape[1] * s), 1), max(int(shape[0] * s), 1)
    img = Image.new("RGB", (w, h), (24, 24, 28))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(110, 110, 120))
    for r, c in coords:
        x, y = c * s, r * s
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(255, 190, 40), width=2)
    path = out_dir / f"{name}.png"
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return EvidenceRef(path=path.name, caption=caption, sha256=_sha(path))


def heat_map(
    out_dir: Path | None, name: str, data: NDArray[np.floating], caption: Message
) -> EvidenceRef | None:
    """Blue to red map of a 2-D array scaled to its own range."""
    if out_dir is None:
        return None
    arr = np.asarray(data, dtype=np.float64)
    lo, hi = float(arr.min()), float(arr.max())
    norm = (arr - lo) / (hi - lo) if hi > lo else np.zeros_like(arr)
    rgb = np.stack([norm, 1.0 - np.abs(norm - 0.5) * 2, 1.0 - norm], axis=-1)
    img = Image.fromarray((rgb * 255).astype(np.uint8))
    scale = max(1, _MAX_SIDE // max(img.size))
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
    path = out_dir / f"{name}.png"
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return EvidenceRef(path=path.name, caption=caption, sha256=_sha(path))


def marks_map(
    out_dir: Path | None,
    name: str,
    shape: tuple[int, int],
    marks: Iterable[tuple[float, float, float]],
    caption: Message,
) -> EvidenceRef | None:
    """Dust and mark outlines (row, col, radius in map pixels)."""
    if out_dir is None:
        return None
    s = _scale(shape)
    w, h = max(int(shape[1] * s), 1), max(int(shape[0] * s), 1)
    img = Image.new("RGB", (w, h), (232, 232, 236))
    draw = ImageDraw.Draw(img)
    for r, c, rad in marks:
        x, y, q = c * s, r * s, max(rad * s, 3)
        draw.ellipse([x - q, y - q, x + q, y + q], outline=(190, 60, 40), width=2)
    path = out_dir / f"{name}.png"
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return EvidenceRef(path=path.name, caption=caption, sha256=_sha(path))
