"""Plain formatting of settings for rejection reasons (value found and value needed, D-44)."""

from __future__ import annotations


def fmt_exposure(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds >= 0.95:
        return f"{seconds:g} s"
    return f"1/{round(1 / seconds)} s"


def fmt_aperture(value: float | None) -> str:
    return "unknown" if value is None else f"f/{value:g}"


def fmt_iso(value: int | None) -> str:
    return "unknown" if value is None else str(value)


def fmt_percent(fraction: float) -> str:
    pct = fraction * 100
    return f"{pct:.2g}" if pct < 10 else f"{pct:.0f}"
