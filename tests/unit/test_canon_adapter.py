"""Canon adapter against a fake layer (no SDK, no camera), plus checks against a local SDK copy.

The checks against the maintainer's ``sdk/canon`` folder are skipped when it is absent, so CI
needs no vendor file (D-31).
"""

from __future__ import annotations

import ctypes
import os
import re
import struct
from pathlib import Path

import pytest

from camera_preflight.backends.protocol import (
    CaptureSettings,
    CommandFailed,
    Disconnected,
    NotSupported,
    RemoteFile,
)
from camera_preflight.backends.sdk import canon
from camera_preflight.backends.sdk.canon import (
    CMD_EXTEND_SHUTDOWN_TIMER,
    CMD_TAKE_PICTURE,
    ERR_DEVICE_BUSY,
    ERR_TAKE_PICTURE_AF_NG,
    P_AV,
    P_BATTERY,
    P_BODY_ID,
    P_COMP,
    P_FIRMWARE,
    P_ISO,
    P_LENS_NAME,
    P_METERING,
    P_PRODUCT_NAME,
    P_TV,
    STATE_SHUTDOWN,
    STATE_WILL_SOON_SHUTDOWN,
    CameraEntry,
    CanonAdapter,
    PropDesc,
    decode_av,
    decode_comp,
    decode_iso,
    decode_tv,
    describe_error,
    pick_comp,
    pick_value,
)
from camera_preflight.backends.sdk.loader import SdkLocation, find_sdk

SDK_ROOT = Path(__file__).resolve().parents[2] / "sdk" / "canon" / "v2132" / "Windows"
HEADERS = SDK_ROOT / "EDSDK" / "Header"
DLL_64 = SDK_ROOT / "EDSDK_64" / "EDSDK.dll"


class FakeLayer:
    def __init__(self, library: Path) -> None:
        self.on_download = None
        self.on_state = None
        self.u32: dict[int, int] = {P_BATTERY: 80, P_ISO: 0x48, P_TV: 0x68, P_AV: 0x30, P_COMP: 0}
        self.text = {
            P_PRODUCT_NAME: "Canon EOS 5D Mark III",
            P_BODY_ID: "0123456789",
            P_FIRMWARE: "1.3.5",
            P_LENS_NAME: "EF50mm f/1.8",
        }
        self.descs: dict[int, PropDesc] = {
            P_ISO: PropDesc([0x48, 0x50, 0x58, 0x60]),
            P_TV: PropDesc([0x58, 0x68, 0x70, 0x78]),
            P_AV: PropDesc([0x28, 0x30, 0x38]),
            P_COMP: PropDesc([0xFD, 0x00, 0x03, 0x08]),
            P_METERING: PropDesc([3, 5]),
        }
        self.commands: list[tuple[int, int]] = []
        self.set_calls: list[tuple[int, int]] = []
        self.folder: Path | None = None
        self.accept_sets = True
        self.command_results: list[int] = []  # popped one per command, then 0
        self.files_per_shot = 1
        self.cameras = [CameraEntry(0, "Canon EOS 5D Mark III")]
        self.connect_result = 0
        self.host_result = 0
        self.live_jpeg: bytes | None = None
        self.released = False
        self.disconnected = False

    def init(self) -> None: ...

    def release(self) -> None:
        self.released = True

    def enumerate(self) -> list[CameraEntry]:
        return self.cameras

    def connect(self, index: int) -> int:
        return self.connect_result

    def prepare_host_transfer(self, folder: Path) -> int:
        self.folder = folder
        return self.host_result

    def disconnect(self) -> None:
        self.disconnected = True

    def get_u32(self, prop: int) -> int | None:
        return self.u32.get(prop)

    def get_text(self, prop: int) -> str | None:
        return self.text.get(prop)

    def get_desc(self, prop: int) -> PropDesc | None:
        return self.descs.get(prop)

    def set_u32(self, prop: int, value: int) -> int:
        self.set_calls.append((prop, value))
        if self.accept_sets:
            self.u32[prop] = value
        return 0

    def send_command(self, command: int, param: int) -> int:
        self.commands.append((command, param))
        result = self.command_results.pop(0) if self.command_results else 0
        if result == 0 and command == CMD_TAKE_PICTURE and self.folder is not None:
            for i in range(self.files_per_shot):
                p = self.folder / f"IMG_{i:04d}.CR2"
                p.write_bytes(b"x" * 8)
                assert self.on_download is not None
                self.on_download(str(p))
        return result

    def pump(self) -> None: ...

    def live_view_jpeg(self) -> bytes | None:
        return self.live_jpeg


@pytest.fixture(autouse=True)
def _no_pauses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canon, "BUSY_RETRY_S", (0.0, 0.0, 0.0))
    monkeypatch.setattr(canon, "DOWNLOAD_QUIET_S", 0.0)
    monkeypatch.setattr(canon, "SETTLE_S", 0.2)


@pytest.fixture
def adapter(tmp_path: Path) -> CanonAdapter:
    lib = tmp_path / "EDSDK.dll"
    lib.write_bytes(b"")
    a = CanonAdapter(SdkLocation("canon", tmp_path, lib), layer_factory=FakeLayer)
    a.open()
    return a


def fake(a: CanonAdapter) -> FakeLayer:
    layer = a.layer
    assert isinstance(layer, FakeLayer)
    return layer


# ---- pure decoders ---------------------------------------------------------------------------------
def test_decoders():
    assert decode_av(0x30) == 5.6 and decode_av(0x99) is None
    assert decode_tv(0x68) == pytest.approx(1 / 60)
    assert decode_tv(0x38) == 1.0 and decode_tv(0x2B) == pytest.approx(3.2)
    assert decode_tv(0x0C) is None  # Bulb has no number
    assert decode_iso(0x48) == 100.0 and decode_iso(0x00) is None  # Auto
    assert decode_comp(0x00) == 0.0 and decode_comp(0x08) == 1.0 and decode_comp(0x18) == 3.0
    assert decode_comp(0x03) == pytest.approx(1 / 3) and decode_comp(0x04) == 0.5
    assert decode_comp(0xFD) == pytest.approx(-1 / 3) and decode_comp(0xF5) == pytest.approx(-4 / 3)
    assert decode_comp(0xFFFFFFFF) is None


def test_pick_value_and_comp():
    assert pick_value([0x68, 0x70], decode_tv, 1 / 125, 0.03) == 0x70
    assert pick_value([0x68], decode_tv, 0.5, 0.03) is None
    assert pick_comp([0xFD, 0x00, 0x03], 0.3) == 0x03
    assert pick_comp([0x00, 0x08], 0.5) is None


def test_every_table_code_decodes():
    assert all(decode_av(c) for c in canon._AV)
    assert all(decode_tv(c) for c in canon._TV)
    assert all(decode_iso(c) for c in canon._ISO)


def test_error_text():
    assert describe_error(ERR_DEVICE_BUSY) == "0x81 (device busy)"
    assert describe_error(0x1234) == "0x1234"


def test_struct_sizes_follow_the_header_layout():
    assert ctypes.sizeof(canon._DeviceInfo) == 520
    assert ctypes.sizeof(canon._PropertyDesc) == 524
    assert ctypes.sizeof(canon._Capacity) == 12
    assert ctypes.sizeof(canon._DirItemInfo) == (288 if struct.calcsize("P") == 8 else 284)


# ---- adapter ----------------------------------------------------------------------------------------
def test_open_prepares_host_transfer_and_close_cleans_up(adapter: CanonAdapter):
    layer = fake(adapter)
    assert layer.folder is not None and layer.folder.is_dir()
    assert str(layer.folder).isascii()
    folder = layer.folder
    adapter.close()
    assert layer.disconnected and layer.released and not folder.exists()


def test_open_fails_cleanly(tmp_path: Path):
    lib = tmp_path / "EDSDK.dll"
    lib.write_bytes(b"")
    holder: list[FakeLayer] = []

    def factory(path: Path) -> FakeLayer:
        layer = FakeLayer(path)
        layer.connect_result = ERR_DEVICE_BUSY
        holder.append(layer)
        return layer

    a = CanonAdapter(SdkLocation("canon", tmp_path, lib), layer_factory=factory)
    with pytest.raises(CommandFailed, match="device busy"):
        a.open()
    assert holder[0].released
    with pytest.raises(CommandFailed, match="session not open"):
        a.device_info()


def test_open_without_camera_times_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class Empty(FakeLayer):
        def __init__(self, library: Path) -> None:
            super().__init__(library)
            self.cameras = []

    clock = iter(range(0, 1000, 4))
    monkeypatch.setattr(canon.time, "monotonic", lambda: float(next(clock)))
    monkeypatch.setattr(canon.time, "sleep", lambda _s: None)
    lib = tmp_path / "EDSDK.dll"
    lib.write_bytes(b"")
    a = CanonAdapter(SdkLocation("canon", tmp_path, lib), layer_factory=Empty)
    with pytest.raises(CommandFailed, match="no Canon camera"):
        a.open()


def test_device_info_and_capabilities(adapter: CanonAdapter):
    info = adapter.device_info()
    assert (info.brand, info.model, info.serial) == ("Canon", "Canon EOS 5D Mark III", "0123456789")
    assert (info.firmware, info.lens, info.battery_percent) == ("1.3.5", "EF50mm f/1.8", 80)
    assert info.shutter_count is None  # not an EDSDK property
    caps = adapter.capabilities()
    assert caps.can_capture and caps.can_set_exposure and caps.can_set_iso
    assert caps.can_set_aperture and caps.can_set_comp and caps.can_set_metering
    assert not caps.can_set_shutter_mode and not caps.reads_shutter_count
    assert caps.sdk_features == ("live_view",)


def test_battery_on_ac_power_is_not_a_percentage(adapter: CanonAdapter):
    fake(adapter).u32[P_BATTERY] = 0xFFFFFFFF
    assert adapter.device_info().battery_percent is None


def test_capabilities_follow_what_the_body_offers(adapter: CanonAdapter):
    fake(adapter).descs[P_TV] = PropDesc([])  # mode dial on a setting that locks exposure time
    fake(adapter).descs[P_ISO] = PropDesc([0x48], access=0)  # read only
    caps = adapter.capabilities()
    assert not caps.can_set_exposure and not caps.can_set_iso


def test_apply_settings_picks_offered_values(adapter: CanonAdapter):
    adapter.apply_settings(
        CaptureSettings(
            iso=400,
            exposure_s=1 / 125,
            aperture=5.6,
            exposure_comp_ev=1 / 3,
            metering="centre_weighted",
        )
    )
    assert fake(adapter).set_calls == [
        (P_ISO, 0x58),
        (P_TV, 0x70),
        (P_AV, 0x30),
        (P_COMP, 0x03),
        (P_METERING, 5),
    ]


@pytest.mark.parametrize(
    "settings",
    [
        CaptureSettings(af_point="center"),
        CaptureSettings(burst=3),
        CaptureSettings(shutter_mode="electronic"),
        CaptureSettings(focus_mode="mf"),
        CaptureSettings(metering="unknown"),
    ],
)
def test_unbound_settings_are_refused(adapter: CanonAdapter, settings: CaptureSettings):
    with pytest.raises(NotSupported):
        adapter.apply_settings(settings)
    assert fake(adapter).set_calls == []


def test_value_not_offered_is_a_failure_not_a_guess(adapter: CanonAdapter):
    with pytest.raises(CommandFailed, match="not offered"):
        adapter.apply_settings(CaptureSettings(iso=3200))
    with pytest.raises(CommandFailed, match="not offered"):
        adapter.apply_settings(CaptureSettings(metering="spot"))
    fake(adapter).descs[P_AV] = PropDesc([])
    with pytest.raises(CommandFailed, match="mode dial"):
        adapter.apply_settings(CaptureSettings(aperture=5.6))
    del fake(adapter).descs[P_AV]
    with pytest.raises(NotSupported):
        adapter.apply_settings(CaptureSettings(aperture=5.6))


def test_write_that_the_body_ignores_is_reported(adapter: CanonAdapter):
    fake(adapter).accept_sets = False
    with pytest.raises(CommandFailed, match="did not take"):
        adapter.apply_settings(CaptureSettings(iso=200))


def test_snapshot_and_restore(adapter: CanonAdapter):
    snap = adapter.snapshot_settings()
    assert snap[f"{P_ISO:x}"] == 0x48
    adapter.apply_settings(CaptureSettings(iso=800))
    assert fake(adapter).u32[P_ISO] == 0x60
    adapter.restore_settings(snap)
    assert fake(adapter).u32[P_ISO] == 0x48


def test_capture_collects_and_downloads(adapter: CanonAdapter, tmp_path: Path):
    out = adapter.capture(CaptureSettings(), timeout_s=2.0)
    assert out.ok and not out.timed_out and not out.focus_failed
    assert [f.name for f in out.files] == ["IMG_0000.CR2"] and out.files[0].size == 8
    dest = adapter.download(out.files[0], tmp_path / "out")
    assert dest.read_bytes() == b"x" * 8
    with pytest.raises(CommandFailed, match="not one captured"):
        adapter.download(RemoteFile(ref=str(tmp_path / "other.cr2"), name="other.cr2"), tmp_path)


def test_capture_reports_autofocus_failure(adapter: CanonAdapter):
    fake(adapter).command_results = [ERR_TAKE_PICTURE_AF_NG]
    out = adapter.capture(CaptureSettings(), timeout_s=1.0)
    assert not out.ok and out.focus_failed and out.files == []


def test_capture_retries_when_the_body_is_busy(adapter: CanonAdapter):
    layer = fake(adapter)
    layer.command_results = [ERR_DEVICE_BUSY, ERR_DEVICE_BUSY]
    assert adapter.capture(CaptureSettings(), timeout_s=1.0).ok
    assert [c for c, _ in layer.commands].count(CMD_TAKE_PICTURE) == 3


def test_capture_gives_up_on_a_body_that_stays_busy(adapter: CanonAdapter):
    fake(adapter).command_results = [ERR_DEVICE_BUSY] * 4
    with pytest.raises(CommandFailed, match="device busy"):
        adapter.capture(CaptureSettings(), timeout_s=1.0)


def test_capture_without_a_file_times_out(adapter: CanonAdapter):
    fake(adapter).files_per_shot = 0
    out = adapter.capture(CaptureSettings(), timeout_s=0.1)
    assert not out.ok and out.timed_out


def test_capture_refuses_burst(adapter: CanonAdapter):
    with pytest.raises(NotSupported):
        adapter.capture(CaptureSettings(burst=2), timeout_s=1.0)


def test_unplugged_body_raises_disconnected(adapter: CanonAdapter):
    fake(adapter).command_results = [0xC1]
    with pytest.raises(Disconnected):
        adapter.capture(CaptureSettings(), timeout_s=1.0)
    with pytest.raises(Disconnected):
        adapter.device_info()


def test_shutdown_event_marks_the_session_lost(adapter: CanonAdapter):
    layer = fake(adapter)
    assert layer.on_state is not None
    layer.on_state(STATE_SHUTDOWN, 0)
    with pytest.raises(Disconnected):
        adapter.capabilities()


def test_warning_before_auto_power_off_extends_the_timer(adapter: CanonAdapter):
    layer = fake(adapter)
    assert layer.on_state is not None
    layer.on_state(STATE_WILL_SOON_SHUTDOWN, 0)
    assert layer.commands == []  # nothing is sent from inside the callback
    adapter.capture(CaptureSettings(), timeout_s=1.0)
    assert (CMD_EXTEND_SHUTDOWN_TIMER, 0) in layer.commands


def test_live_view_frame(adapter: CanonAdapter):
    assert adapter.live_view_frame() is None
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (6, 4), (200, 100, 50)).save(buf, "JPEG")
    fake(adapter).live_jpeg = buf.getvalue()
    frame = adapter.live_view_frame()
    assert frame.shape == (4, 6)


# ---- discovery picks the build for this CPU ----------------------------------------------------------
def _pe(path: Path, machine: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    head = bytearray(64)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 64)
    path.write_bytes(bytes(head) + b"PE\0\0" + struct.pack("<H", machine) + b"\0" * 32)


def test_find_sdk_skips_the_other_cpu_build(tmp_path: Path):
    other, mine = (0x14C, 0x8664) if struct.calcsize("P") == 8 else (0x8664, 0x14C)
    _pe(tmp_path / "EDSDK" / "Dll" / "EDSDK.dll", other)
    _pe(tmp_path / "EDSDK_64" / "EDSDK.dll", mine)
    found = find_sdk("canon", tmp_path)
    assert found is not None and found.library.parent.name == "EDSDK_64"


def test_find_sdk_falls_back_to_what_exists(tmp_path: Path):
    other = 0x14C if struct.calcsize("P") == 8 else 0x8664
    _pe(tmp_path / "EDSDK.dll", other)
    found = find_sdk("canon", tmp_path)
    assert found is not None and found.library.name == "EDSDK.dll"
    assert find_sdk("canon", tmp_path / "missing") is None


# ---- against the maintainer's SDK copy (skipped when absent) -----------------------------------------
@pytest.mark.skipif(not (HEADERS / "EDSDKTypes.h").exists(), reason="no local EDSDK headers")
def test_constants_match_the_sdk_headers():
    text = (HEADERS / "EDSDKTypes.h").read_text(encoding="latin-1") + (
        HEADERS / "EDSDKErrors.h"
    ).read_text(encoding="latin-1")

    def define(name: str) -> int:
        m = re.search(rf"#define\s+{name}\s+(0x[0-9a-fA-F]+)", text)
        assert m, name
        return int(m.group(1), 16)

    pairs = {
        "kEdsPropID_ProductName": canon.P_PRODUCT_NAME,
        "kEdsPropID_BodyIDEx": canon.P_BODY_ID,
        "kEdsPropID_FirmwareVersion": canon.P_FIRMWARE,
        "kEdsPropID_BatteryLevel": canon.P_BATTERY,
        "kEdsPropID_SaveTo": canon.P_SAVE_TO,
        "kEdsPropID_ISOSpeed": canon.P_ISO,
        "kEdsPropID_MeteringMode": canon.P_METERING,
        "kEdsPropID_AFMode": canon.P_AF_MODE,
        "kEdsPropID_Av": canon.P_AV,
        "kEdsPropID_Tv": canon.P_TV,
        "kEdsPropID_ExposureCompensation": canon.P_COMP,
        "kEdsPropID_LensName": canon.P_LENS_NAME,
        "kEdsPropID_Evf_OutputDevice": canon.P_EVF_OUTPUT,
        "kEdsPropID_Evf_Mode": canon.P_EVF_MODE,
        "kEdsCameraCommand_TakePicture": canon.CMD_TAKE_PICTURE,
        "kEdsCameraCommand_ExtendShutDownTimer": canon.CMD_EXTEND_SHUTDOWN_TIMER,
        "kEdsCameraStatusCommand_UILock": canon.STATUS_UI_LOCK,
        "kEdsCameraStatusCommand_UIUnLock": canon.STATUS_UI_UNLOCK,
        "kEdsObjectEvent_All": canon.EVENT_OBJECT_ALL,
        "kEdsObjectEvent_DirItemRequestTransfer": canon.EVENT_REQUEST_TRANSFER,
        "kEdsStateEvent_All": canon.EVENT_STATE_ALL,
        "kEdsStateEvent_Shutdown": canon.STATE_SHUTDOWN,
        "kEdsStateEvent_WillSoonShutDown": canon.STATE_WILL_SOON_SHUTDOWN,
        "EDS_ERR_DEVICE_NOT_FOUND": canon.ERR_DEVICE_NOT_FOUND,
        "EDS_ERR_DEVICE_BUSY": canon.ERR_DEVICE_BUSY,
        "EDS_ERR_COMM_DISCONNECTED": canon.ERR_COMM_DISCONNECTED,
        "EDS_ERR_SESSION_NOT_OPEN": canon.ERR_SESSION_NOT_OPEN,
        "EDS_ERR_TAKE_PICTURE_AF_NG": canon.ERR_TAKE_PICTURE_AF_NG,
        "EDS_ERR_OBJECT_NOTREADY": canon.ERR_OBJECT_NOTREADY,
    }
    for name, ours in pairs.items():
        assert define(name) == ours, name
    assert re.search(r"kEdsSaveTo_Host\s*=\s*2", text)
    assert re.search(r"kEdsEvfOutputDevice_PC\s*=\s*2", text)
    assert re.search(r"kEdsFileCreateDisposition_CreateAlways\s*,", text)  # second member: 1
    assert re.search(r"kEdsAccess_ReadWrite\s*,", text)  # third member: 2


@pytest.mark.skipif(
    os.name != "nt" or struct.calcsize("P") != 8 or not DLL_64.exists(),
    reason="needs Windows, 64-bit Python and the local EDSDK 2.13 copy",
)
def test_real_library_loads_and_sees_no_camera():
    layer = canon.EdsLayer(DLL_64)  # binds every export the adapter uses
    layer.init()
    try:
        assert layer.enumerate() == []
        layer.pump()  # EdsGetEvent with nothing to deliver
    finally:
        layer.release()
