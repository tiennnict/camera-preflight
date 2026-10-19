"""Nikon MAID3 module adapter (D7200 and other D-SLR bodies) against a fake module, plus a load
test of the real Type0017 module when the maintainer's local SDK copy is present."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from camera_preflight.backends.protocol import (
    CaptureSettings,
    CommandFailed,
    Disconnected,
    NotSupported,
    RemoteFile,
)
from camera_preflight.backends.sdk import loader
from camera_preflight.backends.sdk.loader import SdkLocation, find_all_sdk, open_sdk_backend
from camera_preflight.backends.sdk.nikon import (
    ARRAY_PACKED_STRING,
    ARRAY_UNSIGNED,
    EnumData,
    RangeData,
)
from camera_preflight.backends.sdk.nikon_module import (
    CAP_AF_CAPTURE,
    CAP_APERTURE,
    CAP_BATTERY,
    CAP_CAPTURE,
    CAP_COMPRESSION,
    CAP_CONTINUOUS_NUM,
    CAP_EXPOSURE_COMP,
    CAP_EXPOSURE_MODE,
    CAP_LIVE_VIEW_IMAGE,
    CAP_LIVE_VIEW_STATUS,
    CAP_METERING,
    CAP_NAME,
    CAP_NOISE_REDUCTION,
    CAP_SAVE_MEDIA,
    CAP_SENSITIVITY,
    CAP_SHOOTING_MODE,
    CAP_SHUTTER_SPEED,
    CAPTYPE_BOOLEAN,
    CAPTYPE_ENUM,
    CAPTYPE_INTEGER,
    CAPTYPE_PROCESS,
    CAPTYPE_RANGE,
    CAPTYPE_UNSIGNED,
    OP_GET,
    OP_GET_ARRAY,
    OP_SET,
    OP_START,
    RESULT_OUT_OF_FOCUS,
    CapMeta,
    Delivered,
    NikonModuleAdapter,
    find_text,
    jpeg_payload,
)

RW = OP_GET | OP_SET | OP_GET_ARRAY


class FakeModule:
    """Behaves like Type0017 as the documents describe it; values are D7200-like strings."""

    def __init__(self, library: Path) -> None:
        self.library = library
        self.camera_present = True
        self.alive = True
        self.closed = False
        self.manual = True  # mode dial on M
        self.meta = {
            CAP_NAME: CapMeta(8, OP_GET),
            CAP_BATTERY: CapMeta(CAPTYPE_INTEGER, OP_GET),
            CAP_SAVE_MEDIA: CapMeta(CAPTYPE_UNSIGNED, OP_GET | OP_SET),
            CAP_NOISE_REDUCTION: CapMeta(CAPTYPE_BOOLEAN, OP_GET | OP_SET),
            CAP_COMPRESSION: CapMeta(CAPTYPE_ENUM, RW),
            CAP_SENSITIVITY: CapMeta(CAPTYPE_ENUM, RW),
            CAP_SHUTTER_SPEED: CapMeta(CAPTYPE_ENUM, RW),
            CAP_APERTURE: CapMeta(CAPTYPE_ENUM, RW),
            CAP_EXPOSURE_COMP: CapMeta(CAPTYPE_RANGE, OP_GET | OP_SET),
            CAP_METERING: CapMeta(CAPTYPE_UNSIGNED, OP_GET | OP_SET),
            CAP_EXPOSURE_MODE: CapMeta(CAPTYPE_UNSIGNED, OP_GET),
            CAP_SHOOTING_MODE: CapMeta(CAPTYPE_ENUM, RW),
            CAP_CONTINUOUS_NUM: CapMeta(CAPTYPE_UNSIGNED, OP_GET | OP_SET),
            CAP_CAPTURE: CapMeta(CAPTYPE_PROCESS, OP_START),
            CAP_AF_CAPTURE: CapMeta(CAPTYPE_PROCESS, OP_START),
            CAP_LIVE_VIEW_STATUS: CapMeta(CAPTYPE_UNSIGNED, OP_GET | OP_SET),
            CAP_LIVE_VIEW_IMAGE: CapMeta(11, OP_GET | OP_GET_ARRAY),
        }
        self.numbers = {
            CAP_BATTERY: 80,
            CAP_SAVE_MEDIA: 0,
            CAP_NOISE_REDUCTION: 1,
            CAP_METERING: 0,
            CAP_EXPOSURE_MODE: 3,
            CAP_CONTINUOUS_NUM: 1,
            CAP_LIVE_VIEW_STATUS: 0,
        }
        self.enums = {
            CAP_COMPRESSION: EnumData(
                ARRAY_PACKED_STRING, ["JPEG Basic", "JPEG Normal", "JPEG Fine", "RAW"], 2
            ),
            CAP_SENSITIVITY: EnumData(ARRAY_PACKED_STRING, ["100", "200", "1600", "6400"], 0),
            CAP_SHUTTER_SPEED: EnumData(
                ARRAY_PACKED_STRING, ["30", "1", "1/100", "1/125", "1/250", "Bulb"], 4
            ),
            CAP_APERTURE: EnumData(ARRAY_PACKED_STRING, ["3.5", "5.6", "8", "16"], 0),
            CAP_SHOOTING_MODE: EnumData(ARRAY_UNSIGNED, [0, 1, 2, 3, 4, 8], 0),
        }
        self.range = RangeData(0.0, 15, -5.0, 5.0, 31)
        self.started: list[int] = []
        self.start_result = 0
        self.items_per_shot = 1
        self.next_item = 0x100
        self.pending: list[int] = []
        self.log: list[tuple[str, int, object]] = []

    # lifecycle
    def open_module(self) -> None:
        pass

    def wait_source(self, timeout_s: float) -> int | None:
        return 1 if self.camera_present else None

    def open_source(self, source_id: int) -> dict[int, CapMeta]:
        return dict(self.meta)

    def caps(self) -> dict[int, CapMeta]:
        meta = dict(self.meta)
        if not self.manual:
            for cap in (CAP_SHUTTER_SPEED, CAP_APERTURE):
                meta[cap] = CapMeta(CAPTYPE_ENUM, OP_GET | OP_GET_ARRAY)
        return meta

    def source_alive(self) -> bool:
        return self.alive

    def close(self) -> None:
        self.closed = True

    # values
    def get_string(self, cap: int) -> str | None:
        return "D7200" if cap == CAP_NAME else None

    def get_number(self, cap: int) -> int | None:
        return self.numbers.get(cap)

    def set_number(self, cap: int, value: int) -> int:
        self.log.append(("n", cap, value))
        self.numbers[cap] = value
        return 0

    def get_enum(self, cap: int) -> EnumData | None:
        e = self.enums.get(cap)
        return EnumData(e.kind, list(e.values), e.value) if e else None

    def set_enum(self, cap: int, index: int) -> int:
        self.log.append(("e", cap, index))
        self.enums[cap].value = index
        return 0

    def get_range(self, cap: int) -> RangeData | None:
        return self.range if cap == CAP_EXPOSURE_COMP else None

    def set_range(self, cap: int, value: float, index: int) -> int:
        self.log.append(("r", cap, index))
        self.range = RangeData(value, index, self.range.lower, self.range.upper, self.range.steps)
        return 0

    # shooting
    def start(self, cap: int, timeout_s: float) -> int:
        self.started.append(cap)
        if self.start_result:
            return self.start_result
        shots = self.numbers[CAP_CONTINUOUS_NUM] if self.enums[CAP_SHOOTING_MODE].value == 2 else 1
        for _ in range(shots * self.items_per_shot):
            self.pending.append(self.next_item)
            self.next_item += 1
        return 0

    def wait_items(self, count: int, timeout_s: float) -> list[int]:
        items, self.pending = self.pending, []
        return items

    def acquire(self, item_id: int, timeout_s: float) -> list[Delivered]:
        return [Delivered(f"DSC_{item_id:04d}.NEF", b"NEF" + bytes([item_id & 0xFF]))]

    def live_view_image(self) -> bytes | None:
        return b"\x00" * 384 + _tiny_jpeg()


def _tiny_jpeg() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 6), (90, 90, 90)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def fake() -> FakeModule:
    return FakeModule(Path("Type0017.md3"))


@pytest.fixture
def adapter(fake: FakeModule, tmp_path: Path) -> NikonModuleAdapter:
    a = NikonModuleAdapter(
        SdkLocation("nikon", tmp_path, tmp_path / "Type0017.md3"), layer_factory=lambda _p: fake
    )
    a.open()
    yield a
    a.close()


def test_pure_helpers():
    assert find_text(["JPEG Fine", "RAW", "RAW + JPEG Fine"], "raw") == 1
    assert find_text(["JPEG Fine"], "RAW") is None
    jpeg = _tiny_jpeg()
    assert jpeg_payload(b"\x01" * 384 + jpeg) == jpeg
    assert jpeg_payload(b"no image") is None


def test_open_prepares_session_and_close_puts_it_back(fake: FakeModule, tmp_path: Path):
    a = NikonModuleAdapter(
        SdkLocation("nikon", tmp_path, tmp_path / "Type0017.md3"), layer_factory=lambda _p: fake
    )
    a.open()
    # SDRAM only (the card in a body on sale is never written), RAW, long exposure NR off
    assert fake.numbers[CAP_SAVE_MEDIA] == 1
    assert fake.numbers[CAP_NOISE_REDUCTION] == 0
    assert fake.enums[CAP_COMPRESSION].values[fake.enums[CAP_COMPRESSION].value] == "RAW"
    info = a.device_info()
    assert info.brand == "Nikon" and info.model == "D7200" and info.battery_percent == 80
    a.close()
    assert fake.closed
    assert fake.numbers[CAP_SAVE_MEDIA] == 0 and fake.numbers[CAP_NOISE_REDUCTION] == 1
    assert fake.enums[CAP_COMPRESSION].value == 2


def test_no_camera_is_a_clear_failure(fake: FakeModule, tmp_path: Path):
    fake.camera_present = False
    a = NikonModuleAdapter(
        SdkLocation("nikon", tmp_path, tmp_path / "Type0017.md3"), layer_factory=lambda _p: fake
    )
    with pytest.raises(CommandFailed, match="no Nikon camera"):
        a.open()
    assert fake.closed


def test_capabilities(adapter: NikonModuleAdapter):
    c = adapter.capabilities()
    assert c.brand == "Nikon" and c.can_capture and c.can_set_exposure and c.can_set_iso
    assert c.live_view and c.reads_battery and c.can_burst
    assert not c.reads_shutter_count  # read from the NEF files instead


def test_apply_settings_matches_offered_text(adapter: NikonModuleAdapter, fake: FakeModule):
    adapter.apply_settings(
        CaptureSettings(iso=1600, exposure_s=30.0, aperture=8.0, exposure_comp_ev=1.0)
    )
    assert fake.enums[CAP_SENSITIVITY].value == 2
    assert fake.enums[CAP_SHUTTER_SPEED].value == 0
    assert fake.enums[CAP_APERTURE].value == 2
    assert fake.range.index == 18  # (1 - -5) * 30 / 10
    adapter.apply_settings(CaptureSettings(exposure_s=1 / 100, metering="spot"))
    assert fake.enums[CAP_SHUTTER_SPEED].value == 2 and fake.numbers[CAP_METERING] == 2


def test_apply_settings_refusals(adapter: NikonModuleAdapter, fake: FakeModule):
    with pytest.raises(CommandFailed, match="not offered"):
        adapter.apply_settings(CaptureSettings(iso=51200))
    with pytest.raises(NotSupported):
        adapter.apply_settings(CaptureSettings(af_point="centre"))
    with pytest.raises(NotSupported):
        adapter.apply_settings(CaptureSettings(shutter_mode="electronic"))
    adapter.apply_settings(CaptureSettings(shutter_mode="mechanical"))  # the only shutter
    fake.manual = False
    fake.numbers[CAP_EXPOSURE_MODE] = 1  # aperture priority on the dial
    with pytest.raises(CommandFailed, match="not on M"):
        adapter.apply_settings(CaptureSettings(exposure_s=30.0))


def test_capture_downloads_the_sdram_file(adapter: NikonModuleAdapter, fake: FakeModule, tmp_path):
    out = adapter.capture(CaptureSettings(kind="dark"), timeout_s=5.0)
    assert out.ok and len(out.files) == 1
    assert fake.started == [CAP_CAPTURE]  # no AF with a body cap
    dest = adapter.download(out.files[0], tmp_path / "dl")
    assert dest.read_bytes().startswith(b"NEF") and dest.suffix == ".NEF"
    with pytest.raises(CommandFailed):
        adapter.download(RemoteFile(ref=str(tmp_path / "x.NEF"), name="x.NEF"), tmp_path)


def test_chart_frames_use_af_capture_and_report_focus_failure(
    adapter: NikonModuleAdapter, fake: FakeModule
):
    fake.start_result = RESULT_OUT_OF_FOCUS
    out = adapter.capture(CaptureSettings(kind="chart"), timeout_s=5.0)
    assert fake.started == [CAP_AF_CAPTURE]
    assert not out.ok and out.focus_failed


def test_burst_uses_ch_and_puts_single_back(adapter: NikonModuleAdapter, fake: FakeModule):
    out = adapter.capture(CaptureSettings(burst=5, tag="c1"), timeout_s=5.0)
    assert out.ok and len(out.files) == 5
    assert fake.numbers[CAP_CONTINUOUS_NUM] == 5
    assert fake.enums[CAP_SHOOTING_MODE].value == 0  # back to single frame


def test_raw_plus_jpeg_gives_both_files(adapter: NikonModuleAdapter, fake: FakeModule):
    fake.items_per_shot = 2
    out = adapter.capture(CaptureSettings(), timeout_s=5.0)
    assert out.ok and len(out.files) == 2


def test_disconnect_is_reported(adapter: NikonModuleAdapter, fake: FakeModule):
    fake.alive = False
    with pytest.raises(Disconnected):
        adapter.capture(CaptureSettings(), timeout_s=1.0)


def test_snapshot_and_restore(adapter: NikonModuleAdapter, fake: FakeModule):
    snap = adapter.snapshot_settings()
    adapter.apply_settings(CaptureSettings(iso=6400, exposure_s=30.0, exposure_comp_ev=2.0))
    adapter.restore_settings(snap)
    assert fake.enums[CAP_SENSITIVITY].value == 0
    assert fake.enums[CAP_SHUTTER_SPEED].value == 4
    assert fake.range.index == 15


def test_live_view_frame_and_off_before_capture(adapter: NikonModuleAdapter, fake: FakeModule):
    frame = adapter.live_view_frame()
    assert frame is not None and frame.shape == (6, 8)
    assert fake.numbers[CAP_LIVE_VIEW_STATUS] == 1
    adapter.capture(CaptureSettings(), timeout_s=5.0)
    assert fake.numbers[CAP_LIVE_VIEW_STATUS] == 0


def test_loader_finds_modules_and_picks_the_module_adapter(tmp_path: Path):
    deep = tmp_path / "S-SDKD7200-011BF-ALLIN" / "Module" / "Win" / "Binary Files" / "x64"
    deep.mkdir(parents=True)
    (deep / "Type0017.md3").write_bytes(b"not a real module")
    (tmp_path / "ControlServiceLayer.dll").write_bytes(b"x")
    found = find_all_sdk("nikon", tmp_path)
    names = sorted(f.library.name for f in found)
    assert names == ["ControlServiceLayer.dll", "Type0017.md3"]
    direct = find_all_sdk("nikon", deep / "Type0017.md3")
    assert len(direct) == 1 and direct[0].library.name == "Type0017.md3"
    adapter = open_sdk_backend("nikon", deep / "Type0017.md3")
    assert isinstance(adapter, NikonModuleAdapter)
    assert loader.add_dll_directories(Path("relative-does-not-exist")) == []


LOCAL_MODULE = Path(__file__).resolve().parents[2] / "sdk" / "nikon" / "D7200" / "Type0017.md3"


@pytest.mark.skipif(
    os.name != "nt" or not LOCAL_MODULE.exists(), reason="no local Type0017 module (D-31)"
)
def test_real_module_loads_and_sees_no_camera():
    """The ctypes binding against the real module: open, list capabilities, close. No camera."""
    from camera_preflight.backends.sdk.nikon_module import MaidLayer

    layer = MaidLayer(LOCAL_MODULE)
    try:
        layer.open_module()
        assert layer._module is not None and 0x07 in layer._module.caps  # Children
        source = layer.wait_source(0.5)
        assert source is None or isinstance(source, int)  # a plugged-in D7200 is fine too
    finally:
        layer.close()
