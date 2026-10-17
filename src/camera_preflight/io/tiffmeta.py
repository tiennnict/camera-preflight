"""In-house metadata reader for TIFF-based files (DNG, CR2, NEF, ARW) and JPEG (D-42).

Reads the standard EXIF fields only. It is the fallback when ExifTool is unavailable and
cannot decode maker notes, so brand-specific fields (shutter count, AF point) stay unknown.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from ..domain import FrameMeta
from .errors import MetadataError
from .metadata import normalise

_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

# (IFD, tag) -> ExifTool-style name used by ``normalise``.
_IFD0 = {
    0x010F: "Make",
    0x0110: "Model",
    0x0131: "Software",
    0x0100: "ImageWidth",
    0x0101: "ImageHeight",
    0xC62F: "CameraSerialNumber",
    0xC62A: "_BaselineExposure",
}
_EXIF = {
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8827: "ISO",
    0x9003: "DateTimeOriginal",
    0x9204: "ExposureCompensation",
    0x9207: "MeteringMode",
    0x920A: "FocalLength",
    0x9291: "SubSecTimeOriginal",
    0xA431: "SerialNumber",
    0xA434: "LensModel",
    0x927C: "MakerNote",
}


class _Tiff:
    def __init__(self, data: bytes, base: int = 0) -> None:
        self.data = data
        self.base = base
        order = data[base : base + 2]
        if order == b"II":
            self.e = "<"
        elif order == b"MM":
            self.e = ">"
        else:
            raise MetadataError("not a TIFF structure")
        if struct.unpack(self.e + "H", data[base + 2 : base + 4])[0] != 42:
            raise MetadataError("bad TIFF magic")

    def u(self, fmt: str, off: int) -> Any:
        return struct.unpack(
            self.e + fmt, self.data[self.base + off : self.base + off + struct.calcsize(fmt)]
        )[0]

    def ifd(self, offset: int) -> dict[int, Any]:
        out: dict[int, Any] = {}
        try:
            count = self.u("H", offset)
        except struct.error:
            return out
        for i in range(min(count, 512)):
            at = offset + 2 + 12 * i
            try:
                tag, typ, n = struct.unpack(
                    self.e + "HHI", self.data[self.base + at : self.base + at + 8]
                )
            except struct.error:
                break
            size = _TYPE_SIZE.get(typ)
            if size is None:
                continue
            total = size * n
            val_off = at + 8 if total <= 4 else self.u("I", at + 8)
            raw = self.data[self.base + val_off : self.base + val_off + total]
            if len(raw) < total:
                continue
            out[tag] = self._decode(typ, n, raw)
        return out

    def _decode(self, typ: int, n: int, raw: bytes) -> Any:
        e = self.e
        if typ == 2:
            return raw.split(b"\x00")[0].decode("ascii", "replace")
        if typ == 3:
            vals = struct.unpack(f"{e}{n}H", raw)
        elif typ == 4:
            vals = struct.unpack(f"{e}{n}I", raw)
        elif typ == 5:
            nums = struct.unpack(f"{e}{2 * n}I", raw)
            vals = tuple(a / b if b else 0.0 for a, b in zip(nums[::2], nums[1::2], strict=True))
        elif typ == 10:
            nums = struct.unpack(f"{e}{2 * n}i", raw)
            vals = tuple(a / b if b else 0.0 for a, b in zip(nums[::2], nums[1::2], strict=True))
        elif typ == 7 or typ == 1:
            return raw
        else:
            return None
        return vals[0] if n == 1 else vals


def _tiff_from(path: Path) -> _Tiff:
    data = path.read_bytes()
    if data[:2] in (b"II", b"MM"):
        return _Tiff(data)
    if data[:2] == b"\xff\xd8":  # JPEG: find the Exif APP1 segment
        pos = 2
        while pos + 4 <= len(data) and data[pos] == 0xFF:
            marker = data[pos + 1]
            length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
            if marker == 0xE1 and data[pos + 4 : pos + 10] == b"Exif\x00\x00":
                return _Tiff(data, pos + 10)
            pos += 2 + length
    raise MetadataError(f"no TIFF or Exif data in {path.name}")


class TiffMetadataReader:
    name = "in-house"

    def read(self, path: Path) -> FrameMeta:
        tiff = _tiff_from(path)
        first = tiff.u("I", 4)
        ifd0 = tiff.ifd(first)
        raw: dict[str, Any] = {}
        for tag, name in _IFD0.items():
            if tag in ifd0:
                raw[name] = ifd0[tag]
        exif_ptr = ifd0.get(0x8769)
        if isinstance(exif_ptr, int):
            exif = tiff.ifd(exif_ptr)
            for tag, name in _EXIF.items():
                if tag in exif:
                    raw[name] = exif[tag]
            if "MakerNote" in raw:
                raw["MakerNote"] = True
        elif 0x8769 in ifd0:
            pass
        # DNG stores the serial in IFD0; plain EXIF in the Exif IFD.
        # Raw values: ExposureCompensation is already a signed ratio.
        if "DateTimeOriginal" in raw and "SubSecTimeOriginal" in raw:
            raw["SubSecTimeOriginal"] = str(raw["SubSecTimeOriginal"]).strip()
        return normalise(raw)

    def close(self) -> None:
        return None
