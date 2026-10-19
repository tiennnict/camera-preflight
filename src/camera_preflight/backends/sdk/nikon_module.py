"""Nikon adapter on the MAID3 "Type00xx" modules of the Nikon SDK for D-SLR bodies (WP-61, D-31).

The Remote SDK in ``nikon.py`` drives only Z bodies. D-SLR bodies such as the D7200 come with
their own module (``Type0017.md3`` for the D7200, from ``S-SDKD7200-011BF-ALLIN``) that speaks the
classic MAID3 object model: a module object, a source object per camera, item objects per shot
and data objects per image. Every command goes through one exported function, ``MAIDEntryPoint``,
and asynchronous work completes only while the client keeps sending ``kNkMAIDCommand_Async``.

The binding follows ``Maid3.h``, ``Maid3d1.h``, the ``Type0017_CtrlSample_Win`` sample and the
documents ``MAID3(E).pdf``, ``MAID3Type0017(E).pdf`` and ``Usage of Type0017 Module(E).pdf`` of
that package. No SDK file is part of the repository. The library is loaded only inside the
backend host process, and every call (including the event callbacks, which the module makes
while it handles ``Async``) runs on the host's one thread.

Labels: command, capability, event and result numbers and the structure fields are ``[Sourced]``
from the headers. The structure layouts with 2-byte packing on x64 and ``BOOL`` as a 4-byte int
are ``[Inference]`` from the headers (``#pragma pack(push,2)``; ``BOOL`` comes from ``windows.h``
on Windows). How the camera behaves is ``[Unverified]`` until a hardware log exists (V-23).
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
from .nikon import (
    ARRAY_PACKED_STRING,
    ARRAY_STRING,
    ARRAY_UNSIGNED,
    EnumData,
    RangeData,
    parse_aperture,
    parse_exposure,
    parse_iso,
    pick_index,
    split_packed,
)

# ---- constants from Maid3.h and Maid3d1.h of the Type0017 package [Sourced] --------------------
CMD_ASYNC, CMD_OPEN, CMD_CLOSE = 0, 1, 2
CMD_GET_CAP_COUNT, CMD_GET_CAP_INFO = 3, 4
CMD_CAP_START, CMD_CAP_SET, CMD_CAP_GET = 5, 6, 7
CMD_CAP_GET_ARRAY = 9

DT_NULL, DT_BOOLEAN, DT_INTEGER, DT_UNSIGNED = 0, 1, 2, 3
DT_BOOLEAN_PTR, DT_INTEGER_PTR, DT_UNSIGNED_PTR = 4, 5, 6
DT_STRING_PTR, DT_CALLBACK_PTR, DT_RANGE_PTR = 11, 13, 14
DT_ARRAY_PTR, DT_ENUM_PTR, DT_OBJECT_PTR, DT_CAPINFO_PTR = 15, 16, 17, 18

CAPTYPE_PROCESS, CAPTYPE_BOOLEAN, CAPTYPE_INTEGER, CAPTYPE_UNSIGNED = 0, 1, 2, 3
CAPTYPE_STRING, CAPTYPE_ARRAY, CAPTYPE_ENUM, CAPTYPE_RANGE = 8, 11, 12, 13

OP_START, OP_GET, OP_SET, OP_GET_ARRAY = 0x1, 0x2, 0x4, 0x8

CAP_PROGRESS_PROC = 0x02
CAP_EVENT_PROC = 0x03
CAP_DATA_PROC = 0x04
CAP_UI_REQUEST_PROC = 0x05
CAP_CHILDREN = 0x07
CAP_NAME = 0x09
CAP_DATA_TYPES = 0x0C
CAP_CAPTURE = 0x11
CAP_ACQUIRE = 0x14
CAP_BATTERY = 0x31  # kNkMAIDType_Integer, percent; -1 on DC-IN (MAID3Type0017 4.47)
CAP_MODULE_MODE = 0x8101
CAP_COMPRESSION = 0x8110  # packed strings "JPEG Basic" ... "RAW" ... (MAID3Type0017 3.2)
CAP_EXPOSURE_MODE = 0x8111
CAP_SHUTTER_SPEED = 0x8112
CAP_APERTURE = 0x8113
CAP_EXPOSURE_COMP = 0x8115
CAP_METERING = 0x8116
CAP_SENSITIVITY = 0x8117
CAP_FOCUS_MODE = 0x8120
CAP_NOISE_REDUCTION = 0x816D  # long exposure NR, Boolean (MAID3Type0017 3.39)
CAP_SHOOTING_MODE = 0x818D
CAP_CONTINUOUS_NUM = 0x81AE
CAP_CAMERA_TYPE = 0x81D7
CAP_AF_CAPTURE = 0x8225
CAP_LIVE_VIEW_STATUS = 0x823E
CAP_LIVE_VIEW_IMAGE = 0x8247
CAP_SAVE_MEDIA = 0x8305

MODULE_MODE_CONTROLLER = 1
SAVE_MEDIA_SDRAM = 1
EXPOSURE_MODE_MANUAL = 3
SHOOTING_MODE_SINGLE, SHOOTING_MODE_CH = 0, 2
DATA_OBJ_IMAGE = 0x1

EVENT_ADD_CHILD, EVENT_REMOVE_CHILD = 0, 1
EVENT_CAP_CHANGE, EVENT_CAP_CHANGE_VALUE_ONLY = 4, 6
EVENT_CAPTURE_COMPLETE, EVENT_CAP_CHANGE_OPERATION_ONLY = 0x108, 0x10B

RESULT_OK, RESULT_PENDING = 0, 1
RESULT_NOT_SUPPORTED = -127
RESULT_BUFFER_SIZE = -124
RESULT_APERTURE_FEE = 128
RESULT_MEDIA_FULL = 131
RESULT_CAMERA_NOT_FOUND = 134
RESULT_OUT_OF_FOCUS = 137
RESULT_CAPTURE_FAILURE = 148
RESULT_DEVICE_BUSY = 152

FILE_JPEG, FILE_TIFF, FILE_NIF, FILE_NDF = 1, 2, 4, 0x101

CAMERA_TYPES = {0x3D: "D7200"}  # eNkMAIDCameraType of the Type0017 package
_METERING = {"evaluative": 0, "centre_weighted": 1, "spot": 2}  # eNkMAIDMeteringMode
_EXTENSIONS = {FILE_NIF: ".NEF", FILE_JPEG: ".JPG", FILE_TIFF: ".TIF", FILE_NDF: ".NDF"}
_RESULT_TEXT = {
    RESULT_APERTURE_FEE: "lens aperture ring is not at the minimum (FEE)",
    RESULT_MEDIA_FULL: "camera memory is full",
    RESULT_CAMERA_NOT_FOUND: "camera not found",
    RESULT_OUT_OF_FOCUS: "out of focus",
    RESULT_CAPTURE_FAILURE: "capture failed",
    RESULT_DEVICE_BUSY: "camera is busy",
    RESULT_NOT_SUPPORTED: "not supported in the current camera state",
}

SOURCE_WAIT_S = 6.0  # time for the module to report a connected camera [Guess]
LIVE_VIEW_START_S = 3.0  # time for the first live view frame after switching it on [Guess]


def describe(code: int) -> str:
    return _RESULT_TEXT.get(code, f"SDK result {code}")


def jpeg_payload(data: bytes) -> bytes | None:
    """The JPEG inside a live view buffer: a fixed header (384 bytes on the D7200 according to the
    sample) precedes it. The start marker is searched for so the header size is not assumed."""
    start = data.find(b"\xff\xd8\xff")
    if start < 0:
        return None
    end = data.rfind(b"\xff\xd9")
    return data[start : end + 2] if end > start else data[start:]


def find_text(values: list[str], wanted: str) -> int | None:
    """Index of the offered value that equals ``wanted`` ignoring case and spaces."""
    key = wanted.replace(" ", "").lower()
    for i, v in enumerate(values):
        if v.replace(" ", "").lower() == key:
            return i
    return None


# ---- layer interface --------------------------------------------------------------------------------
@dataclass(frozen=True)
class CapMeta:
    type: int
    ops: int


@dataclass
class Delivered:
    name: str
    data: bytes


class ModuleLayer(Protocol):
    """What the adapter needs from a MAID3 module. ``MaidLayer`` is the real one."""

    def open_module(self) -> None: ...
    def wait_source(self, timeout_s: float) -> int | None: ...
    def open_source(self, source_id: int) -> dict[int, CapMeta]: ...
    def caps(self) -> dict[int, CapMeta]: ...
    def get_string(self, cap: int) -> str | None: ...
    def get_number(self, cap: int) -> int | None: ...
    def set_number(self, cap: int, value: int) -> int: ...
    def get_enum(self, cap: int) -> EnumData | None: ...
    def set_enum(self, cap: int, index: int) -> int: ...
    def get_range(self, cap: int) -> RangeData | None: ...
    def set_range(self, cap: int, value: float, index: int) -> int: ...
    def start(self, cap: int, timeout_s: float) -> int: ...
    def wait_items(self, count: int, timeout_s: float) -> list[int]: ...
    def acquire(self, item_id: int, timeout_s: float) -> list[Delivered]: ...
    def live_view_image(self) -> bytes | None: ...
    def source_alive(self) -> bool: ...
    def close(self) -> None: ...


# ---- ctypes binding -------------------------------------------------------------------------------
_FUNC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_NKPARAM = ctypes.c_uint64  # NK_UINT_64 on Win64 (NkTypes.h)


class _Object(ctypes.Structure):  # NkMAIDObject
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulID", ctypes.c_uint32),
        ("refClient", ctypes.c_void_p),
        ("refModule", ctypes.c_void_p),
    ]


class _Callback(ctypes.Structure):  # NkMAIDCallback
    _pack_ = 2
    _fields_ = [("pProc", ctypes.c_void_p), ("refProc", ctypes.c_void_p)]


class _CapInfo(ctypes.Structure):  # NkMAIDCapInfo
    _pack_ = 2
    _fields_ = [
        ("ulID", ctypes.c_uint32),
        ("ulType", ctypes.c_uint32),
        ("ulVisibility", ctypes.c_uint32),
        ("ulOperations", ctypes.c_uint32),
        ("szDescription", ctypes.c_char * 256),
    ]


class _Enum(ctypes.Structure):  # NkMAIDEnum
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


class _Array(ctypes.Structure):  # NkMAIDArray
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulElements", ctypes.c_uint32),
        ("ulDimSize1", ctypes.c_uint32),
        ("ulDimSize2", ctypes.c_uint32),
        ("ulDimSize3", ctypes.c_uint32),
        ("wPhysicalBytes", ctypes.c_uint16),
        ("wLogicalBits", ctypes.c_uint16),
        ("pData", ctypes.c_void_p),
    ]


class _String(ctypes.Structure):  # NkMAIDString
    _pack_ = 2
    _fields_ = [("str", ctypes.c_char * 256)]


class _UIRequest(ctypes.Structure):  # NkMAIDUIRequestInfo
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulDefault", ctypes.c_uint32),
        ("fSync", ctypes.c_int32),
        ("lpPrompt", ctypes.c_char_p),
        ("lpDetail", ctypes.c_char_p),
        ("pObject", ctypes.c_void_p),
        ("data", _NKPARAM),
    ]


class _FileInfo(ctypes.Structure):  # NkMAIDFileInfo
    _pack_ = 2
    _fields_ = [
        ("ulType", ctypes.c_uint32),
        ("ulFileDataType", ctypes.c_uint32),
        ("ulTotalLength", ctypes.c_uint32),
        ("ulStart", ctypes.c_uint32),
        ("ulLength", ctypes.c_uint32),
        ("fDiskFile", ctypes.c_int32),
        ("fRemoveObject", ctypes.c_int32),
    ]


_ENTRY_ARGS = [
    ctypes.POINTER(_Object),
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    _NKPARAM,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_COMPLETION = _FUNC(
    None,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    _NKPARAM,
    ctypes.c_void_p,
    ctypes.c_int32,
)
_EVENT = _FUNC(None, ctypes.c_void_p, ctypes.c_uint32, _NKPARAM)
_DATA = _FUNC(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_PROGRESS = _FUNC(
    None, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32
)
_UI_REQUEST = _FUNC(ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(_UIRequest))


@dataclass
class _Node:
    """One opened MAID object and what the client keeps for it."""

    obj: _Object
    caps: dict[int, CapMeta] = field(default_factory=dict)
    added: list[int] = field(default_factory=list)  # ids from AddChild events
    removed: list[int] = field(default_factory=list)
    stale: bool = False  # a CapChange event came; the list is read again before the next use


class MaidLayer:
    """Real layer: loads a ``Type00xx.md3`` module and calls ``MAIDEntryPoint`` through ctypes."""

    def __init__(self, library: Path) -> None:
        self._dll_dirs = add_dll_directories(library.parent)
        try:
            dll = ctypes.WinDLL(str(library)) if os.name == "nt" else ctypes.CDLL(str(library))  # type: ignore[attr-defined]
            proc = dll.MAIDEntryPoint
        except (OSError, AttributeError) as exc:
            raise SdkUnavailable(f"cannot load {library.name}: {exc}") from exc
        self._dll = dll
        proc.argtypes = _ENTRY_ARGS
        proc.restype = ctypes.c_int32
        self._entry = proc
        # Keep every callback object alive for as long as the module may call it.
        self._completion = _COMPLETION(self._on_completion)
        self._event = _EVENT(self._on_event)
        self._data = _DATA(self._on_data)
        self._progress = _PROGRESS(lambda *_a: None)
        self._ui = _UI_REQUEST(self._on_ui_request)
        self._results: dict[int, int] = {}
        self._seq = 0
        self._nodes: dict[int, _Node] = {}  # key: refClient value
        self._next_key = 1
        self._module: _Node | None = None
        self._source: _Node | None = None
        self._delivered: list[Delivered] = []
        self._buffer = bytearray()
        self._buffer_name = ""

    # -- callbacks (called by the module while it handles a command on this thread) -------------
    def _on_completion(
        self, _obj: Any, _cmd: int, _param: int, _dtype: int, _data: int, ref: Any, result: int
    ) -> None:
        if ref:
            self._results[int(ref)] = int(result)

    def _on_event(self, ref: Any, event: int, data: int) -> None:
        node = self._nodes.get(int(ref or 0))
        if node is None:
            return
        if event == EVENT_ADD_CHILD:
            node.added.append(int(data) & 0xFFFFFFFF)
        elif event == EVENT_REMOVE_CHILD:
            node.removed.append(int(data) & 0xFFFFFFFF)
        elif event in (EVENT_CAP_CHANGE, EVENT_CAP_CHANGE_OPERATION_ONLY):
            node.stale = True  # no SDK call from inside a callback

    def _on_data(self, _ref: Any, info_ptr: Any, data_ptr: Any) -> int:
        if not info_ptr:
            return RESULT_OK
        info = ctypes.cast(info_ptr, ctypes.POINTER(_FileInfo)).contents
        if not info.ulType & 0x10:  # kNkMAIDDataObjType_File: only file delivery is used
            return RESULT_NOT_SUPPORTED
        if info.ulStart == 0:
            self._buffer = bytearray()
        if data_ptr and info.ulLength:
            self._buffer += ctypes.string_at(data_ptr, info.ulLength)
        if len(self._buffer) >= info.ulTotalLength:
            ext = _EXTENSIONS.get(int(info.ulFileDataType), ".DAT")
            name = Path(self._buffer_name or "DSC_0000").stem + ext
            self._delivered.append(Delivered(name, bytes(self._buffer)))
            self._buffer = bytearray()
        return RESULT_OK

    def _on_ui_request(self, _ref: Any, info: Any) -> int:
        """The module asks a question; the answer is its own default (nobody is at a prompt)."""
        try:
            default = int(info.contents.ulDefault)
        except (ValueError, AttributeError):
            default = 0
        return default or 1  # kNkMAIDUIRequestResult_Ok

    # -- raw calls --------------------------------------------------------------------------------
    def _call(
        self,
        obj: _Object | None,
        cmd: int,
        param: int = 0,
        dtype: int = DT_NULL,
        data: int = 0,
        timeout_s: float = 10.0,
    ) -> int:
        """One command; waits for its completion while sending Async (the sample's IdleLoop)."""
        self._seq += 1
        seq = self._seq
        ptr = ctypes.pointer(obj) if obj is not None else None
        code = int(
            self._entry(
                ptr,  # type: ignore[arg-type]
                cmd,
                param,
                dtype,
                data,
                ctypes.cast(self._completion, ctypes.c_void_p),
                ctypes.c_void_p(seq),
            )
        )
        if code not in (RESULT_OK, RESULT_PENDING):
            self._results.pop(seq, None)
            return code
        deadline = time.monotonic() + timeout_s
        target = obj if obj is not None else (self._module.obj if self._module else None)
        while seq not in self._results:
            if time.monotonic() >= deadline:
                raise Disconnected(f"MAID command {cmd} (0x{param:X}) did not complete")
            self._async(target)
            time.sleep(0.01)
        return self._results.pop(seq)

    def _sync(
        self, obj: _Object | None, cmd: int, param: int = 0, dtype: int = DT_NULL, data: int = 0
    ) -> int:
        """Open and Close, called without a completion function as the sample does."""
        ptr = ctypes.pointer(obj) if obj is not None else None
        return int(self._entry(ptr, cmd, param, dtype, data, None, None))  # type: ignore[arg-type]

    def _async(self, obj: _Object | None) -> None:
        if obj is None:
            return
        self._entry(ctypes.pointer(obj), CMD_ASYNC, 0, DT_NULL, 0, None, None)

    def _pump(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._module is not None:
                self._async(self._module.obj)
            if self._source is not None:
                self._async(self._source.obj)
            time.sleep(0.02)

    def _new_node(self, obj_type_hint: int = 0) -> tuple[_Node, int]:
        key = self._next_key
        self._next_key += 1
        obj = _Object()
        obj.ulType = obj_type_hint
        obj.refClient = ctypes.c_void_p(key)
        node = _Node(obj)
        self._nodes[key] = node
        return node, key

    def _open(self, parent: _Node | None, child_id: int) -> _Node:
        node, key = self._new_node()
        parent_obj = parent.obj if parent is not None else None
        code = self._sync(parent_obj, CMD_OPEN, child_id, DT_OBJECT_PTR, ctypes.addressof(node.obj))
        if code not in (RESULT_OK, RESULT_PENDING):
            self._nodes.pop(key, None)
            raise CommandFailed(f"cannot open MAID object {child_id}: {describe(code)}")
        node.caps = self._enum_caps(node.obj)
        self._set_procs(node, key)
        return node

    def _close_node(self, node: _Node | None) -> None:
        if node is None:
            return
        with contextlib.suppress(Exception):
            if self._can(node, CAP_EVENT_PROC, OP_SET):
                self._call(node.obj, CMD_CAP_SET, CAP_EVENT_PROC, DT_NULL, 0)
            self._sync(node.obj, CMD_CLOSE)
        for key, n in list(self._nodes.items()):
            if n is node:
                del self._nodes[key]

    def _enum_caps(self, obj: _Object) -> dict[int, CapMeta]:
        for _ in range(3):  # the count can change between the two calls (BufferSize)
            count = ctypes.c_uint32(0)
            code = self._call(obj, CMD_GET_CAP_COUNT, 0, DT_UNSIGNED_PTR, ctypes.addressof(count))
            if code not in (RESULT_OK, RESULT_PENDING):
                raise CommandFailed(f"capability count: {describe(code)}")
            arr = (_CapInfo * max(count.value, 1))()
            code = self._call(
                obj, CMD_GET_CAP_INFO, count.value, DT_CAPINFO_PTR, ctypes.addressof(arr)
            )
            if code == RESULT_BUFFER_SIZE:
                continue
            if code not in (RESULT_OK, RESULT_PENDING):
                raise CommandFailed(f"capability list: {describe(code)}")
            return {
                int(arr[i].ulID): CapMeta(int(arr[i].ulType), int(arr[i].ulOperations))
                for i in range(count.value)
            }
        raise CommandFailed("capability list keeps changing")

    def _set_procs(self, node: _Node, key: int) -> None:
        cb = _Callback()
        cb.refProc = ctypes.c_void_p(key)
        if self._can(node, CAP_EVENT_PROC, OP_SET):
            cb.pProc = ctypes.cast(self._event, ctypes.c_void_p)
            self._call(node.obj, CMD_CAP_SET, CAP_EVENT_PROC, DT_CALLBACK_PTR, ctypes.addressof(cb))
        if self._can(node, CAP_UI_REQUEST_PROC, OP_SET):
            cb.pProc = ctypes.cast(self._ui, ctypes.c_void_p)
            self._call(
                node.obj, CMD_CAP_SET, CAP_UI_REQUEST_PROC, DT_CALLBACK_PTR, ctypes.addressof(cb)
            )

    def _fresh(self, node: _Node) -> _Node:
        if node.stale:
            node.stale = False
            with contextlib.suppress(CommandFailed):
                node.caps = self._enum_caps(node.obj)
        return node

    def _can(self, node: _Node, cap: int, op: int) -> bool:
        meta = self._fresh(node).caps.get(cap)
        return meta is not None and bool(meta.ops & op)

    @property
    def _src(self) -> _Node:
        if self._source is None:
            raise CommandFailed("no camera open")
        return self._source

    # -- lifecycle --------------------------------------------------------------------------------
    def open_module(self) -> None:
        self._module = self._open(None, 0)
        if self._can(self._module, CAP_MODULE_MODE, OP_SET):
            self._call(
                self._module.obj, CMD_CAP_SET, CAP_MODULE_MODE, DT_UNSIGNED, MODULE_MODE_CONTROLLER
            )

    def wait_source(self, timeout_s: float) -> int | None:
        """A connected camera shows as an AddChild event on the module after Async (Usage 7);
        the Children capability is read as well in case the event came before the callback."""
        module = self._module
        if module is None:
            return None
        deadline = time.monotonic() + timeout_s
        while True:
            if module.added:
                return module.added[0]
            listed = self._children(module)
            if listed:
                return listed[0]
            if time.monotonic() >= deadline:
                return None
            self._pump(0.2)

    def _children(self, node: _Node) -> list[int]:
        e = self._read_enum(node, CAP_CHILDREN)
        return [int(v) for v in e.values] if e is not None else []

    def open_source(self, source_id: int) -> dict[int, CapMeta]:
        if self._module is None:
            raise CommandFailed("module not open")
        self._source = self._open(self._module, source_id)
        return dict(self._source.caps)

    def caps(self) -> dict[int, CapMeta]:
        return dict(self._fresh(self._source).caps) if self._source else {}

    def source_alive(self) -> bool:
        if self._module is None or self._source is None:
            return False
        sid = int(self._source.obj.ulID)
        return sid not in self._module.removed

    def close(self) -> None:
        self._close_node(self._source)
        self._source = None
        self._close_node(self._module)
        self._module = None
        for d in self._dll_dirs:
            with contextlib.suppress(Exception):
                d.close()
        self._dll_dirs = []

    # -- values -----------------------------------------------------------------------------------
    def get_string(self, cap: int) -> str | None:
        src = self._src
        if not self._can(src, cap, OP_GET):
            return None
        s = _String()
        if self._call(src.obj, CMD_CAP_GET, cap, DT_STRING_PTR, ctypes.addressof(s)) != RESULT_OK:
            return None
        return s.str.split(b"\x00", 1)[0].decode("utf-8", "replace").strip() or None

    def get_number(self, cap: int) -> int | None:
        src = self._fresh(self._src)
        meta = src.caps.get(cap)
        if meta is None or not meta.ops & OP_GET:
            return None
        if meta.type == CAPTYPE_BOOLEAN:
            b = ctypes.c_ubyte(0)
            code = self._call(src.obj, CMD_CAP_GET, cap, DT_BOOLEAN_PTR, ctypes.addressof(b))
            return int(b.value) if code == RESULT_OK else None
        if meta.type == CAPTYPE_INTEGER:
            i = ctypes.c_int32(0)
            code = self._call(src.obj, CMD_CAP_GET, cap, DT_INTEGER_PTR, ctypes.addressof(i))
            return int(i.value) if code == RESULT_OK else None
        u = ctypes.c_uint32(0)
        code = self._call(src.obj, CMD_CAP_GET, cap, DT_UNSIGNED_PTR, ctypes.addressof(u))
        return int(u.value) if code == RESULT_OK else None

    def set_number(self, cap: int, value: int) -> int:
        src = self._fresh(self._src)
        meta = src.caps.get(cap)
        if meta is None:
            return RESULT_NOT_SUPPORTED
        dtype = {CAPTYPE_BOOLEAN: DT_BOOLEAN, CAPTYPE_INTEGER: DT_INTEGER}.get(
            meta.type, DT_UNSIGNED
        )
        return self._call(src.obj, CMD_CAP_SET, cap, dtype, int(value) & 0xFFFFFFFF)

    def _read_enum(self, node: _Node, cap: int) -> EnumData | None:
        if not self._can(node, cap, OP_GET):
            return None
        e = _Enum()
        if self._call(node.obj, CMD_CAP_GET, cap, DT_ENUM_PTR, ctypes.addressof(e)) != RESULT_OK:
            return None
        values: list[Any] = []
        width = max(int(e.wPhysicalBytes), 1)
        if e.ulElements and self._can(node, cap, OP_GET_ARRAY):
            buf = ctypes.create_string_buffer(int(e.ulElements) * width)
            e.pData = ctypes.cast(buf, ctypes.c_void_p)
            code = self._call(node.obj, CMD_CAP_GET_ARRAY, cap, DT_ENUM_PTR, ctypes.addressof(e))
            if code != RESULT_OK:
                return None
            raw = buf.raw
            if e.ulType == ARRAY_PACKED_STRING:
                values = split_packed(raw)
            elif e.ulType == ARRAY_STRING:
                values = [
                    raw[i : i + 256].split(b"\x00", 1)[0].decode("utf-8", "replace")
                    for i in range(0, len(raw), 256)
                ]
            else:
                values = [
                    int.from_bytes(raw[i : i + width], "little", signed=e.ulType == 1)
                    for i in range(0, len(raw), width)
                ]
        return EnumData(int(e.ulType), values, int(e.ulValue), int(e.ulDefault))

    def get_enum(self, cap: int) -> EnumData | None:
        return self._read_enum(self._src, cap)

    def set_enum(self, cap: int, index: int) -> int:
        """Set by index with the enum structure, as the sample does (CapGet first, Usage 5)."""
        src = self._src
        e = _Enum()
        code = self._call(src.obj, CMD_CAP_GET, cap, DT_ENUM_PTR, ctypes.addressof(e))
        if code != RESULT_OK:
            return code
        width = max(int(e.wPhysicalBytes), 1)
        buf = ctypes.create_string_buffer(max(int(e.ulElements), 1) * width)
        if e.ulElements:
            e.pData = ctypes.cast(buf, ctypes.c_void_p)
            code = self._call(src.obj, CMD_CAP_GET_ARRAY, cap, DT_ENUM_PTR, ctypes.addressof(e))
            if code != RESULT_OK:
                return code
        e.ulValue = index
        return self._call(src.obj, CMD_CAP_SET, cap, DT_ENUM_PTR, ctypes.addressof(e))

    def get_range(self, cap: int) -> RangeData | None:
        src = self._src
        if not self._can(src, cap, OP_GET):
            return None
        r = _Range()
        if self._call(src.obj, CMD_CAP_GET, cap, DT_RANGE_PTR, ctypes.addressof(r)) != RESULT_OK:
            return None
        value = r.lfValue
        if r.ulSteps > 1:
            value = r.lfLower + r.ulValueIndex * (r.lfUpper - r.lfLower) / (r.ulSteps - 1)
        return RangeData(value, int(r.ulValueIndex), r.lfLower, r.lfUpper, int(r.ulSteps))

    def set_range(self, cap: int, value: float, index: int) -> int:
        src = self._src
        r = _Range()
        code = self._call(src.obj, CMD_CAP_GET, cap, DT_RANGE_PTR, ctypes.addressof(r))
        if code != RESULT_OK:
            return code
        r.lfValue = value
        r.ulValueIndex = index
        return self._call(src.obj, CMD_CAP_SET, cap, DT_RANGE_PTR, ctypes.addressof(r))

    # -- shooting -------------------------------------------------------------------------------------
    def start(self, cap: int, timeout_s: float) -> int:
        src = self._src
        src.added.clear()
        return self._call(src.obj, CMD_CAP_START, cap, DT_NULL, 0, timeout_s=timeout_s)

    def wait_items(self, count: int, timeout_s: float) -> list[int]:
        src = self._src
        deadline = time.monotonic() + timeout_s
        while len(src.added) < count and time.monotonic() < deadline:
            self._pump(0.1)
        self._pump(0.3)  # a RAW+JPEG pair or a late item of a burst
        items, src.added = list(src.added), []
        return items

    def acquire(self, item_id: int, timeout_s: float) -> list[Delivered]:
        """Open the item and its image, deliver the file(s), close both (Usage 5.5 and 5.6)."""
        src = self._src
        item = self._open(src, item_id)
        try:
            self._buffer_name = self._name_of(item) or f"DSC_{item_id & 0xFFFF:04d}"
            data = self._open(item, DATA_OBJ_IMAGE)
            try:
                self._delivered = []
                cb = _Callback()
                cb.pProc = ctypes.cast(self._data, ctypes.c_void_p)
                cb.refProc = ctypes.c_void_p(item_id)
                code = self._call(
                    data.obj, CMD_CAP_SET, CAP_DATA_PROC, DT_CALLBACK_PTR, ctypes.addressof(cb)
                )
                if code != RESULT_OK:
                    raise CommandFailed(f"data callback: {describe(code)}")
                code = self._call(data.obj, CMD_CAP_START, CAP_ACQUIRE, timeout_s=timeout_s)
                with contextlib.suppress(Exception):
                    self._call(data.obj, CMD_CAP_SET, CAP_DATA_PROC, DT_NULL, 0)
                if code not in (RESULT_OK, RESULT_PENDING):
                    raise CommandFailed(f"acquire: {describe(code)}")
                return list(self._delivered)
            finally:
                self._close_node(data)
        finally:
            self._close_node(item)
            src.removed.clear()

    def _name_of(self, node: _Node) -> str | None:
        if not self._can(node, CAP_NAME, OP_GET):
            return None
        s = _String()
        if self._call(node.obj, CMD_CAP_GET, CAP_NAME, DT_STRING_PTR, ctypes.addressof(s)) != 0:
            return None
        text = s.str.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
        return Path(text.replace("\\", "/")).name or None

    def live_view_image(self) -> bytes | None:
        src = self._src
        if not self._can(src, CAP_LIVE_VIEW_IMAGE, OP_GET):
            return None
        a = _Array()
        code = self._call(
            src.obj, CMD_CAP_GET, CAP_LIVE_VIEW_IMAGE, DT_ARRAY_PTR, ctypes.addressof(a)
        )
        if code != RESULT_OK or not a.ulElements:
            return None
        buf = ctypes.create_string_buffer(int(a.ulElements) * max(int(a.wPhysicalBytes), 1))
        a.pData = ctypes.cast(buf, ctypes.c_void_p)
        code = self._call(
            src.obj, CMD_CAP_GET_ARRAY, CAP_LIVE_VIEW_IMAGE, DT_ARRAY_PTR, ctypes.addressof(a)
        )
        return buf.raw if code == RESULT_OK else None


# ---- adapter -------------------------------------------------------------------------------------
class NikonModuleAdapter(SdkAdapter):
    """Nikon D-SLR backend on a MAID3 module.

    Images go to the computer only (SaveMedia = SDRAM), so the card in a body on sale is never
    written. For the session the adapter also switches image quality to RAW and long exposure
    noise reduction off (both would hide what the checks look for) and puts them back on close.
    """

    brand = "nikon"

    def __init__(
        self, location: SdkLocation, layer_factory: Callable[[Path], ModuleLayer] | None = None
    ) -> None:
        super().__init__(location)
        self.name = "sdk:nikon-module"
        self._factory = layer_factory or MaidLayer
        self._layer: ModuleLayer | None = None
        self._caps: dict[int, CapMeta] = {}
        self._session: dict[int, tuple[str, Any]] = {}  # values changed for the session
        self._save_dir: Path | None = None
        self._live_on = False
        self._model: str | None = None

    # ---- lifecycle ---------------------------------------------------------------------------
    def open(self) -> None:
        layer = self._factory(self.location.library)
        try:
            layer.open_module()
            source = layer.wait_source(SOURCE_WAIT_S)
            if source is None:
                raise CommandFailed("no Nikon camera found by this module")
            self._caps = layer.open_source(source)
        except Exception:
            with contextlib.suppress(Exception):
                layer.close()
            raise
        self._layer = layer
        self._save_dir = Path(tempfile.mkdtemp(prefix="cp-nikon-"))
        self._model = self._read_model()
        self._prepare_session()

    def close(self) -> None:
        layer, self._layer = self._layer, None
        if layer is not None:
            if self._live_on:
                with contextlib.suppress(Exception):
                    layer.set_number(CAP_LIVE_VIEW_STATUS, 0)
                self._live_on = False
            self._restore_session(layer)
            with contextlib.suppress(Exception):
                layer.close()
        if self._save_dir is not None:
            shutil.rmtree(self._save_dir, ignore_errors=True)
            self._save_dir = None

    def _prepare_session(self) -> None:
        """SDRAM only, RAW, long exposure NR off. A value the body refuses is left as it is: the
        gate then rejects unusable frames with a reason (FR-GATE-02)."""
        layer = self.layer
        self._remember_number(CAP_SAVE_MEDIA, SAVE_MEDIA_SDRAM)
        self._remember_number(CAP_NOISE_REDUCTION, 0)
        q = layer.get_enum(CAP_COMPRESSION) if CAP_COMPRESSION in self._caps else None
        if q is not None and q.kind == ARRAY_PACKED_STRING:
            idx = find_text([str(v) for v in q.values], "RAW")
            if idx is not None and idx != q.value and layer.set_enum(CAP_COMPRESSION, idx) == 0:
                self._session[CAP_COMPRESSION] = ("e", q.value)
        self._caps = layer.caps() or self._caps

    def _remember_number(self, cap: int, value: int) -> None:
        if not self._settable(cap):
            return
        layer = self.layer
        old = layer.get_number(cap)
        if old is None or old == value:
            return
        if layer.set_number(cap, value) == RESULT_OK:
            self._session[cap] = ("n", old)

    def _restore_session(self, layer: ModuleLayer) -> None:
        for cap, (kind, old) in reversed(list(self._session.items())):
            with contextlib.suppress(Exception):
                if kind == "e":
                    layer.set_enum(cap, int(old))
                else:
                    layer.set_number(cap, int(old))
        self._session = {}

    @property
    def layer(self) -> ModuleLayer:
        if self._layer is None:
            raise CommandFailed("session not open")
        return self._layer

    def _refresh(self) -> None:
        self._caps = self.layer.caps() or self._caps

    def _settable(self, cap: int) -> bool:
        meta = self._caps.get(cap)
        return meta is not None and bool(meta.ops & OP_SET)

    def _read_model(self) -> str | None:
        layer = self.layer
        name = layer.get_string(CAP_NAME)
        if name:
            return name.replace("NIKON", "").strip() or name
        kind = layer.get_number(CAP_CAMERA_TYPE)
        return CAMERA_TYPES.get(kind) if kind is not None else None

    # ---- information -------------------------------------------------------------------------
    def capabilities(self) -> Capabilities:
        has = self._caps.__contains__
        return Capabilities(
            brand="Nikon",
            backend=self.name,
            can_capture=has(CAP_CAPTURE) or has(CAP_AF_CAPTURE),
            can_set_exposure=has(CAP_SHUTTER_SPEED),
            can_set_iso=has(CAP_SENSITIVITY),
            can_set_aperture=has(CAP_APERTURE),
            can_set_metering=has(CAP_METERING),
            can_set_comp=has(CAP_EXPOSURE_COMP),
            live_view=has(CAP_LIVE_VIEW_IMAGE) and has(CAP_LIVE_VIEW_STATUS),
            reads_battery=has(CAP_BATTERY),
            can_burst=has(CAP_SHOOTING_MODE) and has(CAP_CONTINUOUS_NUM),
            sdk_features=self.features(),
        )

    def device_info(self) -> DeviceInfo:
        battery = self.layer.get_number(CAP_BATTERY) if CAP_BATTERY in self._caps else None
        if battery is not None and not 0 <= battery <= 100:
            battery = None  # -1 means DC-IN
        # [Sourced] the module has no serial number or shutter count capability; both are read
        # from the NEF files the session downloads.
        return DeviceInfo(brand="Nikon", model=self._model, battery_percent=battery)

    def features(self) -> tuple[str, ...]:
        # Only what is bound: the out-of-focus result of AFCapture. AF point selection and focus
        # drive are not bound until a hardware log exists (V-03, V-23).
        return ("focus_check",)

    # ---- settings ----------------------------------------------------------------------------
    _ENUM_CAPS = (CAP_SENSITIVITY, CAP_SHUTTER_SPEED, CAP_APERTURE)

    def snapshot_settings(self) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        layer = self.layer
        for cap in self._ENUM_CAPS:
            if cap in self._caps:
                cur = layer.get_enum(cap)
                if cur is not None:
                    snap[f"e{cap:x}"] = cur.value
        for cap in (CAP_METERING, CAP_SHOOTING_MODE, CAP_CONTINUOUS_NUM):
            if cap in self._caps:
                if cap == CAP_SHOOTING_MODE:
                    cur = layer.get_enum(cap)
                    if cur is not None:
                        snap[f"e{cap:x}"] = cur.value
                    continue
                n = layer.get_number(cap)
                if n is not None:
                    snap[f"n{cap:x}"] = n
        if CAP_EXPOSURE_COMP in self._caps:
            rng = layer.get_range(CAP_EXPOSURE_COMP)
            if rng is not None:
                snap[f"r{CAP_EXPOSURE_COMP:x}"] = [rng.value, rng.index]
        return snap

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        self._live_off()
        self._refresh()
        failed: list[str] = []
        for key, value in snapshot.items():
            cap = int(key[1:], 16)
            if not self._settable(cap):
                continue  # read-only now (dial position): the camera keeps its own value
            if key[0] == "e":
                code = self.layer.set_enum(cap, int(value))
            elif key[0] == "n":
                code = self.layer.set_number(cap, int(value))
            else:
                code = self.layer.set_range(cap, float(value[0]), int(value[1]))
            if code != RESULT_OK:
                failed.append(f"0x{cap:X}")
        if failed:
            raise CommandFailed("restore failed for " + ", ".join(failed))

    def apply_settings(self, settings: CaptureSettings) -> None:
        self._live_off()
        self._refresh()
        if settings.af_point is not None:
            raise NotSupported("remote AF point selection is not bound for Nikon (V-03)")
        if settings.shutter_mode not in (None, "mechanical"):
            raise NotSupported("this body has no electronic shutter control")
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
            if settings.metering not in _METERING:
                raise NotSupported(f"metering {settings.metering!r} has no Nikon value")
            self._need_set(CAP_METERING, "metering")
            self._check(
                self.layer.set_number(CAP_METERING, _METERING[settings.metering]), "metering"
            )

    def _need_set(self, cap: int, label: str) -> None:
        if cap not in self._caps:
            raise NotSupported(f"{label} is not offered by this body")
        if not self._settable(cap):
            hint = ""
            if cap in (CAP_SHUTTER_SPEED, CAP_APERTURE) and self._exposure_mode() not in (
                None,
                EXPOSURE_MODE_MANUAL,
            ):
                hint = " (mode dial is not on M)"
            raise CommandFailed(f"{label} cannot be changed now{hint}")

    def _exposure_mode(self) -> int | None:
        if CAP_EXPOSURE_MODE not in self._caps:
            return None
        meta = self._caps[CAP_EXPOSURE_MODE]
        if meta.type == CAPTYPE_ENUM:
            e = self.layer.get_enum(CAP_EXPOSURE_MODE)
            if e is None or not e.values or e.kind != ARRAY_UNSIGNED:
                return None
            return int(e.values[e.value]) if e.value < len(e.values) else None
        return self.layer.get_number(CAP_EXPOSURE_MODE)

    def _set_by_text(
        self, cap: int, parse: Callable[[str], float | None], target: float, tol: float, label: str
    ) -> None:
        self._need_set(cap, label)
        offered = self.layer.get_enum(cap)
        if offered is None or offered.kind != ARRAY_PACKED_STRING:
            raise NotSupported(f"{label} values are not text on this body [Unverified]")
        values = [str(v) for v in offered.values]
        idx = pick_index(values, parse, target, tol)
        if idx is None:
            raise CommandFailed(f"{label} {target:g} is not offered by the camera")
        if idx == offered.value:
            return
        self._check(self.layer.set_enum(cap, idx), label)

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
            raise CommandFailed(f"{label}: {describe(code)}")

    # ---- capture -----------------------------------------------------------------------------
    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        assert self._save_dir is not None
        layer = self.layer
        self._live_off()
        if not layer.source_alive():
            raise Disconnected("camera was disconnected")
        burst = max(settings.burst, 1)
        restore_mode: int | None = None
        if burst > 1:
            restore_mode = self._enter_burst(burst)
        try:
            # AF before the shot only for AF chart frames; dark and flat frames are shot as set
            # (a body cap or a defocused flat target cannot be focused). [Inference]
            use_af = settings.kind == "chart" and CAP_AF_CAPTURE in self._caps
            cap = CAP_AF_CAPTURE if use_af else CAP_CAPTURE
            if cap not in self._caps:
                raise NotSupported("remote release is not offered by this body")
            code = layer.start(cap, timeout_s)
            if code == RESULT_OUT_OF_FOCUS:
                return CaptureOutcome(ok=False, focus_failed=True)  # tier 1 signal (R-01)
            if code not in (RESULT_OK, RESULT_PENDING):
                raise CommandFailed(f"capture: {describe(code)}")
            items = layer.wait_items(burst, timeout_s)
        finally:
            if restore_mode is not None:
                with contextlib.suppress(Exception):
                    layer.set_enum(CAP_SHOOTING_MODE, restore_mode)
        files: list[RemoteFile] = []
        for item in items:
            for d in layer.acquire(item, timeout_s):
                path = self._unique(d.name)
                path.write_bytes(d.data)
                files.append(RemoteFile(ref=str(path), name=path.name, size=len(d.data)))
        if len(items) < burst:
            return CaptureOutcome(ok=False, files=files, timed_out=True)
        return CaptureOutcome(ok=True, files=files)

    def _enter_burst(self, count: int) -> int | None:
        """CH with the shot count set by the host (MAID3Type0017 3.98, 3.99). Returns the index to
        put back, or None when the body keeps single frame (the shots then come one by one)."""
        layer = self.layer
        if not (self._settable(CAP_SHOOTING_MODE) and self._settable(CAP_CONTINUOUS_NUM)):
            raise NotSupported("continuous shooting cannot be set over USB now")
        mode = layer.get_enum(CAP_SHOOTING_MODE)
        if mode is None or SHOOTING_MODE_CH not in mode.values:
            raise NotSupported("continuous high-speed mode is not offered")
        self._check(layer.set_enum(CAP_SHOOTING_MODE, mode.values.index(SHOOTING_MODE_CH)), "CH")
        self._check(layer.set_number(CAP_CONTINUOUS_NUM, count), "shot count")
        return mode.value

    def _unique(self, name: str) -> Path:
        assert self._save_dir is not None
        path = self._save_dir / name
        n = 1
        while path.exists():
            path = self._save_dir / f"{Path(name).stem}_{n}{Path(name).suffix}"
            n += 1
        return path

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
    def _live_off(self) -> None:
        if self._live_on and self._layer is not None:
            with contextlib.suppress(Exception):
                self._layer.set_number(CAP_LIVE_VIEW_STATUS, 0)
            self._live_on = False

    def live_view_frame(self) -> Any | None:
        layer = self.layer
        if CAP_LIVE_VIEW_IMAGE not in self._caps or CAP_LIVE_VIEW_STATUS not in self._caps:
            return None
        if not self._live_on:
            if layer.set_number(CAP_LIVE_VIEW_STATUS, 1) != RESULT_OK:
                return None
            self._live_on = True
            self._refresh()
        deadline = time.monotonic() + LIVE_VIEW_START_S
        while True:
            raw = layer.live_view_image()
            jpeg = jpeg_payload(raw) if raw else None
            if jpeg:
                try:
                    return _decode_jpeg(jpeg)
                except (OSError, ValueError):
                    pass
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.1)


def _decode_jpeg(data: bytes) -> Any:
    import io

    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(data)) as im:
        return np.asarray(im.convert("L"), dtype=np.uint8)
