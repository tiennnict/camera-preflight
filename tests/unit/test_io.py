from datetime import datetime

import numpy as np
import pytest

from camera_preflight.io import (
    ExifToolReader,
    SessionFolder,
    TiffMetadataReader,
    UnsupportedFormat,
    decode_raw,
    find_exiftool,
    make_frame,
    sha256_of,
)
from camera_preflight.synth import Defects, SensorSpec, synth_dark, write_dng
from camera_preflight.synth.dng import DngMeta


@pytest.fixture
def dng(tmp_path):
    spec = SensorSpec()
    frame = synth_dark(spec, Defects(), iso=1600, exposure_s=30, rng=np.random.default_rng(0))
    meta = DngMeta(
        iso=1600, exposure_s=30, capture_time=datetime(2026, 3, 4, 5, 6, 7), sub_second=0.25
    )
    return write_dng(tmp_path / "a.dng", frame, meta)


def test_decode_raw_returns_cfa_levels(dng):
    cfa = decode_raw(dng)
    assert cfa.pattern == "RGGB"
    assert cfa.black_level == 512 and cfa.white_level == 16383
    assert cfa.shape == (320, 480)


def test_decode_rejects_unsupported(tmp_path):
    p = tmp_path / "x.png"
    p.write_bytes(b"x")
    with pytest.raises(UnsupportedFormat):
        decode_raw(p)


def test_inhouse_reader_fields(dng):
    m = TiffMetadataReader().read(dng)
    assert (m.make, m.model, m.serial) == ("SynthCam", "SC-1", "SN0001")
    assert m.iso == 1600 and m.exposure_s == 30.0 and m.aperture == 8.0
    assert m.sub_second == 0.25 and m.capture_time == datetime(2026, 3, 4, 5, 6, 7)
    assert m.metering_mode == "Multi-segment"


@pytest.mark.skipif(find_exiftool() is None, reason="ExifTool not installed")
def test_exiftool_reader_matches_inhouse(dng):
    reader = ExifToolReader()
    try:
        a = reader.read(dng)
    finally:
        reader.close()
    b = TiffMetadataReader().read(dng)
    for field in ("make", "model", "serial", "iso", "exposure_s", "aperture", "capture_time"):
        assert getattr(a, field) == getattr(b, field), field
    assert a.metering_mode == b.metering_mode


def test_session_folder_import_and_rename(tmp_path, dng):
    sess = SessionFolder.create(tmp_path / "sessions", datetime(2026, 1, 2, 3, 4, 5))
    copied, digest = sess.import_file(dng)
    assert digest == sha256_of(dng) and copied.read_bytes() == dng.read_bytes()
    assert dng.exists()  # the original is untouched
    sess.identify("SC-1", "SN0001")
    assert sess.path.name == "20260102-030405-SC-1-0001"
    frame = make_frame("f1", sess.frames_dir / copied.name, digest, TiffMetadataReader().read(dng))
    sess.write_frames_index([frame])
    assert (sess.path / "frames.json").exists()
    assert not list(sess.path.glob("*.tmp"))
