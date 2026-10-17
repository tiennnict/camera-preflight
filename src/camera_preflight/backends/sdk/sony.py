"""Sony adapter on the Camera Remote SDK v2.02.00 (WP-47, FR-CON-03, D-31).

The binding follows ``CameraRemote_SDK.h``, ``CrDeviceProperty.h``, ``IDeviceCallback.h`` and the
``SimpleCli`` and ``RemoteCli`` samples that the maintainer downloads into ``sdk/sony``. No SDK
file is part of the repository. The library loads only inside the backend host process.

The exported functions are plain ``extern "C"``. Two things are C++ objects and are handled by hand:
the callback object (a table of virtual functions built here) and the camera list returned by
``EnumCameraObjects`` (called through its table).

Labels: function names, enums, property codes and value encodings are ``[Sourced]`` from those
headers. Object layouts worked out from the private fields (``CrDeviceProperty`` 64 bytes,
``CrImageDataBlock`` 24 bytes) and the table order of the callback methods are ``[Inference]``
for the 64-bit Windows build. Camera behaviour is ``[Unverified]`` until a hardware log exists.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
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

# ---- property codes (CrDevicePropertyCode) [Sourced] ----------------------------------------------
P_S1 = 0x1
P_FNUMBER = 0x100
P_EXPOSURE_BIAS = 0x101
P_SHUTTER_SPEED = 0x103
P_ISO = 0x104
P_FOCUS_MODE = 0x109
P_METERING = 0x10A
P_SHUTTER_TYPE = 0x1A9
P_BATTERY_REMAIN = 0x702
P_FOCUS_INDICATION = 0x707
P_LENS_MODEL = 0x765
P_BODY_SERIAL = 0x79F
P_MODEL_NAME = 0x7B2

# CrDataType
T_UINT8, T_UINT16, T_UINT32, T_UINT64 = 0x1, 0x2, 0x3, 0x4
T_SIGN, T_ARRAY = 0x1000, 0x2000
T_UINT16_ARRAY = T_ARRAY | T_UINT16

# CrPropertyEnableFlag
ENABLE_TRUE, ENABLE_DISPLAY_ONLY, ENABLE_SET_ONLY = 1, 2, 3

# CrCommandId / CrCommandParam / CrLockIndicator
CMD_RELEASE = 0
PARAM_UP, PARAM_DOWN = 0, 1
LOCK_UNLOCKED, LOCK_LOCKED = 1, 2

# CrFocusIndicator
FOCUS_NOT_FOCUSED = (0x00000202, 0x00000203)
FOCUS_DONE = (0x00000102, 0x00000103, 0x00000202, 0x00000203)

# CrFocusMode, CrShutterType, CrMeteringMode
FOCUS_MF, FOCUS_AF_S, FOCUS_AF_C = 0x1, 0x2, 0x3
SHUTTER_MECHANICAL, SHUTTER_ELECTRONIC = 0x2, 0x3
_FOCUS = {"mf": FOCUS_MF, "af-s": FOCUS_AF_S, "af-c": FOCUS_AF_C}
_SHUTTER = {"mechanical": SHUTTER_MECHANICAL, "electronic": SHUTTER_ELECTRONIC}
# First value the camera offers wins: the table lists the Sony names closest to each term.
_METERING = {
    "evaluative": (0x5, 0x1),  # Multi, Average
    "centre_weighted": (0x2, 0x6),  # CenterWeightedAverage, CenterWeighted
    "spot": (0x4, 0x8, 0x3),  # CenterSpot, Spot_Standard, MultiSpot
}

CR_OK = 0
SETTLE_S = 2.0


# ---- value parsing (pure, tested without the SDK) ---------------------------------------------------
def decode_shutter(v: int) -> float | None:
    """Upper two bytes numerator, lower two bytes denominator; 0 is Bulb."""
    num, den = (v >> 16) & 0xFFFF, v & 0xFFFF
    if v in (0, 0xFFFFFFFF) or den == 0:
        return None
    return num / den


def decode_fnumber(v: int) -> float | None:
    return None if v >= 0xFFFD or v == 0 else v / 100


def decode_iso(v: int) -> float | None:
    """Bits 0-23 ISO value, bits 24-27 ISO mode (0 = normal); auto is all ones."""
    if v == 0x00FFFFFF or (v >> 24) & 0xF != 0:
        return None
    return float(v & 0xFFFFFF) or None


def pick_value(
    offered: list[int], decode: Callable[[int], float | None], target: float, rel_tol: float
) -> int | None:
    """The offered raw value whose decoded number is closest to ``target`` within ``rel_tol``."""
    best: tuple[float, int] | None = None
    for raw in offered:
        x = decode(raw)
        if x is None or x <= 0:
            continue
        err = abs(x - target) / target
        if best is None or err < best[0]:
            best = (err, raw)
    return best[1] if best and best[0] <= rel_tol else None


def to_signed16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


# ---- layer interface ---------------------------------------------------------------------------------
@dataclass
class PropData:
    code: int
    vtype: int
    enable: int
    current: int
    values: list[int] = field(default_factory=list)  # selectable values the camera reports
    text: str | None = None

    @property
    def settable(self) -> bool:
        return self.enable in (ENABLE_TRUE, ENABLE_SET_ONLY)


@dataclass
class CameraEntry:
    index: int
    name: str
    model: str


class Layer(Protocol):
    on_download: Callable[[str], None] | None
    on_connected: Callable[[], None] | None
    on_disconnected: Callable[[int], None] | None
    on_error: Callable[[int], None] | None

    def init(self) -> None: ...
    def release(self) -> None: ...
    def enumerate(self, timeout_s: int) -> list[CameraEntry]: ...
    def connect(self, index: int) -> int: ...
    def disconnect(self) -> None: ...
    def get_property(self, code: int) -> PropData | None: ...
    def set_property(self, code: int, value: int, vtype: int) -> int: ...
    def send_command(self, command: int, param: int) -> int: ...
    def set_save_info(self, folder: Path, prefix: str) -> int: ...
    def live_view_jpeg(self) -> bytes | None: ...


# ---- ctypes binding -------------------------------------------------------------------------------------
class _Prop(ctypes.Structure):
    """CrDeviceProperty: private fields in declaration order, 64-bit layout [Inference]."""

    _fields_ = [
        ("code", ctypes.c_uint32),
        ("valueType", ctypes.c_uint32),
        ("enableFlag", ctypes.c_int16),
        ("variableFlag", ctypes.c_uint16),
        ("currentValue", ctypes.c_uint64),
        ("currentStr", ctypes.c_void_p),
        ("valuesSize", ctypes.c_uint32),
        ("values", ctypes.c_void_p),
        ("getSetValuesSize", ctypes.c_uint32),
        ("getSetValues", ctypes.c_void_p),
    ]


class _ImageInfo(ctypes.Structure):  # CrImageInfo
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("bufferSize", ctypes.c_uint32),
    ]


class _ImageBlock(ctypes.Structure):  # CrImageDataBlock
    _fields_ = [
        ("frameNo", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("pData", ctypes.c_void_p),
        ("imageSize", ctypes.c_uint32),
        ("timeCode", ctypes.c_uint32),
    ]


_VOID = ctypes.c_void_p
_SLOT = ctypes.CFUNCTYPE(None, _VOID, _VOID, _VOID, _VOID)  # extra register args are harmless
_CALLBACK_SLOTS = 32  # IDeviceCallback has 21 virtual methods; spare entries stay no-ops
(
    _S_CONNECTED,
    _S_DISCONNECTED,
    _S_PROP,
    _S_PROP_CODES,
    _S_LV_PROP,
    _S_LV_PROP_CODES,
    _S_DOWNLOAD,
    _S_OPERATION,
    _S_CONTENTS,
    _S_WARNING,
    _S_WARNING_EXT,
    _S_ERROR,
) = range(12)


def _vcall(obj: int, slot: int, restype: Any, *argtypes: Any) -> Any:
    """Bind virtual method ``slot`` of the C++ object at ``obj`` (first argument is ``this``)."""
    vtable = ctypes.c_void_p.from_address(obj).value
    assert vtable
    addr = ctypes.c_void_p.from_address(vtable + slot * ctypes.sizeof(ctypes.c_void_p)).value
    prototype: Any = ctypes.CFUNCTYPE(restype, _VOID, *argtypes)
    return prototype(addr)


class CrLayer:
    """Real layer: ``Cr_Core.dll`` through ctypes."""

    def __init__(self, library: Path) -> None:
        self.on_download: Callable[[str], None] | None = None
        self.on_connected: Callable[[], None] | None = None
        self.on_disconnected: Callable[[int], None] | None = None
        self.on_error: Callable[[int], None] | None = None
        self._path = library
        self._dll_dirs: list[Any] = []
        if hasattr(os, "add_dll_directory"):
            for d in (library.parent, library.parent / "CrAdapter"):
                if d.is_dir():
                    self._dll_dirs.append(os.add_dll_directory(str(d)))
        try:
            self._dll = ctypes.CDLL(str(library))
        except OSError as exc:
            raise SdkUnavailable(f"cannot load {library.name}: {exc}") from exc
        self._handle = ctypes.c_int64(0)
        self._enum_obj = ctypes.c_void_p()
        self._cameras: list[int] = []
        self._slots = self._make_callback_table()
        self._bind()

    # -- callback object (IDeviceCallback) -----------------------------------------------------
    def _make_callback_table(self) -> list[Any]:
        noop = _SLOT(lambda *_a: None)
        table: list[Any] = [noop] * _CALLBACK_SLOTS
        table[_S_CONNECTED] = _SLOT(lambda _t, _v, _b, _c: self._fire(self.on_connected))
        table[_S_DISCONNECTED] = _SLOT(
            lambda _t, err, _b, _c: self._fire(self.on_disconnected, int(err or 0) & 0xFFFFFFFF)
        )
        table[_S_DOWNLOAD] = _SLOT(self._download)
        table[_S_ERROR] = _SLOT(
            lambda _t, err, _b, _c: self._fire(self.on_error, int(err or 0) & 0xFFFFFFFF)
        )
        self._vtable = (ctypes.c_void_p * _CALLBACK_SLOTS)(
            *(ctypes.cast(f, ctypes.c_void_p) for f in table)
        )
        self._cb_object = (ctypes.c_void_p * 1)(ctypes.addressof(self._vtable))
        return table

    @staticmethod
    def _fire(fn: Callable[..., None] | None, *args: Any) -> None:
        if fn is not None:
            fn(*args)

    def _download(self, _this: Any, name_ptr: Any, _type: Any, _c: Any) -> None:
        if name_ptr and self.on_download is not None:
            self.on_download(ctypes.wstring_at(name_ptr))

    # -- binding ------------------------------------------------------------------------------------
    def _fn(self, name: str, argtypes: list[Any], restype: Any = ctypes.c_uint32) -> Any:
        try:
            fn = getattr(self._dll, name)
        except AttributeError as exc:
            raise SdkUnavailable(f"{self._path.name} has no export {name}") from exc
        fn.argtypes = argtypes
        fn.restype = restype
        return fn

    def _bind(self) -> None:
        u32, i32, i64, vp = ctypes.c_uint32, ctypes.c_int32, ctypes.c_int64, ctypes.c_void_p
        pp = ctypes.POINTER
        self._init = self._fn("Init", [u32], ctypes.c_bool)
        self._release = self._fn("Release", [], ctypes.c_bool)
        self._enum = self._fn("EnumCameraObjects", [pp(vp), ctypes.c_uint8])
        self._connect = self._fn(
            "Connect",
            [vp, vp, pp(i64), u32, u32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, u32, vp],
        )
        self._disconnect = self._fn("Disconnect", [i64])
        self._release_device = self._fn("ReleaseDevice", [i64])
        self._get_props = self._fn(
            "GetSelectDeviceProperties", [i64, u32, pp(u32), pp(vp), pp(i32)]
        )
        self._release_props = self._fn("ReleaseDeviceProperties", [i64, vp])
        self._set_prop = self._fn("SetDeviceProperty", [i64, vp])
        self._send = self._fn("SendCommand", [i64, u32, ctypes.c_uint16])
        self._save_info = self._fn("SetSaveInfo", [i64, ctypes.c_wchar_p, ctypes.c_wchar_p, i32])
        self._lv_info = self._fn("GetLiveViewImageInfo", [i64, vp])
        self._lv_image = self._fn("GetLiveViewImage", [i64, vp])

    # -- lifecycle ----------------------------------------------------------------------------------------
    def init(self) -> None:
        if not self._init(0):
            raise SdkUnavailable("Init failed")

    def release(self) -> None:
        if self._enum_obj.value:
            with contextlib.suppress(Exception):
                _vcall(self._enum_obj.value, 2, None)(self._enum_obj.value)
            self._enum_obj = ctypes.c_void_p()
        with contextlib.suppress(Exception):
            self._release()
        for d in self._dll_dirs:
            with contextlib.suppress(Exception):
                d.close()
        self._dll_dirs = []

    def enumerate(self, timeout_s: int) -> list[CameraEntry]:
        if self._enum_obj.value:
            _vcall(self._enum_obj.value, 2, None)(self._enum_obj.value)
            self._enum_obj = ctypes.c_void_p()
        err = self._enum(ctypes.byref(self._enum_obj), timeout_s)
        if err != CR_OK or not self._enum_obj.value:
            return []
        obj = self._enum_obj.value
        count = _vcall(obj, 0, ctypes.c_uint32)(obj)
        get_info = _vcall(obj, 1, ctypes.c_void_p, ctypes.c_uint32)
        out: list[CameraEntry] = []
        self._cameras = []
        for i in range(count):
            info = get_info(obj, i)
            if not info:
                continue
            self._cameras.append(info)
            name = _vcall(info, 1, ctypes.c_wchar_p)(info) or ""
            model = _vcall(info, 3, ctypes.c_wchar_p)(info) or ""
            out.append(CameraEntry(i, name, model))
        return out

    def connect(self, index: int) -> int:
        info = self._cameras[index]
        cb = ctypes.addressof(self._cb_object)
        # openMode Remote (0), reconnecting on (1); no user id, password or fingerprint.
        err = self._connect(info, cb, ctypes.byref(self._handle), 0, 1, None, None, None, 0, None)
        return int(err)

    def disconnect(self) -> None:
        if self._handle.value:
            self._disconnect(self._handle.value)
            self._release_device(self._handle.value)
            self._handle = ctypes.c_int64(0)

    # -- properties --------------------------------------------------------------------------------
    def get_property(self, code: int) -> PropData | None:
        codes = (ctypes.c_uint32 * 1)(code)
        props = ctypes.c_void_p()
        count = ctypes.c_int32(0)
        err = self._get_props(
            self._handle.value, 1, codes, ctypes.byref(props), ctypes.byref(count)
        )
        if err != CR_OK or not props.value or count.value < 1:
            return None
        try:
            p = _Prop.from_address(props.value)
            width = {T_UINT8: 1, T_UINT16: 2, T_UINT32: 4, T_UINT64: 8}.get(p.valueType & 0xF, 0)
            signed = bool(p.valueType & T_SIGN)
            values: list[int] = []
            if p.values and width and p.valuesSize:
                raw = ctypes.string_at(p.values, p.valuesSize)
                values = [
                    int.from_bytes(raw[i : i + width], "little", signed=signed)
                    for i in range(0, len(raw) - width + 1, width)
                ]
            text = None
            if p.currentStr:
                n = ctypes.c_uint16.from_address(p.currentStr).value
                if n:
                    text = ctypes.wstring_at(p.currentStr + 2)
            return PropData(
                p.code, int(p.valueType), int(p.enableFlag), int(p.currentValue), values, text
            )
        finally:
            self._release_props(self._handle.value, props)

    def set_property(self, code: int, value: int, vtype: int) -> int:
        p = _Prop()
        p.code = code
        p.valueType = vtype
        p.currentValue = value & 0xFFFFFFFFFFFFFFFF
        return int(self._set_prop(self._handle.value, ctypes.byref(p)))

    def send_command(self, command: int, param: int) -> int:
        return int(self._send(self._handle.value, command, param))

    def set_save_info(self, folder: Path, prefix: str) -> int:
        return int(self._save_info(self._handle.value, str(folder), prefix, -1))

    def live_view_jpeg(self) -> bytes | None:
        info = _ImageInfo()
        if self._lv_info(self._handle.value, ctypes.byref(info)) != CR_OK or not info.bufferSize:
            return None
        buf = ctypes.create_string_buffer(info.bufferSize)
        block = _ImageBlock()
        block.size = info.bufferSize
        block.pData = ctypes.addressof(buf)
        if self._lv_image(self._handle.value, ctypes.byref(block)) != CR_OK:
            return None
        return buf.raw[: block.imageSize] if block.imageSize else None


# ---- adapter ----------------------------------------------------------------------------------------------
class SonyAdapter(SdkAdapter):
    """Sony backend on the Camera Remote SDK. Values are matched on what the camera offers."""

    brand = "sony"

    def __init__(
        self, location: SdkLocation, layer_factory: Callable[[Path], Layer] | None = None
    ) -> None:
        super().__init__(location)
        self._factory = layer_factory or CrLayer
        self._layer: Layer | None = None
        self._save_dir: Path | None = None
        self._cond = threading.Condition()
        self._downloads: list[str] = []
        self._last_download = 0.0
        self._connected = False
        self._error: int | None = None
        self._model = ""

    # ---- lifecycle ---------------------------------------------------------------------------
    def open(self) -> None:
        layer = self._factory(self.location.library)
        layer.on_download = self._on_download
        layer.on_connected = self._on_connected
        layer.on_disconnected = self._on_disconnected
        layer.on_error = self._on_error
        layer.init()
        try:
            cameras = self._find(layer)
            self._model = cameras[0].model or cameras[0].name
            err = layer.connect(cameras[0].index)
            if err != CR_OK:
                raise CommandFailed(f"Connect failed (0x{err:x})")
            with self._cond:
                self._cond.wait_for(lambda: self._connected or self._error is not None, timeout=15)
            if not self._connected:
                raise CommandFailed(f"camera did not connect (error {self._error})")
            self._save_dir = Path(tempfile.mkdtemp(prefix="cp-sony-"))
            err = layer.set_save_info(self._save_dir, "DSC")
            if err != CR_OK:
                raise CommandFailed(f"SetSaveInfo failed (0x{err:x})")
        except Exception:
            with contextlib.suppress(Exception):
                layer.disconnect()
            layer.release()
            raise
        self._layer = layer

    @staticmethod
    def _find(layer: Layer) -> list[CameraEntry]:
        deadline = time.monotonic() + 10
        while True:
            cameras = layer.enumerate(3)
            if cameras:
                return cameras
            if time.monotonic() >= deadline:
                raise CommandFailed("no Sony camera found")

    def close(self) -> None:
        layer, self._layer = self._layer, None
        if layer is not None:
            with contextlib.suppress(Exception):
                layer.disconnect()
            layer.release()
        if self._save_dir is not None:
            shutil.rmtree(self._save_dir, ignore_errors=True)
            self._save_dir = None

    @property
    def layer(self) -> Layer:
        if self._layer is None:
            raise CommandFailed("session not open")
        return self._layer

    # ---- layer events (SDK threads) ------------------------------------------------------------
    def _on_connected(self) -> None:
        with self._cond:
            self._connected = True
            self._cond.notify_all()

    def _on_disconnected(self, error: int) -> None:
        with self._cond:
            self._connected = False
            self._error = error
            self._cond.notify_all()

    def _on_error(self, error: int) -> None:
        with self._cond:
            self._error = error
            self._cond.notify_all()

    def _on_download(self, path: str) -> None:
        with self._cond:
            self._downloads.append(path)
            self._last_download = time.monotonic()
            self._cond.notify_all()

    # ---- information -----------------------------------------------------------------------------
    def capabilities(self) -> Capabilities:
        def can_set(code: int) -> bool:
            p = self.layer.get_property(code)
            return bool(p and p.settable)

        return Capabilities(
            brand="Sony",
            backend=self.name,
            can_capture=True,
            can_set_exposure=can_set(P_SHUTTER_SPEED),
            can_set_iso=can_set(P_ISO),
            can_set_aperture=can_set(P_FNUMBER),
            can_set_metering=can_set(P_METERING),
            can_set_comp=can_set(P_EXPOSURE_BIAS),
            can_set_shutter_mode=can_set(P_SHUTTER_TYPE),
            live_view=True,
            reads_battery=self.layer.get_property(P_BATTERY_REMAIN) is not None,
            sdk_features=self.features(),
        )

    def features(self) -> tuple[str, ...]:
        # Only what is bound: the focus indicator read after a half press. AF area selection and
        # focus drive are not bound until a hardware log exists (V-03, V-23).
        return ("focus_check",)

    def device_info(self) -> DeviceInfo:
        model = self.layer.get_property(P_MODEL_NAME)
        serial = self.layer.get_property(P_BODY_SERIAL)
        lens = self.layer.get_property(P_LENS_MODEL)
        battery = self.layer.get_property(P_BATTERY_REMAIN)
        percent = battery.current if battery and 0 <= battery.current <= 100 else None
        # [Unverified] the unit of the battery property; the shutter count is not exposed in the
        # property list of this SDK version.
        return DeviceInfo(
            brand="Sony",
            model=(model.text if model and model.text else self._model) or None,
            serial=(serial.text if serial and serial.text else None),
            lens=(lens.text if lens and lens.text else None),
            battery_percent=percent,
        )

    # ---- settings ---------------------------------------------------------------------------------
    _SNAPSHOT = (
        P_ISO,
        P_SHUTTER_SPEED,
        P_FNUMBER,
        P_EXPOSURE_BIAS,
        P_METERING,
        P_SHUTTER_TYPE,
        P_FOCUS_MODE,
    )

    def snapshot_settings(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        for code in self._SNAPSHOT:
            p = self.layer.get_property(code)
            if p is not None and p.settable:
                snap[f"{code:x}"] = [p.current, p.vtype]
        return snap

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        for key, (value, vtype) in snapshot.items():
            self._write(int(key, 16), int(value), int(vtype), key)

    def apply_settings(self, settings: CaptureSettings) -> None:
        if settings.af_point is not None:
            raise NotSupported("AF area selection is not bound for Sony (V-03)")
        if settings.burst > 1:
            raise NotSupported("burst over the SDK is not bound for Sony; use the guided step")
        if settings.iso is not None:
            self._set_number(P_ISO, decode_iso, float(settings.iso), 0.0, "ISO")
        if settings.exposure_s is not None:
            self._set_number(P_SHUTTER_SPEED, decode_shutter, settings.exposure_s, 0.03, "exposure")
        if settings.aperture is not None:
            self._set_number(P_FNUMBER, decode_fnumber, settings.aperture, 0.03, "aperture")
        if settings.exposure_comp_ev is not None:
            self._set_comp(settings.exposure_comp_ev)
        if settings.metering is not None:
            self._set_choice(P_METERING, _METERING.get(settings.metering, ()), "metering")
        if settings.focus_mode is not None:
            mode = _FOCUS.get(settings.focus_mode.lower())
            self._set_choice(P_FOCUS_MODE, (mode,) if mode else (), "focus mode")
        if settings.shutter_mode is not None:
            mode = _SHUTTER.get(settings.shutter_mode)
            self._set_choice(P_SHUTTER_TYPE, (mode,) if mode else (), "shutter mode")

    def _prop(self, code: int, label: str) -> PropData:
        p = self.layer.get_property(code)
        if p is None:
            raise NotSupported(f"{label} is not offered by this body")
        if not p.settable:
            raise CommandFailed(f"{label} cannot be changed now")
        return p

    def _set_number(
        self,
        code: int,
        decode: Callable[[int], float | None],
        target: float,
        tol: float,
        label: str,
    ) -> None:
        p = self._prop(code, label)
        raw = pick_value(p.values, decode, target, tol)
        if raw is None:
            raise CommandFailed(f"{label} {target:g} is not offered by the camera")
        self._write(code, raw, p.vtype, label)

    def _set_choice(self, code: int, wanted: tuple[int | None, ...], label: str) -> None:
        p = self._prop(code, label)
        for raw in wanted:
            if raw is not None and raw in p.values:
                self._write(code, raw, p.vtype, label)
                return
        if not wanted:
            raise NotSupported(f"{label} has no Sony value for this request")
        raise CommandFailed(f"{label} is not offered by the camera")

    def _set_comp(self, ev: float) -> None:
        # [Unverified] value = EV * 1000 as a 16 bit number; checked against the offered list.
        p = self._prop(P_EXPOSURE_BIAS, "compensation")
        want = round(ev * 1000)
        offered = {to_signed16(v): v for v in p.values}
        if want not in offered:
            raise CommandFailed(f"compensation {ev:g} EV is not offered by the camera")
        self._write(P_EXPOSURE_BIAS, offered[want] & 0xFFFF, p.vtype, "compensation")

    def _write(self, code: int, value: int, vtype: int, label: str) -> None:
        err = self.layer.set_property(code, value, vtype)
        if err != CR_OK:
            raise CommandFailed(f"{label}: SDK error 0x{err:x}")
        deadline = time.monotonic() + SETTLE_S
        while time.monotonic() < deadline:
            p = self.layer.get_property(code)
            if p is not None and (p.current & 0xFFFFFFFF) == (value & 0xFFFFFFFF):
                return
            time.sleep(0.05)
        raise CommandFailed(f"{label}: the camera did not take the value")

    # ---- capture --------------------------------------------------------------------------------------
    def _autofocus_fails(self) -> bool:
        """Half press and read the focus indicator; True when the camera reports not focused."""
        mode = self.layer.get_property(P_FOCUS_MODE)
        if mode is None or mode.current == FOCUS_MF:
            return False
        self.layer.set_property(P_S1, LOCK_LOCKED, T_UINT16)
        try:
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                p = self.layer.get_property(P_FOCUS_INDICATION)
                if p is not None and p.current in FOCUS_DONE:
                    return p.current in FOCUS_NOT_FOCUSED  # tier 1 signal (R-01)
                time.sleep(0.05)
            return False
        finally:
            self.layer.set_property(P_S1, LOCK_UNLOCKED, T_UINT16)

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        if settings.burst > 1:
            raise NotSupported("burst over the SDK is not bound for Sony; use the guided step")
        with self._cond:
            self._downloads = []
        if self._autofocus_fails():
            return CaptureOutcome(ok=False, focus_failed=True)
        self._check(self.layer.send_command(CMD_RELEASE, PARAM_DOWN), "shutter down")
        time.sleep(0.035)
        self._check(self.layer.send_command(CMD_RELEASE, PARAM_UP), "shutter up")
        deadline = time.monotonic() + timeout_s
        with self._cond:
            while True:
                now = time.monotonic()
                settled = bool(self._downloads) and now - self._last_download >= 1.0
                if settled or now >= deadline:
                    break
                self._cond.wait(timeout=min(0.25, max(deadline - now, 0.01)))
            paths = list(self._downloads)
        files = [RemoteFile(ref=p, name=Path(p).name, size=_size(p)) for p in paths]
        return CaptureOutcome(ok=bool(files), files=files, timed_out=not files)

    @staticmethod
    def _check(code: int, label: str) -> None:
        if code != CR_OK:
            raise CommandFailed(f"{label}: SDK error 0x{code:x}")

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
        jpeg = self.layer.live_view_jpeg()
        return _decode_jpeg(jpeg) if jpeg else None


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
