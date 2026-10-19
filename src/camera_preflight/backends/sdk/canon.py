"""Canon adapter on EDSDK (WP-46, FR-CON-03, D-31).

The binding follows the public API of EDSDK 2.13 (headers, ``EDSDK_API.pdf`` and the Visual C++
``CameraControl`` sample from that release), which the maintainer keeps in ``sdk/canon``. No SDK
file is part of the repository. The library loads only inside the backend host process.

Labels. Function names, argument lists, structures, property ids, command ids, event ids and error
codes are ``[Sourced]`` from that release and were checked against two independent open-source
wrappers (``fmargall/pyedsdk``, ``Jiloc/edsdk-python``); nothing is copied from them. Aperture,
shutter and ISO code tables are ``[Sourced]`` from the API reference only where both it and
``pyedsdk`` agree. Everything the sources do not settle is ``[Unverified]`` until a hardware log
exists (V-23): how long a body needs after a property write, the retry delays for "device busy",
whether a body offers a value list in a given mode, live view start-up time.

Not covered by this SDK, on purpose. The shutter count is not an EDSDK property (no such id in the
2.13 headers); the PTP backend reads it (``backends/ptp``). Shutter mode (mechanical or
electronic), AF point selection, focus drive and burst are not bound. The AF mode property is read
only in the API reference, so focus mode cannot be set.

Threading [Sourced: API reference, wrapper examples, canon-sdk-java README]. Events reach the
thread that initialised the library: through the Windows message loop in a GUI program, through
``EdsGetEvent`` in a console program (``EdsGetEvent`` from another thread does nothing). So every
call and the event pump stay on one thread. The host process serves requests on one thread, which
satisfies this; waits in this module pump events instead of sleeping blind. Events are only
delivered while a request is being served, because the host blocks on its input in between.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ...domain import DeviceInfo
from ..protocol import (
    Capabilities,
    CaptureOutcome,
    CaptureSettings,
    CommandFailed,
    Disconnected,
    NotSupported,
    RemoteFile,
)
from .loader import SdkAdapter, SdkLocation, SdkUnavailable, add_dll_directories

# ---- property ids (kEdsPropID_*) [Sourced] --------------------------------------------------------
P_PRODUCT_NAME = 0x02
P_BODY_ID = 0x15  # serial number as text
P_FIRMWARE = 0x07
P_BATTERY = 0x08  # 0 to 100 percent, 0xFFFFFFFF when on AC power
P_SAVE_TO = 0x0B
P_ISO = 0x402
P_METERING = 0x403
P_AF_MODE = 0x404  # read only
P_AV = 0x405
P_TV = 0x406
P_COMP = 0x407
P_LENS_NAME = 0x40D
P_EVF_OUTPUT = 0x500
P_EVF_MODE = 0x501

# ---- commands, events, enums [Sourced] ------------------------------------------------------------
CMD_TAKE_PICTURE = 0x0
CMD_EXTEND_SHUTDOWN_TIMER = 0x1
STATUS_UI_LOCK, STATUS_UI_UNLOCK = 0x0, 0x1
EVENT_OBJECT_ALL = 0x200
EVENT_REQUEST_TRANSFER = 0x208  # kEdsObjectEvent_DirItemRequestTransfer
EVENT_STATE_ALL = 0x300
STATE_SHUTDOWN = 0x301
STATE_WILL_SOON_SHUTDOWN = 0x303
SAVE_TO_HOST = 2
EVF_MODE_ON = 1
EVF_OUTPUT_PC = 2
FILE_CREATE_ALWAYS = 1  # kEdsFileCreateDisposition_CreateAlways
ACCESS_READ_WRITE = 2  # kEdsAccess_ReadWrite
HOST_CAPACITY = (0x7FFFFFFF, 0x1000, 1)  # free clusters, bytes per sector, reset: as in the sample
ACCESS_READ = 0  # EdsPropertyDesc.access: 0 read, 1 write, 2 read and write
INVALID_VALUE = 0xFFFFFFFF

# ---- error codes (EDS_ERR_*) [Sourced] ------------------------------------------------------------
ERR_OK = 0x0
ERR_DEVICE_NOT_FOUND = 0x80
ERR_DEVICE_BUSY = 0x81
ERR_COMM_DISCONNECTED = 0xC1
ERR_SESSION_NOT_OPEN = 0x2003
ERR_TAKE_PICTURE_AF_NG = 0x8D01
ERR_OBJECT_NOTREADY = 0xA102
_LOST = (ERR_DEVICE_NOT_FOUND, ERR_COMM_DISCONNECTED, ERR_SESSION_NOT_OPEN)
_NAMES = {
    ERR_DEVICE_NOT_FOUND: "device not found",
    ERR_DEVICE_BUSY: "device busy",
    ERR_COMM_DISCONNECTED: "disconnected",
    ERR_SESSION_NOT_OPEN: "session not open",
    ERR_TAKE_PICTURE_AF_NG: "autofocus failed",
    ERR_OBJECT_NOTREADY: "object not ready",
}

# [Sourced: canon-sdk-java README] leave about 500 ms between re-sent commands, some bodies turn
# unstable otherwise. [Unverified] on our bodies.
BUSY_RETRY_S = (0.5, 0.5, 0.5)
SETTLE_S = 2.0  # time for a written property to read back as set [Guess]
DOWNLOAD_QUIET_S = 1.0  # no new file for this long after the last one: the capture is done [Guess]
LIVE_VIEW_WAIT_S = 1.5  # time for a live view frame to become ready [Guess]
FIND_WAIT_S = 10.0  # time for the SDK to list a connected camera after it starts [Guess]

# ---- value tables: code to nominal value [Sourced: API reference, agreeing with pyedsdk] ------------
# Codes marked "(1/3)" in the reference are the values a body reports when its exposure step is 1/3.
_AV = {
    0x08: 1.0, 0x0B: 1.1, 0x0C: 1.2, 0x0D: 1.2, 0x10: 1.4, 0x13: 1.6, 0x14: 1.8, 0x15: 1.8,
    0x18: 2.0, 0x1B: 2.2, 0x1C: 2.5, 0x1D: 2.5, 0x20: 2.8, 0x23: 3.2, 0x24: 3.5, 0x25: 3.5,
    0x28: 4.0, 0x2B: 4.5, 0x2D: 5.0, 0x30: 5.6, 0x33: 6.3, 0x34: 6.7, 0x35: 7.1, 0x38: 8.0,
    0x3B: 9.0, 0x3C: 9.5, 0x3D: 10.0, 0x40: 11.0, 0x43: 13.0, 0x44: 13.0, 0x45: 14.0,
    0x48: 16.0, 0x4B: 18.0, 0x4C: 19.0, 0x4D: 20.0, 0x50: 22.0, 0x53: 25.0, 0x54: 27.0,
    0x55: 29.0, 0x58: 32.0, 0x5B: 36.0, 0x5C: 38.0, 0x5D: 40.0, 0x60: 45.0, 0x63: 51.0,
    0x64: 54.0, 0x65: 57.0, 0x68: 64.0, 0x6B: 72.0, 0x6C: 76.0, 0x6D: 80.0, 0x70: 91.0,
}  # fmt: skip
_TV = {
    0x10: "30", 0x13: "25", 0x14: "20", 0x15: "20", 0x18: "15", 0x1B: "13", 0x1C: "10",
    0x1D: "10", 0x20: "8", 0x23: "6", 0x24: "6", 0x25: "5", 0x28: "4", 0x2B: "3.2", 0x2C: "3",
    0x2D: "2.5", 0x30: "2", 0x33: "1.6", 0x34: "1.5", 0x35: "1.3", 0x38: "1", 0x3B: "0.8",
    0x3C: "0.7", 0x3D: "0.6", 0x40: "0.5", 0x43: "0.4", 0x44: "0.3", 0x45: "0.3", 0x48: "1/4",
    0x4B: "1/5", 0x4C: "1/6", 0x4D: "1/6", 0x50: "1/8", 0x53: "1/10", 0x54: "1/10",
    0x55: "1/13", 0x58: "1/15", 0x5B: "1/20", 0x5C: "1/20", 0x5D: "1/25", 0x60: "1/30",
    0x63: "1/40", 0x64: "1/45", 0x65: "1/50", 0x68: "1/60", 0x6B: "1/80", 0x6C: "1/90",
    0x6D: "1/100", 0x70: "1/125", 0x73: "1/160", 0x74: "1/180", 0x75: "1/200", 0x78: "1/250",
    0x7B: "1/320", 0x7C: "1/350", 0x7D: "1/400", 0x80: "1/500", 0x83: "1/640", 0x84: "1/750",
    0x85: "1/800", 0x88: "1/1000", 0x8B: "1/1250", 0x8C: "1/1500", 0x8D: "1/1600",
    0x90: "1/2000", 0x93: "1/2500", 0x94: "1/3000", 0x95: "1/3200", 0x98: "1/4000",
    0x9B: "1/5000", 0x9C: "1/6000", 0x9D: "1/6400", 0xA0: "1/8000",
}  # fmt: skip
_BULB = 0x0C
_ISO = {
    0x40: 50, 0x48: 100, 0x4B: 125, 0x4D: 160, 0x50: 200, 0x53: 250, 0x55: 320, 0x58: 400,
    0x5B: 500, 0x5D: 640, 0x60: 800, 0x63: 1000, 0x65: 1250, 0x68: 1600, 0x6B: 2000,
    0x6D: 2500, 0x70: 3200, 0x73: 4000, 0x75: 5000, 0x78: 6400, 0x7B: 8000, 0x7D: 10000,
    0x80: 12800, 0x88: 25600, 0x90: 51200, 0x98: 102400,
}  # fmt: skip

# Metering [Sourced]: 1 spot, 3 evaluative, 4 partial, 5 centre-weighted average.
_METERING = {"evaluative": (3,), "centre_weighted": (5,), "spot": (1,)}


# ---- value parsing (pure, tested without the SDK) --------------------------------------------------
def decode_av(code: int) -> float | None:
    return _AV.get(code)


def decode_tv(code: int) -> float | None:
    """Exposure time in seconds; Bulb and unknown codes give None."""
    text = _TV.get(code)
    if text is None:
        return None
    num, _, den = text.partition("/")
    return float(num) / float(den) if den else float(num)


def decode_iso(code: int) -> float | None:
    """ISO number; 0 is Auto, which has no number."""
    value = _ISO.get(code)
    return float(value) if value else None


def decode_comp(code: int) -> float | None:
    """Exposure compensation in EV. The code is a signed byte in 1/8 EV steps whose third and
    half stops are written as 3/8, 4/8 and 5/8 (+1/3, +1/2, +2/3). [Sourced: API reference table]"""
    if code == INVALID_VALUE or not 0 <= code <= 0xFF:
        return None
    signed = code - 0x100 if code & 0x80 else code
    whole, rest = divmod(abs(signed), 8)
    if rest not in (0, 3, 4, 5):
        return signed / 8
    ev = whole + {0: 0.0, 3: 1 / 3, 4: 0.5, 5: 2 / 3}[rest]
    return -ev if signed < 0 else ev


def pick_value(
    offered: list[int], decode: Callable[[int], float | None], target: float, rel_tol: float
) -> int | None:
    """The offered code whose decoded number is closest to ``target`` within ``rel_tol``."""
    best: tuple[float, int] | None = None
    for raw in offered:
        x = decode(raw)
        if x is None or x <= 0:
            continue
        err = abs(x - target) / target
        if best is None or err < best[0]:
            best = (err, raw)
    return best[1] if best and best[0] <= rel_tol else None


def pick_comp(offered: list[int], ev: float) -> int | None:
    best: tuple[float, int] | None = None
    for raw in offered:
        x = decode_comp(raw)
        if x is not None and (best is None or abs(x - ev) < best[0]):
            best = (abs(x - ev), raw)
    return best[1] if best and best[0] < 0.1 else None


def describe_error(code: int) -> str:
    name = _NAMES.get(code)
    return f"0x{code:x} ({name})" if name else f"0x{code:x}"


# ---- layer interface -----------------------------------------------------------------------------------
@dataclass
class CameraEntry:
    index: int
    name: str
    port: str = ""


@dataclass
class PropDesc:
    values: list[int] = field(default_factory=list)  # values the body accepts right now
    access: int = 2

    @property
    def settable(self) -> bool:
        return bool(self.values) and self.access != ACCESS_READ


class Layer(Protocol):
    on_download: Callable[[str], None] | None
    on_state: Callable[[int, int], None] | None

    def init(self) -> None: ...
    def release(self) -> None: ...
    def enumerate(self) -> list[CameraEntry]: ...
    def connect(self, index: int) -> int: ...
    def prepare_host_transfer(self, folder: Path) -> int: ...
    def disconnect(self) -> None: ...
    def get_u32(self, prop: int) -> int | None: ...
    def get_text(self, prop: int) -> str | None: ...
    def get_desc(self, prop: int) -> PropDesc | None: ...
    def set_u32(self, prop: int, value: int) -> int: ...
    def send_command(self, command: int, param: int) -> int: ...
    def pump(self) -> None: ...
    def live_view_jpeg(self) -> bytes | None: ...


# ---- ctypes binding ----------------------------------------------------------------------------------
class _DeviceInfo(ctypes.Structure):  # EdsDeviceInfo
    _fields_ = [
        ("portName", ctypes.c_char * 256),
        ("description", ctypes.c_char * 256),
        ("subType", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class _DirItemInfo(ctypes.Structure):  # EdsDirectoryItemInfo
    _fields_ = [
        ("size", ctypes.c_uint64),
        ("isFolder", ctypes.c_int32),
        ("groupId", ctypes.c_uint32),
        ("option", ctypes.c_uint32),
        ("fileName", ctypes.c_char * 256),
        ("format", ctypes.c_uint32),
        ("dateTime", ctypes.c_uint32),
    ]


class _PropertyDesc(ctypes.Structure):  # EdsPropertyDesc
    _fields_ = [
        ("form", ctypes.c_int32),
        ("access", ctypes.c_int32),
        ("numElements", ctypes.c_int32),
        ("values", ctypes.c_int32 * 128),
    ]


class _Capacity(ctypes.Structure):  # EdsCapacity, passed by value
    _fields_ = [
        ("freeClusters", ctypes.c_int32),
        ("bytesPerSector", ctypes.c_int32),
        ("reset", ctypes.c_int32),
    ]


class _Msg(ctypes.Structure):  # Win32 MSG, for the message pump
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_uint32),
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


# EDSCALLBACK is __stdcall; WINFUNCTYPE exists on Windows only.
_CALLBACK: Any = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_VOID = ctypes.c_void_p
_OBJECT_HANDLER = _CALLBACK(ctypes.c_uint32, ctypes.c_uint32, _VOID, _VOID)
_STATE_HANDLER = _CALLBACK(ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, _VOID)
_COINIT_APARTMENTTHREADED = 0x2
_PM_REMOVE = 0x1


def _windll(name: str) -> Any:
    root = getattr(ctypes, "windll", None)
    return getattr(root, name, None) if root is not None else None


class EdsLayer:
    """Real layer: ``EDSDK.dll`` through ctypes. Everything runs on the calling thread."""

    def __init__(self, library: Path) -> None:
        self.on_download: Callable[[str], None] | None = None
        self.on_state: Callable[[int, int], None] | None = None
        self._path = library
        self._dll_dirs = add_dll_directories(library.parent)
        loader: Any = getattr(ctypes, "WinDLL", ctypes.CDLL)
        try:
            self._dll = loader(str(library))
        except OSError as exc:
            raise SdkUnavailable(f"cannot load {library.name}: {exc}") from exc
        self._refs: list[int] = []  # camera references from the last enumeration
        self._camera = ctypes.c_void_p()
        self._pending: list[int] = []  # directory items waiting to be downloaded
        self._folder: Path | None = None
        self._sdk_up = False
        self._com_up = False
        self._evf_on = False
        self._evf_stream = ctypes.c_void_p()
        self._evf_image = ctypes.c_void_p()
        self.last_download_error = 0
        # The callbacks must stay referenced for as long as the camera may call them.
        self._object_cb = _OBJECT_HANDLER(self._object_event)
        self._state_cb = _STATE_HANDLER(self._state_event)
        self._bind()

    def _fn(self, name: str, argtypes: list[Any], restype: Any = ctypes.c_uint32) -> Any:
        try:
            fn = getattr(self._dll, name)
        except AttributeError as exc:
            raise SdkUnavailable(f"{self._path.name} has no export {name}") from exc
        fn.argtypes = argtypes
        fn.restype = restype
        return fn

    def _bind(self) -> None:
        u32, i32, u64, vp = ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint64, ctypes.c_void_p
        pp = ctypes.POINTER
        self._init = self._fn("EdsInitializeSDK", [])
        self._term = self._fn("EdsTerminateSDK", [])
        self._release_ref = self._fn("EdsRelease", [vp])
        self._camera_list = self._fn("EdsGetCameraList", [pp(vp)])
        self._child_count = self._fn("EdsGetChildCount", [vp, pp(u32)])
        self._child_at = self._fn("EdsGetChildAtIndex", [vp, i32, pp(vp)])
        self._device_info = self._fn("EdsGetDeviceInfo", [vp, pp(_DeviceInfo)])
        self._open = self._fn("EdsOpenSession", [vp])
        self._close = self._fn("EdsCloseSession", [vp])
        self._command = self._fn("EdsSendCommand", [vp, u32, i32])
        self._status = self._fn("EdsSendStatusCommand", [vp, u32, i32])
        self._prop_size = self._fn("EdsGetPropertySize", [vp, u32, i32, pp(u32), pp(u32)])
        self._prop_get = self._fn("EdsGetPropertyData", [vp, u32, i32, u32, vp])
        self._prop_set = self._fn("EdsSetPropertyData", [vp, u32, i32, u32, vp])
        self._prop_desc = self._fn("EdsGetPropertyDesc", [vp, u32, pp(_PropertyDesc)])
        self._set_object_handler = self._fn(
            "EdsSetObjectEventHandler", [vp, u32, _OBJECT_HANDLER, vp]
        )
        self._set_state_handler = self._fn(
            "EdsSetCameraStateEventHandler", [vp, u32, _STATE_HANDLER, vp]
        )
        self._set_capacity = self._fn("EdsSetCapacity", [vp, _Capacity])
        self._item_info = self._fn("EdsGetDirectoryItemInfo", [vp, pp(_DirItemInfo)])
        self._download = self._fn("EdsDownload", [vp, u64, vp])
        self._download_cancel = self._fn("EdsDownloadCancel", [vp])
        self._download_done = self._fn("EdsDownloadComplete", [vp])
        self._file_stream = self._fn("EdsCreateFileStream", [ctypes.c_char_p, u32, u32, pp(vp)])
        self._mem_stream = self._fn("EdsCreateMemoryStream", [u64, pp(vp)])
        self._pointer = self._fn("EdsGetPointer", [vp, pp(vp)])
        self._length = self._fn("EdsGetLength", [vp, pp(u64)])
        self._evf_ref = self._fn("EdsCreateEvfImageRef", [vp, pp(vp)])
        self._evf_download = self._fn("EdsDownloadEvfImage", [vp, vp])
        self._get_event = self._fn("EdsGetEvent", [])

    # -- lifecycle ----------------------------------------------------------------------------------
    def init(self) -> None:
        ole32 = _windll("ole32")
        if (
            ole32 is not None
        ):  # EDSDK uses the COM single-threaded apartment model [Sourced: example]
            self._com_up = ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED) in (0, 1)
        err = self._init()
        if err != ERR_OK:
            raise SdkUnavailable(f"EdsInitializeSDK failed ({describe_error(err)})")
        self._sdk_up = True

    def release(self) -> None:
        self._drop_refs()
        if self._sdk_up:
            with contextlib.suppress(Exception):
                self._term()
            self._sdk_up = False
        ole32 = _windll("ole32")
        if self._com_up and ole32 is not None:
            with contextlib.suppress(Exception):
                ole32.CoUninitialize()
            self._com_up = False
        for d in self._dll_dirs:
            with contextlib.suppress(Exception):
                d.close()
        self._dll_dirs = []

    def _drop_refs(self) -> None:
        for ref in self._refs:
            self._release_ref(ctypes.c_void_p(ref))
        self._refs = []

    # -- connection -----------------------------------------------------------------------------------
    def enumerate(self) -> list[CameraEntry]:
        self._drop_refs()
        listing = ctypes.c_void_p()
        if self._camera_list(ctypes.byref(listing)) != ERR_OK:
            return []
        entries: list[CameraEntry] = []
        try:
            count = ctypes.c_uint32()
            if self._child_count(listing, ctypes.byref(count)) != ERR_OK:
                return []
            for i in range(count.value):
                ref = ctypes.c_void_p()
                if self._child_at(listing, i, ctypes.byref(ref)) != ERR_OK or not ref.value:
                    continue
                info = _DeviceInfo()
                if self._device_info(ref, ctypes.byref(info)) != ERR_OK:
                    self._release_ref(ref)
                    continue
                self._refs.append(ref.value)
                name = info.description.decode("ascii", "replace")
                entries.append(CameraEntry(len(self._refs) - 1, name, info.portName.decode()))
        finally:
            self._release_ref(listing)
        return entries

    def connect(self, index: int) -> int:
        """Keep camera ``index``, set the handlers, then open the session (order as in the
        sample: handlers first)."""
        keep = self._refs.pop(index)
        self._drop_refs()
        self._camera = ctypes.c_void_p(keep)
        self._pending = []
        err = self._set_object_handler(self._camera, EVENT_OBJECT_ALL, self._object_cb, None)
        if err == ERR_OK:
            err = self._set_state_handler(self._camera, EVENT_STATE_ALL, self._state_cb, None)
        if err == ERR_OK:
            err = self._open(self._camera)
        return int(err)

    def prepare_host_transfer(self, folder: Path) -> int:
        """Send shots to this PC: SaveTo host, then tell the body there is room (the sample locks
        the body UI around the capacity call). Files are written into ``folder``."""
        self._folder = folder
        err = self.set_u32(P_SAVE_TO, SAVE_TO_HOST)
        if err != ERR_OK:
            return err
        locked = self._status(self._camera, STATUS_UI_LOCK, 0) == ERR_OK
        try:
            free, sector, reset = HOST_CAPACITY
            return int(self._set_capacity(self._camera, _Capacity(free, sector, reset)))
        finally:
            if locked:
                self._status(self._camera, STATUS_UI_UNLOCK, 0)

    def disconnect(self) -> None:
        self._stop_live_view()
        if self._camera.value:
            with contextlib.suppress(Exception):
                self._close(self._camera)
            self._release_ref(self._camera)
            self._camera = ctypes.c_void_p()
        for ref in self._pending:
            self._release_ref(ctypes.c_void_p(ref))
        self._pending = []

    # -- properties -----------------------------------------------------------------------------------
    def get_u32(self, prop: int) -> int | None:
        value = ctypes.c_uint32()
        err = self._prop_get(self._camera, prop, 0, 4, ctypes.byref(value))
        return value.value if err == ERR_OK else None

    def get_text(self, prop: int) -> str | None:
        kind, size = ctypes.c_uint32(), ctypes.c_uint32()
        if self._prop_size(self._camera, prop, 0, ctypes.byref(kind), ctypes.byref(size)) != ERR_OK:
            return None
        buf = ctypes.create_string_buffer(max(size.value, 1))
        if self._prop_get(self._camera, prop, 0, size.value, buf) != ERR_OK:
            return None
        return buf.value.decode("ascii", "replace").strip() or None

    def get_desc(self, prop: int) -> PropDesc | None:
        desc = _PropertyDesc()
        if self._prop_desc(self._camera, prop, ctypes.byref(desc)) != ERR_OK:
            return None
        n = max(0, min(desc.numElements, 128))
        return PropDesc([desc.values[i] & 0xFFFFFFFF for i in range(n)], desc.access)

    def set_u32(self, prop: int, value: int) -> int:
        data = ctypes.c_uint32(value & 0xFFFFFFFF)
        return int(self._prop_set(self._camera, prop, 0, 4, ctypes.byref(data)))

    def send_command(self, command: int, param: int) -> int:
        return int(self._command(self._camera, command, param))

    # -- events ---------------------------------------------------------------------------------------
    def _object_event(self, event: int, ref: Any, _ctx: Any) -> int:
        # Only queue here: no SDK call inside a callback. Items nobody asked for are released.
        if event == EVENT_REQUEST_TRANSFER and ref:
            self._pending.append(int(ref))
        elif ref:
            self._release_ref(ctypes.c_void_p(ref))
        return ERR_OK

    def _state_event(self, event: int, data: int, _ctx: Any) -> int:
        if self.on_state is not None:
            self.on_state(int(event), int(data))
        return ERR_OK

    def pump(self) -> None:
        """Deliver waiting events, then fetch queued files. The host is a console program, for
        which the reference says to call EdsGetEvent regularly; the Windows message queue is
        drained as well because the wrappers' examples need it for the COM apartment."""
        self._get_event()
        user32 = _windll("user32")
        if user32 is not None:
            msg = _Msg()
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, _PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        while self._pending:
            self._fetch(ctypes.c_void_p(self._pending.pop(0)))

    def _fetch(self, item: ctypes.c_void_p) -> None:
        stream = ctypes.c_void_p()
        err = ERR_OK
        path: Path | None = None
        try:
            info = _DirItemInfo()
            err = self._item_info(item, ctypes.byref(info))
            if err != ERR_OK or self._folder is None:
                return
            name = Path(info.fileName.decode("ascii", "replace")).name
            path = self._folder / name
            err = self._file_stream(
                str(path).encode("mbcs" if os.name == "nt" else "utf-8"),
                FILE_CREATE_ALWAYS,
                ACCESS_READ_WRITE,
                ctypes.byref(stream),
            )
            if err == ERR_OK:
                err = self._download(item, info.size, stream)
            if err == ERR_OK:
                err = self._download_done(item)
            else:
                self._download_cancel(item)
        except UnicodeEncodeError:
            err = ERR_DEVICE_BUSY  # path not representable in the ANSI code page
        finally:
            if stream.value:
                self._release_ref(stream)
            self._release_ref(item)
        self.last_download_error = int(err)
        if err == ERR_OK and path is not None and self.on_download is not None:
            self.on_download(str(path))

    # -- live view ------------------------------------------------------------------------------------
    def live_view_jpeg(self) -> bytes | None:
        if not self._evf_on and not self._start_live_view():
            return None
        deadline = time.monotonic() + LIVE_VIEW_WAIT_S
        while True:
            err = self._evf_download(self._camera, self._evf_image)
            if err == ERR_OK:
                break
            if err != ERR_OBJECT_NOTREADY or time.monotonic() >= deadline:
                return None
            time.sleep(0.02)
        ptr, length = ctypes.c_void_p(), ctypes.c_uint64()
        if self._pointer(self._evf_stream, ctypes.byref(ptr)) != ERR_OK or not ptr.value:
            return None
        if self._length(self._evf_stream, ctypes.byref(length)) != ERR_OK:
            return None
        return ctypes.string_at(ptr.value, length.value)

    def _start_live_view(self) -> bool:
        if self.set_u32(P_EVF_MODE, EVF_MODE_ON) != ERR_OK:
            return False
        device = self.get_u32(P_EVF_OUTPUT) or 0
        if self.set_u32(P_EVF_OUTPUT, device | EVF_OUTPUT_PC) != ERR_OK:
            return False
        if self._mem_stream(0, ctypes.byref(self._evf_stream)) != ERR_OK:
            return False
        if self._evf_ref(self._evf_stream, ctypes.byref(self._evf_image)) != ERR_OK:
            self._release_ref(self._evf_stream)
            self._evf_stream = ctypes.c_void_p()
            return False
        self._evf_on = True
        return True

    def _stop_live_view(self) -> None:
        if not self._evf_on:
            return
        self._evf_on = False
        with contextlib.suppress(Exception):
            device = self.get_u32(P_EVF_OUTPUT) or 0
            self.set_u32(P_EVF_OUTPUT, device & ~EVF_OUTPUT_PC)
        for ref in (self._evf_image, self._evf_stream):
            if ref.value:
                self._release_ref(ref)
        self._evf_image = ctypes.c_void_p()
        self._evf_stream = ctypes.c_void_p()


# ---- adapter -----------------------------------------------------------------------------------------
class CanonAdapter(SdkAdapter):
    """Canon backend on EDSDK. Values are matched on what the body offers right now."""

    brand = "canon"

    def __init__(
        self, location: SdkLocation, layer_factory: Callable[[Path], Layer] | None = None
    ) -> None:
        super().__init__(location)
        self._factory = layer_factory or EdsLayer
        self._layer: Layer | None = None
        self._save_dir: Path | None = None
        self._downloads: list[str] = []
        self._last_download = 0.0
        self._lost = False
        self._extend_timer = False
        self._model = ""

    # ---- lifecycle ---------------------------------------------------------------------------
    def open(self) -> None:
        layer = self._factory(self.location.library)
        layer.on_download = self._on_download
        layer.on_state = self._on_state
        layer.init()
        try:
            cameras = self._find(layer)
            self._model = cameras[0].name
            err = layer.connect(cameras[0].index)
            if err != ERR_OK:
                raise CommandFailed(f"open session failed ({describe_error(err)})")
            self._save_dir = _plain_temp_dir()
            err = layer.prepare_host_transfer(self._save_dir)
            if err != ERR_OK:
                raise CommandFailed(f"host transfer setup failed ({describe_error(err)})")
        except Exception:
            with contextlib.suppress(Exception):
                layer.disconnect()
            layer.release()
            self._remove_save_dir()
            raise
        self._layer = layer

    @staticmethod
    def _find(layer: Layer) -> list[CameraEntry]:
        deadline = time.monotonic() + FIND_WAIT_S
        while True:
            cameras = layer.enumerate()
            if cameras:
                return cameras
            if time.monotonic() >= deadline:
                raise CommandFailed("no Canon camera found")
            layer.pump()
            time.sleep(0.25)

    def close(self) -> None:
        layer, self._layer = self._layer, None
        if layer is not None:
            with contextlib.suppress(Exception):
                layer.disconnect()
            layer.release()
        self._remove_save_dir()

    def _remove_save_dir(self) -> None:
        if self._save_dir is not None:
            shutil.rmtree(self._save_dir, ignore_errors=True)
            self._save_dir = None

    @property
    def layer(self) -> Layer:
        if self._layer is None:
            raise CommandFailed("session not open")
        if self._lost:
            raise Disconnected("the camera was switched off or unplugged")
        return self._layer

    # ---- layer events ---------------------------------------------------------------------------
    def _on_download(self, path: str) -> None:
        self._downloads.append(path)
        self._last_download = time.monotonic()

    def _on_state(self, event: int, _data: int) -> None:
        if event == STATE_SHUTDOWN:
            self._lost = True
        elif event == STATE_WILL_SOON_SHUTDOWN:
            self._extend_timer = True  # answered outside the callback, in _service

    def _service(self) -> None:
        """Pump events, then answer a "will shut down soon" warning by extending the timer."""
        layer = self.layer
        layer.pump()
        if self._extend_timer:
            self._extend_timer = False
            layer.send_command(CMD_EXTEND_SHUTDOWN_TIMER, 0)

    # ---- information -----------------------------------------------------------------------------
    def _can_set(self, prop: int) -> bool:
        desc = self.layer.get_desc(prop)
        return bool(desc and desc.settable)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            brand="Canon",
            backend=self.name,
            can_capture=True,
            can_set_exposure=self._can_set(P_TV),
            can_set_iso=self._can_set(P_ISO),
            can_set_aperture=self._can_set(P_AV),
            can_set_metering=self._can_set(P_METERING),
            can_set_comp=self._can_set(P_COMP),
            live_view=True,
            reads_battery=self.layer.get_u32(P_BATTERY) is not None,
            sdk_features=self.features(),
        )

    def features(self) -> tuple[str, ...]:
        # Only what is bound. Focus drive and newer bodies need a newer SDK and a hardware log.
        return ("live_view",)

    def device_info(self) -> DeviceInfo:
        layer = self.layer
        battery = layer.get_u32(P_BATTERY)
        percent = battery if battery is not None and battery <= 100 else None
        # The shutter count is not an EDSDK property; the PTP backend supplies it.
        return DeviceInfo(
            brand="Canon",
            model=layer.get_text(P_PRODUCT_NAME) or self._model or None,
            serial=layer.get_text(P_BODY_ID),
            firmware=layer.get_text(P_FIRMWARE),
            lens=layer.get_text(P_LENS_NAME),
            battery_percent=percent,
        )

    # ---- settings ---------------------------------------------------------------------------------
    _SNAPSHOT = (P_ISO, P_TV, P_AV, P_COMP, P_METERING)

    def snapshot_settings(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        for prop in self._SNAPSHOT:
            desc = self.layer.get_desc(prop)
            value = self.layer.get_u32(prop)
            if desc is not None and desc.settable and value is not None:
                snap[f"{prop:x}"] = value
        return snap

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        for key, value in snapshot.items():
            self._write(int(key, 16), int(value), key)

    def apply_settings(self, settings: CaptureSettings) -> None:
        if settings.af_point is not None:
            raise NotSupported("AF point selection is not bound for Canon (V-03)")
        if settings.burst > 1:
            raise NotSupported("burst over the SDK is not bound for Canon; use the guided step")
        if settings.shutter_mode is not None:
            raise NotSupported("EDSDK 2.13 has no shutter mode property")
        if settings.focus_mode is not None:
            raise NotSupported("the AF mode property is read only in EDSDK")
        if settings.iso is not None:
            self._set_number(P_ISO, decode_iso, float(settings.iso), 0.0, "ISO")
        if settings.exposure_s is not None:
            self._set_number(P_TV, decode_tv, settings.exposure_s, 0.03, "exposure")
        if settings.aperture is not None:
            self._set_number(P_AV, decode_av, settings.aperture, 0.03, "aperture")
        if settings.exposure_comp_ev is not None:
            desc = self._desc(P_COMP, "compensation")
            raw = pick_comp(desc.values, settings.exposure_comp_ev)
            if raw is None:
                raise CommandFailed(f"compensation {settings.exposure_comp_ev:g} EV not offered")
            self._write(P_COMP, raw, "compensation")
        if settings.metering is not None:
            wanted = _METERING.get(settings.metering, ())
            if not wanted:
                raise NotSupported("metering has no Canon value for this request")
            desc = self._desc(P_METERING, "metering")
            for raw in wanted:
                if raw in desc.values:
                    self._write(P_METERING, raw, "metering")
                    return
            raise CommandFailed("metering mode is not offered by the camera")

    def _desc(self, prop: int, label: str) -> PropDesc:
        desc = self.layer.get_desc(prop)
        if desc is None:
            raise NotSupported(f"{label} is not offered by this body")
        if not desc.settable:
            raise CommandFailed(f"{label} cannot be changed now (check the mode dial)")
        return desc

    def _set_number(
        self,
        prop: int,
        decode: Callable[[int], float | None],
        target: float,
        tol: float,
        label: str,
    ) -> None:
        desc = self._desc(prop, label)
        raw = pick_value(desc.values, decode, target, tol)
        if raw is None:
            raise CommandFailed(f"{label} {target:g} is not offered by the camera")
        self._write(prop, raw, label)

    def _write(self, prop: int, value: int, label: str) -> None:
        err = self.layer.set_u32(prop, value)
        if err != ERR_OK:
            raise CommandFailed(f"{label}: SDK error {describe_error(err)}")
        deadline = time.monotonic() + SETTLE_S
        while time.monotonic() < deadline:
            self._service()
            if self.layer.get_u32(prop) == value:
                return
            time.sleep(0.05)
        raise CommandFailed(f"{label}: the camera did not take the value")

    # ---- capture --------------------------------------------------------------------------------------
    def _send(self, command: int, param: int, label: str) -> int:
        """Send a command, retrying while the body says it is busy."""
        err = self.layer.send_command(command, param)
        for pause in BUSY_RETRY_S:
            if err != ERR_DEVICE_BUSY:
                break
            time.sleep(pause)
            self._service()
            err = self.layer.send_command(command, param)
        if err in _LOST:
            self._lost = True
            raise Disconnected(f"{label}: {describe_error(err)}")
        return err

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        if settings.burst > 1:
            raise NotSupported("burst over the SDK is not bound for Canon; use the guided step")
        self._service()
        self._downloads = []
        err = self._send(CMD_TAKE_PICTURE, 0, "take picture")
        if err == ERR_TAKE_PICTURE_AF_NG:
            return CaptureOutcome(ok=False, focus_failed=True)  # tier 1 signal (R-01)
        if err != ERR_OK:
            raise CommandFailed(f"take picture: SDK error {describe_error(err)}")
        deadline = time.monotonic() + timeout_s
        while True:
            self._service()
            now = time.monotonic()
            settled = bool(self._downloads) and now - self._last_download >= DOWNLOAD_QUIET_S
            if settled or now >= deadline:
                break
            time.sleep(0.02)
        files = [RemoteFile(ref=p, name=Path(p).name, size=_size(p)) for p in self._downloads]
        return CaptureOutcome(ok=bool(files), files=files, timed_out=not files)

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path:
        src = Path(ref.ref).resolve()
        root = self._save_dir.resolve() if self._save_dir else None
        if root is None or root not in src.parents or not src.is_file():
            raise CommandFailed("file is not one captured in this session")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        return dest

    # ---- live view -------------------------------------------------------------------------------------
    def live_view_frame(self) -> Any | None:
        self._service()
        jpeg = self.layer.live_view_jpeg()
        return _decode_jpeg(jpeg) if jpeg else None


def _plain_temp_dir() -> Path:
    """A scratch folder whose path survives the ANSI encoding EDSDK expects for file names."""
    path = Path(tempfile.mkdtemp(prefix="cp-canon-"))
    if str(path).isascii():
        return path
    shutil.rmtree(path, ignore_errors=True)
    return Path(tempfile.mkdtemp(prefix="cp-canon-", dir=os.environ.get("PROGRAMDATA", "C:\\")))


def _size(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def _decode_jpeg(data: bytes) -> Any:
    import io

    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(data)) as im:
        return np.asarray(im.convert("L"), dtype=np.uint8)
