import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from fake_ptp import FakePtpCamera

from camera_preflight.backends.client import BackendClient
from camera_preflight.backends.protocol import CaptureSettings, Disconnected, NotSupported
from camera_preflight.backends.ptp import PtpBackend, codec
from camera_preflight.backends.sdk.loader import find_sdk, open_sdk_backend, sdk_present


def test_container_and_string_roundtrip():
    c = codec.Container(codec.CMD, 0x1002, 7, (1, 2))
    again = codec.Container.unpack(c.pack())
    assert (again.code, again.transaction, again.params) == (0x1002, 7, (1, 2))
    text, _ = codec.read_string(codec.pack_string("EOS ü"), 0)
    assert text == "EOS ü"


def test_device_info_roundtrip():
    info = codec.DeviceInfoData(
        operations=[0x1001], properties=[0x5001], manufacturer="Sony", model="A", serial="9"
    )
    back = codec.parse_device_info(codec.build_device_info(info))
    assert (back.manufacturer, back.model, back.serial, back.operations) == (
        "Sony",
        "A",
        "9",
        [0x1001],
    )


def test_ptp_backend_identifies_and_reads():
    fake = FakePtpCamera()
    be = PtpBackend(fake, poll_s=0)
    be.open()
    caps = be.capabilities()
    assert (
        caps.brand == "Canon" and caps.can_capture and caps.can_set_iso and caps.reads_shutter_count
    )
    dev = be.device_info()
    assert dev.model == "EOS Test" and dev.battery_percent == 77 and dev.shutter_count == 4321
    assert dev.storage == ("slot1",)


def test_ptp_apply_capture_download_restore(tmp_path):
    fake = FakePtpCamera()
    be = PtpBackend(fake, poll_s=0)
    be.open()
    snap = be.snapshot_settings()
    be.apply_settings(CaptureSettings(iso=1600, exposure_s=0.5, aperture=8.0))
    assert fake.props[codec.PROP_ISO][1] == 1600
    assert (
        fake.props[codec.PROP_EXPOSURE_TIME][1] == 5000 and fake.props[codec.PROP_FNUMBER][1] == 800
    )
    out = be.capture(CaptureSettings(), 1.0)
    assert out.ok and len(out.files) == 1
    path = be.download(out.files[0], tmp_path)
    assert path.read_bytes().startswith(b"RAWDATA")
    be.restore_settings(snap)
    assert fake.props[codec.PROP_ISO][1] == 100


def test_ptp_focus_failure_is_tier1_signal():
    be = PtpBackend(FakePtpCamera(focus_ok=False), poll_s=0)
    be.open()
    out = be.capture(CaptureSettings(), 0.2)
    assert not out.ok and out.focus_failed


def test_ptp_unsupported_vendor_features_are_reported():
    be = PtpBackend(FakePtpCamera(), poll_s=0)
    be.open()
    with pytest.raises(NotSupported):
        be.apply_settings(CaptureSettings(af_point="left"))


def test_sdk_discovery_and_missing(tmp_path):
    assert not sdk_present("canon", tmp_path)
    (tmp_path / "x" / "y").mkdir(parents=True)
    (tmp_path / "x" / "y" / "EDSDK.dll").write_bytes(b"not a library")
    loc = find_sdk("canon", tmp_path)
    assert loc and loc.library.name == "EDSDK.dll"
    adapter = open_sdk_backend("canon", tmp_path)
    assert adapter.capabilities().sdk_features
    with pytest.raises(NotSupported):
        adapter.capture(CaptureSettings(), 1.0)


def test_host_process_roundtrip_and_isolation(tmp_path):
    client = BackendClient("sim", workdir=tmp_path / "cam")
    try:
        client.open()
        assert client.capabilities().can_capture
        assert client.device_info().model == "SC-1"
        out = client.capture(CaptureSettings(kind="dark", iso=1600, exposure_s=0.01), 5.0)
        assert out.ok and out.files
        p = client.download(out.files[0], tmp_path / "dl")
        assert p.exists()
        frame = client.live_view_frame()
        assert frame is not None and frame.ndim == 2
        client.call("sim", name="disconnect")
        with pytest.raises(Disconnected):
            client.capture(CaptureSettings(), 1.0)
    finally:
        client.close()
    assert not client.alive
