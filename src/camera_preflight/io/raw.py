"""RAW decoding to CFA arrays through rawpy/LibRaw (FR-META-01, R-08)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rawpy

from ..domain import CfaData
from .errors import RawDecodeError, UnsupportedFormat

RAW_SUFFIXES = frozenset({".cr2", ".cr3", ".nef", ".nrw", ".arw", ".dng"})
JPEG_SUFFIXES = frozenset({".jpg", ".jpeg"})
_COLOR_LETTER = {"R": "R", "G": "G", "B": "B", "E": "G"}


def is_raw(path: Path) -> bool:
    return path.suffix.lower() in RAW_SUFFIXES


def is_jpeg(path: Path) -> bool:
    return path.suffix.lower() in JPEG_SUFFIXES


def _pattern_from(raw: rawpy.RawPy) -> str:
    desc = raw.color_desc.decode("ascii", "replace")
    pat = raw.raw_pattern
    assert pat is not None
    # The visible area can start on an odd row or column, which shifts the 2x2 phase.
    dr = int(raw.sizes.top_margin) % 2
    dc = int(raw.sizes.left_margin) % 2
    letters = [
        _COLOR_LETTER.get(desc[int(pat[(i + dr) % 2][(j + dc) % 2])], "?")
        for i in range(2)
        for j in range(2)
    ]
    pattern = "".join(letters)
    if len(pattern) != 4 or "?" in pattern:
        raise RawDecodeError(f"unsupported CFA layout: {pattern!r}")
    return pattern


def decode_raw(path: Path) -> CfaData:
    """Decode the mosaic with black and white levels. Raises ``UnsupportedFormat`` for non-RAW."""
    if not is_raw(path):
        raise UnsupportedFormat(path.suffix)
    try:
        with rawpy.imread(str(path)) as raw:
            array = np.array(raw.raw_image_visible, dtype=np.float32)
            blacks = list(raw.black_level_per_channel)
            black = float(np.mean(blacks)) if blacks else 0.0
            white = float(raw.white_level)
            pattern = _pattern_from(raw)
    except (rawpy.LibRawFileUnsupportedError, rawpy.LibRawNoThumbnailError) as exc:
        raise UnsupportedFormat(str(exc)) from exc
    except rawpy.LibRawError as exc:
        raise RawDecodeError(str(exc)) from exc
    except OSError as exc:
        raise RawDecodeError(str(exc)) from exc
    return CfaData(array=array, pattern=pattern, black_level=black, white_level=white)
