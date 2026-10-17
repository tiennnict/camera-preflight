"""Helpers H1 to H7: detect a physical action from live view, properties or storage (D-34).

Detectors take small grey frames (uint8) and return True when the condition holds. They are
pure functions so they can be tested on recorded live view. All limits are named parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]


@dataclass(frozen=True)
class HelperParams:
    dark_mean_max: float = 14.0  # [Guess] mean level of a covered sensor, 0..255
    flat_mean_min: float = 90.0  # [Guess]
    flat_mean_max: float = 240.0  # [Guess] not clipped
    flat_block_std_max: float = 8.0  # [Guess] spread of block means: even field
    chart_contrast_min: float = 35.0  # [Guess] std of a chart-filled frame
    chart_edge_share_min: float = 0.12  # [Guess] share of pixels on strong edges
    steady_diff_max: float = 3.0  # [Guess] mean frame to frame change
    timeout_s: float = 20.0  # [Guess] before the button fallback appears


def _blocks(frame: Frame, n: int = 6) -> NDArray[np.float64]:
    h, w = frame.shape
    return np.array(
        [
            frame[i * h // n : (i + 1) * h // n, j * w // n : (j + 1) * w // n].mean()
            for i in range(n)
            for j in range(n)
        ]
    )


def h1_dark(frame: Frame, p: HelperParams = HelperParams()) -> bool:
    """Body cap fitted and viewfinder covered: the frame is near black."""
    return float(frame.mean()) <= p.dark_mean_max


def h2_flat(frame: Frame, p: HelperParams = HelperParams()) -> bool:
    """Even bright field, defocused: mid to high level, little spatial variation."""
    mean = float(frame.mean())
    if not (p.flat_mean_min <= mean <= p.flat_mean_max):
        return False
    return (
        float(_blocks(frame).std()) <= p.flat_block_std_max
        and float(frame.std()) <= 4 * p.flat_block_std_max
    )


def h3_chart(frame: Frame, p: HelperParams = HelperParams()) -> bool:
    """AF chart in view: strong local contrast over most of the frame."""
    f = frame.astype(np.float64)
    if float(f.std()) < p.chart_contrast_min:
        return False
    gx = np.abs(np.diff(f, axis=1))
    return float((gx > 40).mean()) >= p.chart_edge_share_min


def h4_steady(prev: Frame, cur: Frame, p: HelperParams = HelperParams()) -> bool:
    """Camera on a tripod: consecutive live view frames barely change."""
    if prev.shape != cur.shape:
        return False
    return float(np.abs(prev.astype(np.int16) - cur.astype(np.int16)).mean()) <= p.steady_diff_max


def h5_lens_changed(initial: str | None, current: str | None) -> bool:
    return bool(current) and current != initial


def h6_focus_mode(value: str | None, wanted: str) -> bool | None:
    """None when the body does not expose the focus mode (the button takes over)."""
    return None if value is None else value.upper() == wanted.upper()


def h7_card_present(before: tuple[str, ...], now: tuple[str, ...]) -> bool:
    return len(now) > len(before) or (bool(now) and now != before)
