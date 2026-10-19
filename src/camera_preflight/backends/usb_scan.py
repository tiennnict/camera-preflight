"""Which camera brands are on USB, without opening anything (FR-CON-01).

On Windows the Plug and Play list is read through SetupAPI: no driver, no SDK, no camera session.
Detection then tries only the SDKs of brands that are actually plugged in, so a missing camera is
reported at once instead of after every SDK has timed out.
"""

from __future__ import annotations

import ctypes
import os
import re
from typing import Any

# [Sourced] USB-IF vendor IDs (usb.ids): Canon 04A9, Nikon 04B0, Sony 054C.
VENDORS = {0x04A9: "canon", 0x04B0: "nikon", 0x054C: "sony"}

_VID = re.compile(r"VID_([0-9A-F]{4})", re.IGNORECASE)
_DIGCF_PRESENT, _DIGCF_ALLCLASSES = 0x2, 0x4
_INVALID_HANDLE = ctypes.c_void_p(-1).value


def brands_in(instance_ids: list[str]) -> frozenset[str]:
    """Brands named by USB device instance ids such as ``USB\\VID_04B0&PID_0444\\5``."""
    out: set[str] = set()
    for text in instance_ids:
        m = _VID.search(text)
        if m:
            brand = VENDORS.get(int(m.group(1), 16))
            if brand:
                out.add(brand)
    return frozenset(out)


class _DevInfoData(ctypes.Structure):  # SP_DEVINFO_DATA
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("ClassGuid", ctypes.c_ubyte * 16),
        ("DevInst", ctypes.c_uint32),
        ("Reserved", ctypes.c_size_t),
    ]


def _instance_ids() -> list[str]:
    setupapi: Any = ctypes.WinDLL("setupapi")  # type: ignore[attr-defined]
    get_devs = setupapi.SetupDiGetClassDevsW
    get_devs.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    get_devs.restype = ctypes.c_void_p
    enum_info = setupapi.SetupDiEnumDeviceInfo
    enum_info.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_DevInfoData)]
    enum_info.restype = ctypes.c_int
    get_id = setupapi.SetupDiGetDeviceInstanceIdW
    get_id.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_DevInfoData),
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    get_id.restype = ctypes.c_int
    destroy = setupapi.SetupDiDestroyDeviceInfoList
    destroy.argtypes = [ctypes.c_void_p]
    handle = get_devs(None, "USB", None, _DIGCF_PRESENT | _DIGCF_ALLCLASSES)
    if not handle or handle == _INVALID_HANDLE:
        raise OSError("SetupDiGetClassDevsW failed")
    ids: list[str] = []
    try:
        index = 0
        while True:
            data = _DevInfoData()
            data.cbSize = ctypes.sizeof(_DevInfoData)
            if not enum_info(handle, index, ctypes.byref(data)):
                break
            buf = ctypes.create_unicode_buffer(512)
            if get_id(handle, ctypes.byref(data), buf, len(buf), None):
                ids.append(buf.value)
            index += 1
    finally:
        destroy(handle)
    return ids


def present_brands() -> frozenset[str] | None:
    """Camera brands on USB now, or None when this cannot be known (not Windows, or an error)."""
    if os.name != "nt":
        return None
    try:
        return brands_in(_instance_ids())
    except (OSError, AttributeError):
        return None
