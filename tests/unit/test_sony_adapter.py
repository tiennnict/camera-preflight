"""Sony adapter against a fake layer (no SDK, no camera)."""

from __future__ import annotations

import ctypes
from pathlib import Path

import pytest

from camera_preflight.backends.protocol import (
    CaptureSettings,
    CommandFailed,
    NotSupported,
    RemoteFile,
)
from camera_preflight.backends.sdk import sony
from camera_preflight.backends.sdk.loader import SdkLocation, find_sdk
from camera_preflight.backends.sdk.sony import (
    P_BATTERY_REMAIN,
    P_BODY_SERIAL,
    P_EXPOSURE_BIAS,
    P_FNUMBER,
    P_FOCUS_INDICATION,
    P_FOCUS_MODE,
    P_ISO,
    P_METERING,
    P_MODEL_NAME,
    P_S1,
    P_SHUTTER_SPEED,
    P_SHUTTER_TYPE,
    CameraEntry,
    PropData,
    SonyAdapter,
    decode_fnumber,
    decode_iso,
    decode_shutter,
    pick_value,
    to_signed16,
)

ENABLED = 1


def _shutter(num: int, den: int) -> int:
    return (num << 16) | den


class FakeLayer:
    def __init__(self, library: Path) -> None:
        self.on_download = None
        self.on_connected = None
        self.on_disconnected = None
        self.on_error = None
        self.props: dict[int, PropData] = {
            P_ISO: PropData(P_ISO, 0x3, ENABLED, 100, [100, 200, 400, 0x00FFFFFF]),
            P_SHUTTER_SPEED: PropData(
                P_SHUTTER_SPEED,
                0x3,
                ENABLED,
                _shutter(1, 250),
                [0, _shutter(1, 1000), _shutter(1, 250), _shutter(1, 60), _shutter(2, 1)],
            ),
            P_FNUMBER: PropData(P_FNUMBER, 0x2002, ENABLED, 280, [280, 560, 800]),
            P_EXPOSURE_BIAS: PropData(
                P_EXPOSURE_BIAS, 0x2002, ENABLED, 0, [0xFC18, 0, 1000]
            ),  # -1.0, 0, +1.0 EV
            P_METERING: PropData(P_METERING, 0x2002, ENABLED, 5, [1, 2, 4, 5]),
            P_SHUTTER_TYPE: PropData(P_SHUTTER_TYPE, 0x2001, ENABLED, 1, [1, 2, 3]),
            P_FOCUS_MODE: PropData(P_FOCUS_MODE, 0x2002, ENABLED, 2, [1, 2, 3]),
            P_FOCUS_INDICATION: PropData(P_FOCUS_INDICATION, 0x3, 2, 0x102),
            P_BATTERY_REMAIN: PropData(P_BATTERY_REMAIN, 0x1, 2, 64),
            P_MODEL_NAME: PropData(P_MODEL_NAME, 0xFFFF, 2, 0, text="ILCE-7M4"),
            P_BODY_SERIAL: PropData(P_BODY_SERIAL, 0xFFFF, 2, 0, text="1234567"),
        }
        self.commands: list[tuple[int, int]] = []
        self.set_calls: list[tuple[int, int]] = []
        self.save_dir: Path | None = None
        self.accept_sets = True
        self.release_result = 0
        self.files_per_shot = 1

    def init(self) -> None: ...
    def release(self) -> None: ...

    def enumerate(self, timeout_s: int) -> list[CameraEntry]:
        return [CameraEntry(0, "ILCE-7M4", "ILCE-7M4")]

    def connect(self, index: int) -> int:
        assert self.on_connected is not None
        self.on_connected()
        return 0

    def disconnect(self) -> None: ...

    def get_property(self, code: int) -> PropData | None:
        return self.props.get(code)

    def set_property(self, code: int, value: int, vtype: int) -> int:
        self.set_calls.append((code, value))
        if code == P_S1:
            return 0
        if self.accept_sets and code in self.props:
            self.props[code].current = value
        return 0

    def send_command(self, command: int, param: int) -> int:
        self.commands.append((command, param))
        if self.release_result:
            return self.release_result
        if param == 0 and self.save_dir is not None:  # shutter up: the camera sends the file
            for i in range(self.files_per_shot):
                p = self.save_dir / f"DSC{i:05d}.ARW"
                p.write_bytes(b"y" * 8)
                assert self.on_download is not None
                self.on_download(str(p))
        return 0

    def set_save_info(self, folder: Path, prefix: str) -> int:
        self.save_dir = folder
        return 0

    def live_view_jpeg(self) -> bytes | None:
        return None


@pytest.fixture
def adapter(tmp_path: Path) -> SonyAdapter:
    lib = tmp_path / "Cr_Core.dll"
    lib.write_bytes(b"")
    a = SonyAdapter(SdkLocation("sony", tmp_path, lib), layer_factory=FakeLayer)
    a.open()
    return a


def test_decoders():
    assert decode_shutter(_shutter(1, 250)) == pytest.approx(0.004)
    assert decode_shutter(0) is None
    assert decode_fnumber(560) == 5.6 and decode_fnumber(0xFFFE) is None
    assert decode_iso(400) == 400.0
    assert decode_iso(0x00FFFFFF) is None
    assert decode_iso(0x01000064) is None  # multi frame NR mode is not plain ISO
    assert to_signed16(0xFC18) == -1000
    assert pick_value([_shutter(1, 60)], decode_shutter, 0.5, 0.03) is None


def test_struct_sizes_follow_the_header_layout():
    assert ctypes.sizeof(sony._Prop) == 64
    assert ctypes.sizeof(sony._ImageInfo) == 12
    assert ctypes.sizeof(sony._ImageBlock) == 24


def test_find_sdk_in_downloaded_layout(tmp_path: Path):
    d = tmp_path / "Win64" / "SimpleCli" / "external" / "crsdk"
    d.mkdir(parents=True)
    (d / "Cr_Core.dll").write_bytes(b"")
    loc = find_sdk("sony", tmp_path)
    assert loc and loc.library.name == "Cr_Core.dll"


def test_info_and_capabilities(adapter: SonyAdapter):
    info = adapter.device_info()
    assert info.brand == "Sony" and info.model == "ILCE-7M4" and info.serial == "1234567"
    assert info.battery_percent == 64
    caps = adapter.capabilities()
    assert caps.can_capture and caps.can_set_iso and caps.can_set_shutter_mode


def test_settings_matched_from_offered_values(adapter: SonyAdapter):
    adapter.apply_settings(
        CaptureSettings(
            iso=200,
            exposure_s=1 / 60,
            aperture=5.6,
            metering="spot",
            exposure_comp_ev=1.0,
            shutter_mode="electronic",
            focus_mode="MF",
        )
    )
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    assert layer.props[P_ISO].current == 200
    assert layer.props[P_SHUTTER_SPEED].current == _shutter(1, 60)
    assert layer.props[P_FNUMBER].current == 560
    assert layer.props[P_METERING].current == 4
    assert layer.props[P_EXPOSURE_BIAS].current == 1000
    assert layer.props[P_SHUTTER_TYPE].current == 3
    assert layer.props[P_FOCUS_MODE].current == 1


def test_refusals(adapter: SonyAdapter):
    with pytest.raises(CommandFailed):
        adapter.apply_settings(CaptureSettings(iso=3200))
    with pytest.raises(CommandFailed):
        adapter.apply_settings(CaptureSettings(exposure_comp_ev=2.0))
    with pytest.raises(NotSupported):
        adapter.apply_settings(CaptureSettings(af_point="left"))
    with pytest.raises(NotSupported):
        adapter.apply_settings(CaptureSettings(burst=5))


def test_camera_that_ignores_a_set_is_reported(adapter: SonyAdapter, monkeypatch):
    monkeypatch.setattr(sony, "SETTLE_S", 0.2)
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    layer.accept_sets = False
    with pytest.raises(CommandFailed):
        adapter.apply_settings(CaptureSettings(iso=400))


def test_snapshot_and_restore(adapter: SonyAdapter):
    snap = adapter.snapshot_settings()
    adapter.apply_settings(CaptureSettings(iso=400))
    adapter.restore_settings(snap)
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    assert layer.props[P_ISO].current == 100


def test_capture_and_download(adapter: SonyAdapter, tmp_path: Path):
    out = adapter.capture(CaptureSettings(), timeout_s=3.0)
    assert out.ok and len(out.files) == 1
    got = adapter.download(out.files[0], tmp_path / "dl")
    assert got.read_bytes() == b"y" * 8
    with pytest.raises(CommandFailed):
        adapter.download(RemoteFile(ref=str(tmp_path / "x.ARW"), name="x.ARW"), tmp_path)


def test_not_focused_is_the_tier_one_signal(adapter: SonyAdapter):
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    layer.props[P_FOCUS_INDICATION].current = 0x202
    out = adapter.capture(CaptureSettings(), timeout_s=1.0)
    assert not out.ok and out.focus_failed and not layer.commands
    assert layer.set_calls[0][0] == P_S1 and layer.set_calls[-1] == (P_S1, 1)  # unlocked again


def test_manual_focus_skips_the_half_press(adapter: SonyAdapter):
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    layer.props[P_FOCUS_MODE].current = 1
    adapter.capture(CaptureSettings(), timeout_s=1.0)
    assert all(code != P_S1 for code, _ in layer.set_calls)


def test_no_download_is_a_timeout(adapter: SonyAdapter):
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    layer.props[P_FOCUS_MODE].current = 1
    layer.files_per_shot = 0
    out = adapter.capture(CaptureSettings(), timeout_s=0.3)
    assert not out.ok and out.timed_out
    layer.release_result = 0x8000
    with pytest.raises(CommandFailed):
        adapter.capture(CaptureSettings(), timeout_s=0.3)
