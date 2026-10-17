"""Nikon adapter on the Remote SDK "Control Service Layer" (WP-61, FR-CON-03, D-31).

The binding follows the headers and sample app of the Remote SDK v2.1.0 that the maintainer
downloads into ``sdk/nikon`` (``Maid3.h``, ``Maid3d1.h``, ``SampleApp``). No SDK file is part of
the repository. The library is loaded only inside the backend host process.

Labels: structures, exported names, capability ids and result codes are ``[Sourced]`` from those
headers. How the camera behaves (value strings of the packed enums, what a silent mode really
does, when ``StartShooting`` returns) is ``[Unverified]`` until a hardware log exists (V-23).
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import re
import shutil
import tempfile
import threading
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
    NotSupported,
    RemoteFile,
)
from .loader import SdkAdapter, SdkLocation, SdkUnavailable

# ---- constants from Maid3.h and Maid3d1.h [Sourced] --------------------------------------------
_VENDOR = 0x8000
_DX2 = _VENDOR + 0x100
CAP_BATTERY = 0x30  # kNkMAIDCapability_BatteryLevel
CAP_SHUTTER_SPEED = _DX2 + 0x12
CAP_APERTURE = _DX2 + 0x13
CAP_EXPOSURE_COMP = _DX2 + 0x15
CAP_METERING = _DX2 + 0x16
CAP_SENSITIVITY = _DX2 + 0x17
CAP_FOCUS_MODE = _DX2 + 0x20
CAP_SILENT_MODE = _DX2 + 0x436

ARRAY_BOOLEAN, ARRAY_INTEGER, ARRAY_UNSIGNED, ARRAY_FLOAT = 0, 1, 2, 3
ARRAY_PACKED_STRING, ARRAY_STRING = 7, 8

DT_BOOLEAN_PTR, DT_INTEGER_PTR, DT_UNSIGNED_PTR, DT_FLOAT_PTR = 4, 5, 6, 7
DT_STRING_PTR, DT_RANGE_PTR, DT_ARRAY_PTR, DT_ENUM_PTR = 11, 14, 15, 16

GET_VALUE, GET_SUPPORTED_ARRAY = 0, 1  # eNkSDKGetSettingRequestType

SHOOT_SINGLE, SHOOT_CONTINUOUS = 1, 2  # eNkMAIDShootingType

EVENT_IMAGE_SAVED = 8  # eNkMAIDEvent
EVENT_DEVICE_INFO_CHANGED = 7

RESULT_OK = 0
RESULT_OUT_OF_FOCUS = 137
RESULT_DEVICE_BUSY = 152

_METERING = {"evaluative": 0, "centre_weighted": 1, "spot": 2}  # eNkMAIDMeteringMode
_FOCUS_MODE = {"mf": 0, "af-s": 1, "af-c": 2}  # eNkMAIDFocusMode
_SILENT = {"mechanical": 0, "electronic": 1}  # eNkMAIDSilentMode [Unverified] meaning

_CONFIG_FILES = ("DC_PTP_Config.config", "MaidLayer.config", "RangeValue.config")


# ---- value parsing (pure, tested without the SDK) ------------------------------------------------
def split_packed(raw: bytes) -> list[str]:
    """A packed string array is NUL separated; the last separator ends the data."""
    text = raw.rstrip(b"\x00").decode("utf-8", "replace")
    return text.split("\x00") if text else []


def parse_exposure(text: str) -> float | None:
    """Seconds from strings such as ``1/250``, ``0.5``, ``2"`` or ``30``; None for ``Bulb``."""
    s = text.strip().lower().replace("″", '"').rstrip('s" ')
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", s)
    if m:
        den = float(m.group(2))
        return float(m.group(1)) / den if den else None
    m = re.fullmatch(r"\d+(?:\.\d+)?", s)
    return float(s) if m else None


def parse_aperture(text: str) -> float | None:
    m = re.fullmatch(r"\s*f?\s*/?\s*(\d+(?:\.\d+)?)\s*", text.lower())
    return float(m.group(1)) if m else None


def parse_iso(text: str) -> float | None:
    m = re.fullmatch(r"\s*(?:iso\s*)?(\d+)\s*", text.lower())
    return float(m.group(1)) if m else None


def pick_index(
    values: list[str], parse: Callable[[str], float | None], target: float, rel_tol: float
) -> int | None:
    """Index of the offered value closest to ``target`` within ``rel_tol`` (relative)."""
    best: tuple[float, int] | None = None
    for i, v in enumerate(values):
        x = parse(v)
        if x is None or x <= 0:
            continue
        err = abs(x - target) / target
        if best is None or err < best[0]:
            best = (err, i)
    return best[1] if best and best[0] <= rel_tol else None


# ---- layer interface -------------------------------------------------------------------------------
@dataclass
class EnumData:
    kind: int  # eNkMAIDArrayType
    values: list[Any]
    value: int  # ulValue: an index, or the constant itself for unsigned arrays
    default: int = 0


@dataclass
class RangeData:
    value: float
    index: int
    lower: float
    upper: float
    steps: int


@dataclass
class DeviceEntry:
    id: int
    name: str
    available: bool
    version: str = ""


class Layer(Protocol):
    """What the adapter needs from the Control Service Layer. ``CsLayer`` is the real one."""

    on_saved: Callable[[str], None] | None
    on_live_frame: Callable[[bytes], None] | None

    def initialize(self) -> None: ...
    def shutdown(self) -> None: ...
    def devices(self) -> list[DeviceEntry]: ...
    def connect(self, device_id: int) -> dict[int, int]: ...
    def disconnect(self) -> None: ...
    def get_enum(self, cap: int, supported: bool) -> EnumData | None: ...
    def set_enum(self, cap: int, value: int) -> int: ...
    def get_range(self, cap: int) -> RangeData | None: ...
    def set_range(self, cap: int, value: float, index: int) -> int: ...
    def get_unsigned(self, cap: int) -> int | None: ...
    def start_shooting(self, kind: int, count: int, save_dir: Path) -> int: ...
    def start_live_view(self) -> int: ...
    def stop_live_view(self) -> int: ...


# ---- ctypes binding ----------------------------------------------------------------------------------
_FUNC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)


class _Enum(ctypes.Structure):  # NkMAIDEnum, packed to 2 bytes by Maid3.h
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulElements", ctypes.c_uint32),
        ("ulValue", ctypes.c_uint32),
        ("ulDefault", ctypes.c_uint32),
        ("wPhysicalBytes", ctypes.c_int16),
        ("pData", ctypes.c_void_p),
    ]


class _Range(ctypes.Structure):  # NkMAIDRange
    _pack_ = 2
    _fields_ = [
        ("lfValue", ctypes.c_double),
        ("lfDefault", ctypes.c_double),
        ("ulValueIndex", ctypes.c_uint32),
        ("ulDefaultIndex", ctypes.c_uint32),
        ("lfLower", ctypes.c_double),
        ("lfUpper", ctypes.c_double),
        ("ulSteps", ctypes.c_uint32),
    ]


class _CapInfo(ctypes.Structure):  # NkMAIDCapInfo
    _pack_ = 2
    _fields_ = [
        ("ulID", ctypes.c_uint32),
        ("ulType", ctypes.c_uint32),
        ("ulVisibility", ctypes.c_uint32),
        ("ulOperations", ctypes.c_uint32),
        ("szDescription", ctypes.c_char * 256),
    ]


class _EnumCapInfo(ctypes.Structure):  # NkMAIDEnumCapInfo
    _pack_ = 2
    _fields_ = [
        ("pCapArray", ctypes.c_void_p),
        ("ulCapCount", ctypes.c_uint32),
        ("ulAllocationSize", ctypes.c_uint32),
    ]


class _DeviceInfo(ctypes.Structure):  # NkMAIDDeviceInfo
    _pack_ = 2
    _fields_ = [
        ("ID", ctypes.c_uint32),
        ("Name", ctypes.c_char * 64),
        ("Availability", ctypes.c_bool),
        ("ulConnectedPID", ctypes.c_uint32),
        ("Version", ctypes.c_char * 64),
    ]


class _EnumDevices(ctypes.Structure):  # NkMAIDEnumDevices
    _pack_ = 2
    _fields_ = [
        ("ulElements", ctypes.c_uint32),
        ("ulValue", ctypes.c_uint32),
        ("pDeviceData", ctypes.c_void_p),
    ]


class _CsCallback(ctypes.Structure):  # NkMAIDCSCallback
    _pack_ = 2
    _fields_ = [
        ("pUIReqProc", ctypes.c_void_p),
        ("pfnEventProc", ctypes.c_void_p),
        ("pProgressProc", ctypes.c_void_p),
        ("pDataProc", ctypes.c_void_p),
        ("pLiveViewDataProc", ctypes.c_void_p),
        ("refProc", ctypes.c_void_p),
    ]


class _Shooting(ctypes.Structure):  # MAIDShootingStructure (Windows layout, wchar_t path)
    _pack_ = 2
    _fields_ = [
        ("ShootingType", ctypes.c_int32),
        ("ulContinuous_Interval_NumShots", ctypes.c_uint32),
        ("ulBULBExposureDuration", ctypes.c_uint32),
        ("ulShootingStartTimeFromNow", ctypes.c_uint32),
        ("ulIntervalTime", ctypes.c_uint32),
        ("bAutoFocus", ctypes.c_bool),
        ("ImageSavePath", ctypes.c_wchar * 1024),
        ("pOutPutRefrence", ctypes.c_void_p),
    ]


# NkMAIDLiveViewData: ulLvImageSize, wPhysicalBytes, wLogicalBits, a 884 byte header (size worked
# out from Maid3.h with 2-byte packing, [Inference]), then the image pointer.
_LV_HEADER_BYTES = 884


class _LiveView(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("ulLvImageSize", ctypes.c_uint32),
        ("wPhysicalBytes", ctypes.c_uint16),
        ("wLogicalBits", ctypes.c_uint16),
        ("header", ctypes.c_ubyte * _LV_HEADER_BYTES),
        ("pImageData", ctypes.c_void_p),
    ]


_ALLOC = _FUNC(ctypes.c_void_p, ctypes.c_size_t)
_FREE = _FUNC(None, ctypes.c_void_p)
_UI_REQUEST = _FUNC(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)
_EVENT = _FUNC(None, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64)
_PROGRESS = _FUNC(
    None, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32
)
_DATA = _FUNC(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_LIVE = _FUNC(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)


def _c_runtime() -> Any:
    for name in ("ucrtbase", "msvcrt"):
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    raise SdkUnavailable("C runtime not found")


class CsLayer:
    """Real layer: calls ``ControlServiceLayer.dll`` through ctypes. Exported names are the plain
    ones used by the sample app (``InitializeSDK``, ``ConnectDevice``, ``StartShooting`` ...)."""

    def __init__(self, library: Path) -> None:
        self.on_saved: Callable[[str], None] | None = None
        self.on_live_frame: Callable[[bytes], None] | None = None
        self._path = library
        self._dll_dir: Any = None
        if hasattr(os, "add_dll_directory"):
            self._dll_dir = os.add_dll_directory(str(library.parent))
        try:
            self._dll = (
                ctypes.WinDLL(str(library)) if os.name == "nt" else ctypes.CDLL(str(library))
            )
        except OSError as exc:
            raise SdkUnavailable(f"cannot load {library.name}: {exc}") from exc
        self._crt = _c_runtime()
        self._crt.malloc.restype = ctypes.c_void_p
        self._crt.malloc.argtypes = [ctypes.c_size_t]
        self._crt.free.argtypes = [ctypes.c_void_p]
        self._crt.free.restype = None
        # Keep every callback object alive for as long as the SDK may call it.
        self._alloc = _ALLOC(lambda n: self._crt.malloc(n))
        self._free = _FREE(lambda p: self._crt.free(p))
        self._ui = _UI_REQUEST(self._ui_request)
        self._event = _EVENT(self._on_event)
        self._progress = _PROGRESS(lambda *_a: None)
        self._data = _DATA(lambda *_a: 0)
        self._live = _LIVE(self._on_live)
        self._callback = _CsCallback()
        self._device_list = ctypes.POINTER(_EnumDevices)()
        self._cap_ops: dict[int, int] = {}
        self._initialised = False
        self._bind()

    # -- binding -------------------------------------------------------------------------------
    def _fn(self, name: str, argtypes: list[Any], restype: Any = ctypes.c_int32) -> Any:
        try:
            fn = getattr(self._dll, name)
        except AttributeError as exc:
            raise SdkUnavailable(f"{self._path.name} has no export {name}") from exc
        fn.argtypes = argtypes
        fn.restype = restype
        return fn

    def _bind(self) -> None:
        u32, i32, vp = ctypes.c_uint32, ctypes.c_int32, ctypes.c_void_p
        pp = ctypes.POINTER
        self._initialize_sdk = self._fn(
            "InitializeSDK", [_ALLOC, _FREE, pp(_CsCallback), pp(pp(_EnumDevices)), vp]
        )
        self._free_sdk = self._fn("FreeSDK", [])
        self._enum_devices = self._fn("EnumDevices", [pp(pp(_EnumDevices)), vp, vp])
        self._connect = self._fn("ConnectDevice", [u32, pp(pp(_EnumCapInfo))])
        self._disconnect = self._fn("DisconnectDevice", [])
        self._get_cap = self._fn("GetCapability", [u32, i32, pp(vp), pp(i32)])
        self._set_cap = self._fn("SetCapability", [u32, vp, i32])
        self._start_shooting = self._fn("StartShooting", [pp(_Shooting), vp, vp])
        self._start_lv = self._fn("StartLiveView", [vp, vp])
        self._stop_lv = self._fn("StopLiveView", [vp, vp])
        self._set_save_path = self._fn(
            "SetImageVideoSavePath", [ctypes.c_wchar_p, ctypes.c_wchar_p]
        )

    # -- callbacks (run on SDK threads) ---------------------------------------------------------
    def _ui_request(self, _ref: Any, info: Any) -> int:
        if not info:
            return 1
        default = ctypes.cast(info, ctypes.POINTER(ctypes.c_uint32))[1]
        return int(default) or 1  # kNkMAIDUIRequestResult_Ok when the SDK has no default

    def _on_event(self, _ref: Any, event: int, data: int) -> None:
        if event == EVENT_IMAGE_SAVED and data:
            try:
                path = ctypes.wstring_at(data)
            finally:
                self._crt.free(ctypes.c_void_p(data))
            if self.on_saved is not None:
                self.on_saved(path)

    def _on_live(self, _ref: Any, ptr: Any) -> int:
        if not ptr:
            return RESULT_OK
        lv = ctypes.cast(ptr, ctypes.POINTER(_LiveView)).contents
        try:
            if lv.pImageData and lv.ulLvImageSize and self.on_live_frame is not None:
                self.on_live_frame(ctypes.string_at(lv.pImageData, lv.ulLvImageSize))
        finally:
            if lv.pImageData:
                self._crt.free(ctypes.c_void_p(lv.pImageData))
            self._crt.free(ctypes.c_void_p(ptr))
        return RESULT_OK

    # -- lifecycle ------------------------------------------------------------------------------
    def initialize(self) -> None:
        cb = self._callback
        cb.pUIReqProc = ctypes.cast(self._ui, ctypes.c_void_p)
        cb.pfnEventProc = ctypes.cast(self._event, ctypes.c_void_p)
        cb.pProgressProc = ctypes.cast(self._progress, ctypes.c_void_p)
        cb.pDataProc = ctypes.cast(self._data, ctypes.c_void_p)
        cb.pLiveViewDataProc = ctypes.cast(self._live, ctypes.c_void_p)
        cb.refProc = None
        err = self._initialize_sdk(
            self._alloc, self._free, ctypes.byref(cb), ctypes.byref(self._device_list), None
        )
        if err != RESULT_OK:
            raise SdkUnavailable(f"InitializeSDK failed ({err})")
        self._initialised = True
        self._set_save_path("", "")

    def shutdown(self) -> None:
        if self._initialised:
            with contextlib.suppress(Exception):
                self._free_sdk()
            self._initialised = False
        if self._dll_dir is not None:
            with contextlib.suppress(Exception):
                self._dll_dir.close()
            self._dll_dir = None

    def devices(self) -> list[DeviceEntry]:
        self._release_device_list()
        lst = ctypes.POINTER(_EnumDevices)()
        if self._enum_devices(ctypes.byref(lst), None, None) != RESULT_OK or not lst:
            return []
        self._device_list = lst
        n = lst.contents.ulElements
        base = lst.contents.pDeviceData
        out: list[DeviceEntry] = []
        if base:
            arr = ctypes.cast(base, ctypes.POINTER(_DeviceInfo))
            for i in range(n):
                d = arr[i]
                out.append(
                    DeviceEntry(
                        d.ID,
                        d.Name.decode("utf-8", "replace"),
                        bool(d.Availability),
                        d.Version.decode("utf-8", "replace"),
                    )
                )
        return out

    def _release_device_list(self) -> None:
        lst = self._device_list
        if lst:
            if lst.contents.pDeviceData:
                self._crt.free(ctypes.c_void_p(lst.contents.pDeviceData))
            self._crt.free(ctypes.cast(lst, ctypes.c_void_p))
        self._device_list = ctypes.POINTER(_EnumDevices)()

    def connect(self, device_id: int) -> dict[int, int]:
        caps = ctypes.POINTER(_EnumCapInfo)()
        err = self._connect(device_id, ctypes.byref(caps))
        if err != RESULT_OK:
            raise CommandFailed(f"ConnectDevice failed ({err})")
        ops: dict[int, int] = {}
        if caps:
            info = caps.contents
            if info.pCapArray:
                arr = ctypes.cast(info.pCapArray, ctypes.POINTER(_CapInfo))
                for i in range(info.ulCapCount):
                    ops[arr[i].ulID] = arr[i].ulOperations
                self._crt.free(ctypes.c_void_p(info.pCapArray))
            self._crt.free(ctypes.cast(caps, ctypes.c_void_p))
        self._cap_ops = ops
        return ops

    def disconnect(self) -> None:
        self._disconnect()

    # -- capabilities ---------------------------------------------------------------------------
    def _get(self, cap: int, request: int) -> tuple[int, int | None, int]:
        ptr = ctypes.c_void_p()
        dtype = ctypes.c_int32(0)
        err = self._get_cap(cap, request, ctypes.byref(ptr), ctypes.byref(dtype))
        return err, ptr.value, dtype.value

    def _free_data(self, addr: int, dtype: int) -> None:
        if dtype == DT_ENUM_PTR:
            inner = _Enum.from_address(addr).pData
            if inner:
                self._crt.free(ctypes.c_void_p(inner))
        elif dtype == DT_ARRAY_PTR:
            # NkMAIDArray keeps its data pointer in the last field; not needed by this adapter.
            pass
        self._crt.free(ctypes.c_void_p(addr))

    def get_enum(self, cap: int, supported: bool) -> EnumData | None:
        err, addr, dtype = self._get(cap, GET_SUPPORTED_ARRAY if supported else GET_VALUE)
        if err != RESULT_OK or not addr:
            if addr:
                self._free_data(addr, dtype)
            return None
        try:
            if dtype != DT_ENUM_PTR:
                return None
            s = _Enum.from_address(addr)
            values: list[Any] = []
            if s.pData and s.ulElements:
                if s.ulType == ARRAY_PACKED_STRING:
                    values = split_packed(ctypes.string_at(s.pData, s.ulElements))
                elif s.ulType in (ARRAY_UNSIGNED, ARRAY_INTEGER, ARRAY_BOOLEAN):
                    width = max(int(s.wPhysicalBytes), 1)
                    raw = ctypes.string_at(s.pData, s.ulElements * width)
                    signed = s.ulType == ARRAY_INTEGER
                    values = [
                        int.from_bytes(raw[i : i + width], "little", signed=signed)
                        for i in range(0, len(raw), width)
                    ]
                elif s.ulType == ARRAY_STRING:
                    raw = ctypes.string_at(s.pData, s.ulElements * 256)
                    values = [
                        raw[i : i + 256].split(b"\x00", 1)[0].decode("utf-8", "replace")
                        for i in range(0, len(raw), 256)
                    ]
            return EnumData(int(s.ulType), values, int(s.ulValue), int(s.ulDefault))
        finally:
            self._free_data(addr, dtype)

    def set_enum(self, cap: int, value: int) -> int:
        err, addr, dtype = self._get(cap, GET_VALUE)
        if err != RESULT_OK or not addr or dtype != DT_ENUM_PTR:
            if addr:
                self._free_data(addr, dtype)
            return err or -1
        try:
            s = _Enum.from_address(addr)
            send = _Enum(s.ulType, s.ulElements, value, s.ulDefault, s.wPhysicalBytes, None)
        finally:
            self._free_data(addr, dtype)
        return int(self._set_cap(cap, ctypes.byref(send), DT_ENUM_PTR))

    def get_range(self, cap: int) -> RangeData | None:
        err, addr, dtype = self._get(cap, GET_VALUE)
        if err != RESULT_OK or not addr:
            if addr:
                self._free_data(addr, dtype)
            return None
        try:
            if dtype != DT_RANGE_PTR:
                return None
            r = _Range.from_address(addr)
            return RangeData(
                float(r.lfValue),
                int(r.ulValueIndex),
                float(r.lfLower),
                float(r.lfUpper),
                int(r.ulSteps),
            )
        finally:
            self._free_data(addr, dtype)

    def set_range(self, cap: int, value: float, index: int) -> int:
        err, addr, dtype = self._get(cap, GET_VALUE)
        if err != RESULT_OK or not addr or dtype != DT_RANGE_PTR:
            if addr:
                self._free_data(addr, dtype)
            return err or -1
        try:
            cur = _Range.from_address(addr)
            send = _Range(
                value,
                cur.lfDefault,
                index,
                cur.ulDefaultIndex,
                cur.lfLower,
                cur.lfUpper,
                cur.ulSteps,
            )
        finally:
            self._free_data(addr, dtype)
        return int(self._set_cap(cap, ctypes.byref(send), DT_RANGE_PTR))

    def get_unsigned(self, cap: int) -> int | None:
        err, addr, dtype = self._get(cap, GET_VALUE)
        if err != RESULT_OK or not addr:
            if addr:
                self._free_data(addr, dtype)
            return None
        try:
            if dtype in (DT_UNSIGNED_PTR, DT_INTEGER_PTR):
                return int(ctypes.c_uint32.from_address(addr).value)
            if dtype == DT_BOOLEAN_PTR:
                return int(ctypes.c_ubyte.from_address(addr).value)
            return None
        finally:
            self._free_data(addr, dtype)

    # -- shooting and live view -----------------------------------------------------------------
    def start_shooting(self, kind: int, count: int, save_dir: Path) -> int:
        s = _Shooting()
        s.ShootingType = kind
        s.ulContinuous_Interval_NumShots = count if kind == SHOOT_CONTINUOUS else 0
        s.bAutoFocus = False
        s.ImageSavePath = str(save_dir)
        return int(self._start_shooting(ctypes.byref(s), None, None))  # synchronous call

    def start_live_view(self) -> int:
        return int(self._start_lv(None, None))

    def stop_live_view(self) -> int:
        return int(self._stop_lv(None, None))


# ---- adapter -------------------------------------------------------------------------------------
@dataclass
class _Saved:
    paths: list[str] = field(default_factory=list)
    last: float = 0.0


class NikonAdapter(SdkAdapter):
    """Nikon backend on the Control Service Layer. Settings go through packed-string enums, so a
    value is matched by parsing what the camera offers, never by assuming a table."""

    brand = "nikon"

    def __init__(
        self, location: SdkLocation, layer_factory: Callable[[Path], Layer] | None = None
    ) -> None:
        super().__init__(location)
        self._factory = layer_factory or CsLayer
        self._layer: Layer | None = None
        self._ops: dict[int, int] = {}
        self._device: DeviceEntry | None = None
        self._saved = _Saved()
        self._cond = threading.Condition()
        self._save_dir: Path | None = None
        self._frame: bytes | None = None
        self._live_on = False

    # ---- lifecycle ---------------------------------------------------------------------------
    def open(self) -> None:
        self._install_config()
        layer = self._factory(self.location.library)
        layer.on_saved = self._saved_event
        layer.on_live_frame = self._live_event
        layer.initialize()
        try:
            self._device = self._find_device(layer)
            self._ops = layer.connect(self._device.id)
        except Exception:
            layer.shutdown()
            raise
        self._layer = layer
        self._save_dir = Path(tempfile.mkdtemp(prefix="cp-nikon-"))

    def close(self) -> None:
        layer, self._layer = self._layer, None
        if layer is not None:
            if self._live_on:
                with contextlib.suppress(Exception):
                    layer.stop_live_view()
                self._live_on = False
            with contextlib.suppress(Exception):
                layer.disconnect()
            layer.shutdown()
        if self._save_dir is not None:
            shutil.rmtree(self._save_dir, ignore_errors=True)
            self._save_dir = None

    def _install_config(self) -> None:
        """The SDK reads three profiles from %LOCALAPPDATA%\\Nikon\\NXTether (its ReadMe). They
        are copied from the SDK folder only when missing; nothing is overwritten."""
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            return
        dest = Path(base) / "Nikon" / "NXTether"
        for name in _CONFIG_FILES:
            src = self.location.library.parent / name
            if src.is_file() and not (dest / name).exists():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / name)

    @staticmethod
    def _find_device(layer: Layer) -> DeviceEntry:
        deadline = time.monotonic() + 5.0
        while True:
            for d in layer.devices():
                if d.available:
                    return d
            if time.monotonic() >= deadline:
                raise CommandFailed("no Nikon camera found")
            time.sleep(0.25)

    @property
    def layer(self) -> Layer:
        if self._layer is None:
            raise CommandFailed("session not open")
        return self._layer

    def _has(self, cap: int, op: int) -> bool:
        return bool(self._ops.get(cap, 0) & op)

    # ---- information -------------------------------------------------------------------------
    def capabilities(self) -> Capabilities:
        has = self._ops.__contains__
        return Capabilities(
            brand="Nikon",
            backend=self.name,
            can_capture=True,
            can_set_exposure=has(CAP_SHUTTER_SPEED),
            can_set_iso=has(CAP_SENSITIVITY),
            can_set_aperture=has(CAP_APERTURE),
            can_set_metering=has(CAP_METERING),
            can_set_comp=has(CAP_EXPOSURE_COMP),
            can_set_shutter_mode=has(CAP_SILENT_MODE),
            live_view=True,
            reads_battery=has(CAP_BATTERY),
            sdk_features=self.features(),
        )

    def device_info(self) -> DeviceInfo:
        dev = self._device
        battery = self.layer.get_unsigned(CAP_BATTERY) if CAP_BATTERY in self._ops else None
        if battery is not None and not 0 <= battery <= 100:
            battery = None
        # [Unverified] no serial number or shutter count capability was found in the headers.
        return DeviceInfo(
            brand="Nikon",
            model=dev.name if dev else None,
            firmware=(dev.version or None) if dev else None,
            battery_percent=battery,
        )

    # ---- settings ----------------------------------------------------------------------------
    def snapshot_settings(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        for cap in (
            CAP_SENSITIVITY,
            CAP_SHUTTER_SPEED,
            CAP_APERTURE,
            CAP_METERING,
            CAP_FOCUS_MODE,
            CAP_SILENT_MODE,
        ):
            if cap in self._ops:
                cur = self.layer.get_enum(cap, supported=False)
                if cur is not None:
                    snap[f"e{cap:x}"] = cur.value
        if CAP_EXPOSURE_COMP in self._ops:
            rng = self.layer.get_range(CAP_EXPOSURE_COMP)
            if rng is not None:
                snap[f"r{CAP_EXPOSURE_COMP:x}"] = [rng.value, rng.index]
        return snap

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        for key, value in snapshot.items():
            cap = int(key[1:], 16)
            if key[0] == "e":
                self._check(self.layer.set_enum(cap, int(value)), "restore")
            elif key[0] == "r":
                self._check(self.layer.set_range(cap, float(value[0]), int(value[1])), "restore")

    def apply_settings(self, settings: CaptureSettings) -> None:
        if settings.af_point is not None:
            raise NotSupported("remote AF point selection is not bound for Nikon (V-03)")
        if settings.iso is not None:
            self._set_by_text(CAP_SENSITIVITY, parse_iso, float(settings.iso), 0.0, "ISO")
        if settings.exposure_s is not None:
            self._set_by_text(
                CAP_SHUTTER_SPEED, parse_exposure, settings.exposure_s, 0.03, "exposure"
            )
        if settings.aperture is not None:
            self._set_by_text(CAP_APERTURE, parse_aperture, settings.aperture, 0.03, "aperture")
        if settings.exposure_comp_ev is not None:
            self._set_comp(settings.exposure_comp_ev)
        if settings.metering is not None:
            self._set_constant(CAP_METERING, _METERING, settings.metering, "metering")
        if settings.focus_mode is not None:
            self._set_constant(
                CAP_FOCUS_MODE, _FOCUS_MODE, settings.focus_mode.lower(), "focus mode"
            )
        if settings.shutter_mode is not None:
            self._set_constant(CAP_SILENT_MODE, _SILENT, settings.shutter_mode, "shutter mode")

    def _need_set(self, cap: int, label: str) -> None:
        if cap not in self._ops:
            raise NotSupported(f"{label} is not offered by this body")
        if not self._has(cap, 0x0004):  # kNkMAIDCapOperation_Set
            raise CommandFailed(f"{label} cannot be changed now")

    def _set_by_text(
        self, cap: int, parse: Callable[[str], float | None], target: float, tol: float, label: str
    ) -> None:
        self._need_set(cap, label)
        offered = self.layer.get_enum(cap, supported=True)
        if offered is None or offered.kind != ARRAY_PACKED_STRING:
            raise NotSupported(f"{label} values are not text on this body [Unverified]")
        idx = pick_index([str(v) for v in offered.values], parse, target, tol)
        if idx is None:
            raise CommandFailed(f"{label} {target:g} is not offered by the camera")
        self._check(self.layer.set_enum(cap, idx), label)

    def _set_constant(self, cap: int, table: dict[str, int], key: str, label: str) -> None:
        self._need_set(cap, label)
        if key not in table:
            raise NotSupported(f"{label} {key!r} has no Nikon value")
        wanted = table[key]
        offered = self.layer.get_enum(cap, supported=True)
        if offered is not None and offered.values and wanted not in offered.values:
            raise CommandFailed(f"{label} {key!r} is not offered by the camera")
        self._check(self.layer.set_enum(cap, wanted), label)

    def _set_comp(self, ev: float) -> None:
        self._need_set(CAP_EXPOSURE_COMP, "compensation")
        rng = self.layer.get_range(CAP_EXPOSURE_COMP)
        if rng is None:
            raise NotSupported("compensation range is not readable")
        if not rng.lower - 1e-9 <= ev <= rng.upper + 1e-9:
            raise CommandFailed(f"compensation {ev:g} EV is outside the camera range")
        index = 0
        if rng.steps > 1:
            index = round((ev - rng.lower) * (rng.steps - 1) / (rng.upper - rng.lower))
        self._check(self.layer.set_range(CAP_EXPOSURE_COMP, ev, index), "compensation")

    @staticmethod
    def _check(code: int, label: str) -> None:
        if code != RESULT_OK:
            raise CommandFailed(f"{label}: SDK result {code}")

    # ---- capture -----------------------------------------------------------------------------
    def _saved_event(self, path: str) -> None:
        with self._cond:
            self._saved.paths.append(path)
            self._saved.last = time.monotonic()
            self._cond.notify_all()

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        assert self._save_dir is not None
        burst = max(settings.burst, 1)
        with self._cond:
            self._saved = _Saved()
        kind = SHOOT_CONTINUOUS if burst > 1 else SHOOT_SINGLE
        code = self.layer.start_shooting(kind, burst, self._save_dir)
        if code == RESULT_OUT_OF_FOCUS:
            return CaptureOutcome(ok=False, focus_failed=True)  # tier 1 signal (R-01)
        if code != RESULT_OK:
            raise CommandFailed(f"StartShooting: SDK result {code}")
        deadline = time.monotonic() + timeout_s
        with self._cond:
            while True:
                n = len(self._saved.paths)
                settled = n >= burst and time.monotonic() - self._saved.last >= 1.0
                now = time.monotonic()
                if settled or now >= deadline:
                    break
                self._cond.wait(timeout=min(0.25, max(deadline - now, 0.01)))
            paths = list(self._saved.paths)
        files = [RemoteFile(ref=p, name=Path(p).name, size=_size(p)) for p in paths]
        if len(paths) < burst:
            return CaptureOutcome(ok=False, files=files, timed_out=True)
        return CaptureOutcome(ok=True, files=files)

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path:
        src = Path(ref.ref).resolve()
        root = self._save_dir.resolve() if self._save_dir else None
        if root is None or root not in src.parents or not src.is_file():
            raise CommandFailed("file is not one captured in this session")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        return dest

    # ---- live view -----------------------------------------------------------------------------
    def _live_event(self, jpeg: bytes) -> None:
        with self._cond:
            self._frame = jpeg
            self._cond.notify_all()

    def live_view_frame(self) -> Any | None:
        if not self._live_on:
            if self.layer.start_live_view() != RESULT_OK:
                return None
            self._live_on = True
        with self._cond:
            self._frame = None
            self._cond.wait_for(lambda: self._frame is not None, timeout=2.0)
            jpeg = self._frame
        return _decode_jpeg(jpeg) if jpeg else None

    def features(self) -> tuple[str, ...]:
        # Only what is bound: the out-of-focus result of StartShooting. AF point selection and
        # focus drive are not bound until a hardware log exists (V-03, V-23).
        return ("focus_check",)


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
