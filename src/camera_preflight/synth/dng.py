"""Minimal uncompressed CFA DNG writer for synthetic frames (little-endian TIFF)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

BYTE, ASCII, SHORT, LONG, RATIONAL, SRATIONAL = 1, 2, 3, 4, 5, 10
_SIZE = {BYTE: 1, ASCII: 1, SHORT: 2, LONG: 4, RATIONAL: 8, SRATIONAL: 8}
_CFA_CODE = {"R": 0, "G": 1, "B": 2}


@dataclass
class DngMeta:
    make: str = "SynthCam"
    model: str = "SC-1"
    serial: str | None = "SN0001"
    lens: str | None = "Synth 50mm f/1.8"
    iso: int = 100
    exposure_s: float = 1 / 100
    aperture: float = 8.0
    focal_length_mm: float = 50.0
    exposure_comp_ev: float = 0.0
    metering_mode: int = 5  # pattern
    capture_time: datetime | None = None
    sub_second: float = 0.0
    software: str | None = None
    black_level: int = 512
    white_level: int = 16383


def _ascii(text: str) -> bytes:
    return text.encode("ascii", "replace") + b"\x00"


def _rat(value: float, signed: bool = False) -> bytes:
    f = Fraction(value).limit_denominator(1_000_000)
    fmt = "<ii" if signed else "<II"
    return struct.pack(fmt, f.numerator, f.denominator)


class _Entry:
    def __init__(self, tag: int, typ: int, count: int, data: bytes) -> None:
        self.tag, self.typ, self.count, self.data = tag, typ, count, data


def _e_short(tag: int, *vals: int) -> _Entry:
    return _Entry(tag, SHORT, len(vals), struct.pack(f"<{len(vals)}H", *vals))


def _e_long(tag: int, *vals: int) -> _Entry:
    return _Entry(tag, LONG, len(vals), struct.pack(f"<{len(vals)}I", *vals))


def _e_byte(tag: int, *vals: int) -> _Entry:
    return _Entry(tag, BYTE, len(vals), bytes(vals))


def _e_ascii(tag: int, text: str) -> _Entry:
    data = _ascii(text)
    return _Entry(tag, ASCII, len(data), data)


def _e_rat(tag: int, *vals: float) -> _Entry:
    return _Entry(tag, RATIONAL, len(vals), b"".join(_rat(v) for v in vals))


def _e_srat(tag: int, *vals: float) -> _Entry:
    return _Entry(tag, SRATIONAL, len(vals), b"".join(_rat(v, True) for v in vals))


def _ifd_size(entries: list[_Entry]) -> int:
    size = 2 + 12 * len(entries) + 4
    for e in entries:
        if len(e.data) > 4:
            size += len(e.data) + (len(e.data) & 1)
    return size


def _build_ifd(entries: list[_Entry], offset: int) -> bytes:
    entries = sorted(entries, key=lambda e: e.tag)
    head = struct.pack("<H", len(entries))
    extra_off = offset + 2 + 12 * len(entries) + 4
    body = b""
    extra = b""
    for e in entries:
        if len(e.data) <= 4:
            value = e.data.ljust(4, b"\x00")
        else:
            value = struct.pack("<I", extra_off + len(extra))
            extra += e.data + (b"\x00" if len(e.data) & 1 else b"")
        body += struct.pack("<HHI", e.tag, e.typ, e.count) + value
    return head + body + struct.pack("<I", 0) + extra


def write_dng(
    path: Path,
    cfa: NDArray[np.float32],
    meta: DngMeta,
    pattern: str = "RGGB",
    extra_exif: dict[int, Any] | None = None,
) -> Path:
    """Write ``cfa`` (DN values) as a DNG that LibRaw and ExifTool can read."""
    h, w = cfa.shape
    pixels = np.clip(np.rint(cfa), 0, 65535).astype("<u2").tobytes()
    when = meta.capture_time or datetime(2026, 1, 1, 12, 0, 0)
    stamp = when.strftime("%Y:%m:%d %H:%M:%S")

    exif: list[_Entry] = [
        _e_rat(33434, meta.exposure_s),
        _e_rat(33437, meta.aperture),
        _e_short(34855, meta.iso),
        _e_ascii(36867, stamp),
        _e_srat(37380, meta.exposure_comp_ev),
        _e_short(37383, meta.metering_mode),
        _e_rat(37386, meta.focal_length_mm),
        _e_ascii(37521, f"{round(meta.sub_second * 1000):03d}"),
    ]
    if meta.serial:
        exif.append(_e_ascii(42033, meta.serial))
    if meta.lens:
        exif.append(_e_ascii(42036, meta.lens))
    if extra_exif:
        for tag, val in extra_exif.items():
            exif.append(_e_short(tag, int(val)))

    cfa_bytes = bytes(_CFA_CODE[c] for c in pattern)
    ifd0: list[_Entry] = [
        _e_long(254, 0),
        _e_long(256, w),
        _e_long(257, h),
        _e_short(258, 16),
        _e_short(259, 1),
        _e_short(262, 32803),
        _e_ascii(271, meta.make),
        _e_ascii(272, meta.model),
        _e_long(273, 0),  # patched below
        _e_short(274, 1),
        _e_short(277, 1),
        _e_long(278, h),
        _e_long(279, len(pixels)),
        _e_ascii(306, stamp),
        _e_short(33421, 2, 2),
        _Entry(33422, BYTE, 4, cfa_bytes),
        _e_long(34665, 0),  # patched below
        _e_byte(50706, 1, 4, 0, 0),
        _e_byte(50707, 1, 1, 0, 0),
        _e_ascii(50708, f"{meta.make} {meta.model}"),
        _e_byte(50710, 0, 1, 2),
        _e_short(50711, 1),
        _e_short(50714, meta.black_level),
        _e_long(50717, meta.white_level),
        _e_srat(50721, 0.9, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.9),
        _e_rat(50728, 0.5, 1.0, 0.5),
        _e_short(50778, 21),
    ]
    if meta.software:
        ifd0.append(_e_ascii(305, meta.software))
    if meta.serial:
        ifd0.append(_e_ascii(50735, meta.serial))

    ifd0_off = 8
    exif_off = ifd0_off + _ifd_size(ifd0)
    data_off = exif_off + _ifd_size(exif)
    data_off += data_off & 1
    for e in ifd0:
        if e.tag == 273:
            e.data = struct.pack("<I", data_off)
        if e.tag == 34665:
            e.data = struct.pack("<I", exif_off)
    blob = b"II*\x00" + struct.pack("<I", ifd0_off)
    blob += _build_ifd(ifd0, ifd0_off)
    blob += _build_ifd(exif, exif_off)
    blob += b"\x00" * (data_off - len(blob))
    blob += pixels
    path.write_bytes(blob)
    return path
