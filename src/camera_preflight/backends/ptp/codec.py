"""PTP wire format: containers, strings, arrays and datasets (ISO 15740).

[Sourced] container layout and operation codes follow the public PTP standard. Nothing here
has been run against a real camera yet (docs/hardware-log/).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# Container types
CMD, DATA, RESP, EVENT = 1, 2, 3, 4

# Operations
OP_GET_DEVICE_INFO = 0x1001
OP_OPEN_SESSION = 0x1002
OP_CLOSE_SESSION = 0x1003
OP_GET_STORAGE_IDS = 0x1004
OP_GET_STORAGE_INFO = 0x1005
OP_GET_OBJECT_HANDLES = 0x1007
OP_GET_OBJECT_INFO = 0x1008
OP_GET_OBJECT = 0x1009
OP_INITIATE_CAPTURE = 0x100E
OP_GET_PROP_VALUE = 0x1015
OP_SET_PROP_VALUE = 0x1016

# Responses
RC_OK = 0x2001
RC_GENERAL_ERROR = 0x2002
RC_DEVICE_BUSY = 0x2019

# Standard device properties
PROP_BATTERY = 0x5001
PROP_FNUMBER = 0x5007
PROP_FOCUS_MODE = 0x500A
PROP_METERING = 0x500B
PROP_EXPOSURE_TIME = 0x500D
PROP_ISO = 0x500F
PROP_EXPOSURE_BIAS = 0x5010

HEADER = struct.Struct("<IHHI")


@dataclass
class Container:
    type: int
    code: int
    transaction: int
    params: tuple[int, ...] = ()
    payload: bytes = b""

    def pack(self) -> bytes:
        body = b"".join(struct.pack("<I", p) for p in self.params) + self.payload
        return HEADER.pack(HEADER.size + len(body), self.type, self.code, self.transaction) + body

    @classmethod
    def unpack(cls, data: bytes) -> Container:
        if len(data) < HEADER.size:
            raise ValueError("short PTP container")
        length, typ, code, tid = HEADER.unpack_from(data)
        body = data[HEADER.size : length]
        if typ in (CMD, RESP, EVENT):
            n = min(len(body) // 4, 5)
            params = struct.unpack(f"<{n}I", body[: n * 4])
            return cls(typ, code, tid, params, body[n * 4 :])
        return cls(typ, code, tid, (), body)


def pack_string(text: str) -> bytes:
    if not text:
        return b"\x00"
    units = text.encode("utf-16-le") + b"\x00\x00"
    return bytes([len(units) // 2]) + units


def read_string(data: bytes, off: int) -> tuple[str, int]:
    n = data[off]
    off += 1
    if n == 0:
        return "", off
    raw = data[off : off + 2 * n]
    return raw.decode("utf-16-le").rstrip("\x00"), off + 2 * n


def read_u16_array(data: bytes, off: int) -> tuple[list[int], int]:
    (n,) = struct.unpack_from("<I", data, off)
    off += 4
    vals = list(struct.unpack_from(f"<{n}H", data, off))
    return vals, off + 2 * n


@dataclass
class DeviceInfoData:
    standard_version: int = 0
    vendor_extension_id: int = 0
    vendor_extension: str = ""
    operations: list[int] = field(default_factory=list)
    events: list[int] = field(default_factory=list)
    properties: list[int] = field(default_factory=list)
    manufacturer: str = ""
    model: str = ""
    device_version: str = ""
    serial: str = ""


def parse_device_info(data: bytes) -> DeviceInfoData:
    """DeviceInfo dataset: version, extension, functional mode, arrays, then four strings."""
    info = DeviceInfoData()
    info.standard_version, info.vendor_extension_id, _ext_version = struct.unpack_from(
        "<HIH", data, 0
    )
    info.vendor_extension, off = read_string(data, 8)
    off += 2  # functional mode
    info.operations, off = read_u16_array(data, off)
    info.events, off = read_u16_array(data, off)
    info.properties, off = read_u16_array(data, off)
    _capture_formats, off = read_u16_array(data, off)
    _image_formats, off = read_u16_array(data, off)
    info.manufacturer, off = read_string(data, off)
    info.model, off = read_string(data, off)
    info.device_version, off = read_string(data, off)
    info.serial, off = read_string(data, off)
    return info


def build_device_info(info: DeviceInfoData) -> bytes:
    """Inverse of ``parse_device_info``; the test camera uses it."""

    def arr(vals: list[int]) -> bytes:
        return struct.pack("<I", len(vals)) + b"".join(struct.pack("<H", v) for v in vals)

    return (
        struct.pack("<HIH", info.standard_version, info.vendor_extension_id, 0)
        + pack_string(info.vendor_extension)
        + struct.pack("<H", 0)
        + arr(info.operations)
        + arr(info.events)
        + arr(info.properties)
        + arr([])
        + arr([])
        + pack_string(info.manufacturer)
        + pack_string(info.model)
        + pack_string(info.device_version)
        + pack_string(info.serial)
    )
