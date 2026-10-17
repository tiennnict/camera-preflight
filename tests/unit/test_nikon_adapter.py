"""Nikon adapter against a fake Control Service Layer (no SDK, no camera)."""

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
from camera_preflight.backends.sdk import nikon
from camera_preflight.backends.sdk.loader import SdkLocation, find_sdk
from camera_preflight.backends.sdk.nikon import (
    ARRAY_PACKED_STRING,
    ARRAY_UNSIGNED,
    CAP_APERTURE,
    CAP_BATTERY,
    CAP_EXPOSURE_COMP,
    CAP_METERING,
    CAP_SENSITIVITY,
    CAP_SHUTTER_SPEED,
    CAP_SILENT_MODE,
    RESULT_OUT_OF_FOCUS,
    DeviceEntry,
    EnumData,
    NikonAdapter,
    RangeData,
    parse_aperture,
    parse_exposure,
    parse_iso,
    pick_index,
    split_packed,
)

SET = 0x0004
GET = 0x0002


class FakeLayer:
    def __init__(self, library: Path) -> None:
        self.library = library
        self.on_saved = None
        self.on_live_frame = None
        self.enums = {
            CAP_SENSITIVITY: EnumData(ARRAY_PACKED_STRING, ["100", "200", "400", "800"], 0),
            CAP_SHUTTER_SPEED: EnumData(
                ARRAY_PACKED_STRING, ["1/1000", "1/250", "1/60", '1"', "Bulb"], 1
            ),
            CAP_APERTURE: EnumData(ARRAY_PACKED_STRING, ["f/2.8", "f/5.6", "f/8"], 0),
            CAP_METERING: EnumData(ARRAY_UNSIGNED, [0, 1, 2], 0),
            CAP_SILENT_MODE: EnumData(ARRAY_UNSIGNED, [0, 1], 0),
        }
        self.range = RangeData(0.0, 6, -3.0, 3.0, 13)
        self.set_calls: list[tuple[int, int]] = []
        self.range_calls: list[tuple[float, int]] = []
        self.shoot_result = 0
        self.files_per_shot = 1
        self.shutdown_called = False

    def initialize(self) -> None: ...
    def shutdown(self) -> None:
        self.shutdown_called = True

    def devices(self) -> list[DeviceEntry]:
        return [DeviceEntry(7, "Nikon Z 6_2", True, "1.40")]

    def connect(self, device_id: int) -> dict[int, int]:
        ops = {cap: GET | SET for cap in (*self.enums, CAP_EXPOSURE_COMP)}
        ops[CAP_BATTERY] = GET
        return ops

    def disconnect(self) -> None: ...

    def get_enum(self, cap: int, supported: bool) -> EnumData | None:
        return self.enums.get(cap)

    def set_enum(self, cap: int, value: int) -> int:
        self.set_calls.append((cap, value))
        return 0

    def get_range(self, cap: int) -> RangeData | None:
        return self.range

    def set_range(self, cap: int, value: float, index: int) -> int:
        self.range_calls.append((value, index))
        return 0

    def get_unsigned(self, cap: int) -> int | None:
        return 87

    def start_shooting(self, kind: int, count: int, save_dir: Path) -> int:
        if self.shoot_result:
            return self.shoot_result
        for i in range(count * self.files_per_shot):
            p = save_dir / f"DSC_{i:04d}.NEF"
            p.write_bytes(b"x" * 10)
            assert self.on_saved is not None
            self.on_saved(str(p))
        return 0

    def start_live_view(self) -> int:
        return 0

    def stop_live_view(self) -> int:
        return 0


@pytest.fixture
def adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NikonAdapter:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    lib = tmp_path / "ControlServiceLayer.dll"
    lib.write_bytes(b"")
    a = NikonAdapter(SdkLocation("nikon", tmp_path, lib), layer_factory=FakeLayer)
    a.open()
    return a


def test_parsers():
    assert split_packed(b"100\x00200\x00") == ["100", "200"]
    assert parse_exposure("1/250") == pytest.approx(0.004)
    assert parse_exposure('2"') == 2.0
    assert parse_exposure("Bulb") is None
    assert parse_aperture("f/5.6") == 5.6
    assert parse_iso("ISO 800") == 800.0
    assert parse_iso("Hi 1.0") is None
    assert pick_index(["1/60", "1/250"], parse_exposure, 0.004, 0.03) == 1
    assert pick_index(["1/60"], parse_exposure, 0.5, 0.03) is None


def test_struct_sizes_follow_two_byte_packing():
    assert ctypes.sizeof(nikon._Enum) == 26
    assert ctypes.sizeof(nikon._Range) == 44
    assert ctypes.sizeof(nikon._DeviceInfo) == 138
    # 22 bytes before the path, 1024 wide characters, then the 8 byte reference pointer
    assert ctypes.sizeof(nikon._Shooting) == 22 + 1024 * ctypes.sizeof(ctypes.c_wchar) + 8
    assert ctypes.sizeof(nikon._LiveView) == 900


def test_find_sdk_in_downloaded_layout(tmp_path: Path):
    d = tmp_path / "Z-210" / "Module" / "Win" / "BinaryFile"
    d.mkdir(parents=True)
    (d / "ControlServiceLayer.dll").write_bytes(b"")
    loc = find_sdk("nikon", tmp_path)
    assert loc and loc.library.name == "ControlServiceLayer.dll"


def test_info_and_capabilities(adapter: NikonAdapter):
    info = adapter.device_info()
    assert info.brand == "Nikon" and info.model == "Nikon Z 6_2" and info.battery_percent == 87
    caps = adapter.capabilities()
    assert caps.can_capture and caps.can_set_iso and caps.can_set_shutter_mode


def test_settings_are_matched_from_offered_values(adapter: NikonAdapter):
    layer = adapter.layer
    adapter.apply_settings(
        CaptureSettings(
            iso=400,
            exposure_s=1 / 60,
            aperture=5.6,
            metering="spot",
            exposure_comp_ev=1.0,
            shutter_mode="electronic",
        )
    )
    assert isinstance(layer, FakeLayer)
    assert (CAP_SENSITIVITY, 2) in layer.set_calls
    assert (CAP_SHUTTER_SPEED, 2) in layer.set_calls
    assert (CAP_APERTURE, 1) in layer.set_calls
    assert (CAP_METERING, 2) in layer.set_calls
    assert (CAP_SILENT_MODE, 1) in layer.set_calls
    assert layer.range_calls == [(1.0, 8)]


def test_unoffered_value_and_af_point_are_refused(adapter: NikonAdapter):
    with pytest.raises(CommandFailed):
        adapter.apply_settings(CaptureSettings(iso=3200))
    with pytest.raises(NotSupported):
        adapter.apply_settings(CaptureSettings(af_point="left"))
    with pytest.raises(CommandFailed):
        adapter.apply_settings(CaptureSettings(exposure_comp_ev=5.0))


def test_snapshot_and_restore(adapter: NikonAdapter):
    snap = adapter.snapshot_settings()
    adapter.restore_settings(snap)
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    assert (CAP_SENSITIVITY, 0) in layer.set_calls and layer.range_calls == [(0.0, 6)]


def test_capture_download_and_burst(adapter: NikonAdapter, tmp_path: Path):
    out = adapter.capture(CaptureSettings(burst=3), timeout_s=3.0)
    assert out.ok and len(out.files) == 3
    got = adapter.download(out.files[0], tmp_path / "dl")
    assert got.read_bytes() == b"x" * 10
    with pytest.raises(CommandFailed):
        adapter.download(RemoteFile(ref=str(tmp_path / "other.NEF"), name="other.NEF"), tmp_path)


def test_out_of_focus_is_the_tier_one_signal(adapter: NikonAdapter):
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    layer.shoot_result = RESULT_OUT_OF_FOCUS
    out = adapter.capture(CaptureSettings(), timeout_s=1.0)
    assert not out.ok and out.focus_failed
    layer.shoot_result = 152
    with pytest.raises(CommandFailed):
        adapter.capture(CaptureSettings(), timeout_s=1.0)


def test_capture_timeout_reports_partial(adapter: NikonAdapter):
    layer = adapter.layer
    assert isinstance(layer, FakeLayer)
    layer.files_per_shot = 0
    out = adapter.capture(CaptureSettings(), timeout_s=0.3)
    assert not out.ok and out.timed_out


def test_close_shuts_layer_down(adapter: NikonAdapter):
    layer = adapter.layer
    adapter.close()
    assert isinstance(layer, FakeLayer) and layer.shutdown_called
