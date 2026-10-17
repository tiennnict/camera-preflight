"""Metadata reader interface and normalisation (ARCHITECTURE section 2.2, D-42)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ..domain import FrameMeta
from .fields import EXIFTOOL_TAGS, MAKER_NOTE_TAG


class MetadataReader(Protocol):
    """Reads allowlisted fields only."""

    name: str

    def read(self, path: Path) -> FrameMeta: ...

    def close(self) -> None: ...


_FRACTION = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
METERING_MODES = {
    0: "Unknown",
    1: "Average",
    2: "Center-weighted",
    3: "Spot",
    4: "Multi-spot",
    5: "Multi-segment",
    6: "Partial",
}
_NR_OFF = {"off", "0", "false", "no", "disable", "disabled"}


def to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    m = _FRACTION.match(text)
    if m:
        den = float(m.group(2))
        return float(m.group(1)) / den if den else None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def to_int(value: Any) -> int | None:
    f = to_float(value)
    return None if f is None else int(round(f))


def to_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def to_datetime(value: Any) -> datetime | None:
    text = to_text(value)
    if not text:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:25] if "%z" in fmt else text[:19], fmt)
        except ValueError:
            continue
    return None


def to_sub_second(value: Any) -> float | None:
    text = to_text(value)
    if not text or not text.isdigit():
        return None
    return float(f"0.{text}")


def nr_state(value: Any) -> bool | None:
    """True when noise reduction is on, False when off, None when unknown."""
    text = to_text(value)
    if text is None:
        return None
    return text.lower() not in _NR_OFF


def metering_text(value: Any) -> str | None:
    text = to_text(value)
    if text is not None and text.isdigit():
        return METERING_MODES.get(int(text), text)
    return text


def normalise(raw: dict[str, Any]) -> FrameMeta:
    """Convert a mapping of tag name to value into ``FrameMeta`` using the allowlist."""

    def pick(field: str) -> Any:
        for tag in EXIFTOOL_TAGS[field]:
            if tag in raw and raw[tag] not in (None, ""):
                return raw[tag]
        return None

    sub = to_sub_second(pick("sub_second"))
    return FrameMeta(
        make=to_text(pick("make")),
        model=to_text(pick("model")),
        serial=to_text(pick("serial")),
        firmware=to_text(pick("firmware")),
        lens=to_text(pick("lens")),
        iso=to_int(pick("iso")),
        exposure_s=to_float(pick("exposure_s")),
        aperture=to_float(pick("aperture")),
        focal_length_mm=to_float(pick("focal_length_mm")),
        exposure_comp_ev=to_float(pick("exposure_comp_ev")),
        metering_mode=metering_text(pick("metering_mode")),
        focus_mode=to_text(pick("focus_mode")),
        af_point=to_text(pick("af_point")),
        af_fine_tune=to_int(pick("af_fine_tune")),
        shutter_type=to_text(pick("shutter_type")),
        file_type=to_text(pick("file_type")),
        file_number=to_int(pick("file_number")),
        shutter_count=to_int(pick("shutter_count")),
        temperature_c=to_float(pick("temperature_c")),
        capture_time=to_datetime(pick("capture_time")),
        sub_second=sub,
        long_exposure_nr=nr_state(pick("long_exposure_nr")),
        high_iso_nr=nr_state(pick("high_iso_nr")),
        software=to_text(pick("software")),
        has_maker_notes=MAKER_NOTE_TAG in raw,
        width=to_int(pick("width")),
        height=to_int(pick("height")),
    )
