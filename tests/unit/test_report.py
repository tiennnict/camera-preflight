from datetime import datetime

from camera_preflight import __version__, i18n
from camera_preflight.checks import ALL_CHECKS, CheckContext, ManualAnswer
from camera_preflight.domain import DEFAULT_1, Camera, Level, Mode
from camera_preflight.gate import check_provenance
from camera_preflight.report import ReportData, SourceFile, render_report
from camera_preflight.synth import Defects, SynthCamera, af_attempts, build_frames


def _data(tmp_path, cam=None):
    cam = cam or SynthCamera(
        defects=Defects(hot=[(100, 100), (100, 102), (102, 100)], hot_rate_e_s=2000.0)
    )
    frames = build_frames(cam)
    allf = [f for v in frames.values() for f in v]
    ctx = CheckContext(
        params=DEFAULT_1,
        mode=Mode.UPLOAD,
        provenance=check_provenance(allf),
        af_attempts=af_attempts(cam),
        evidence_dir=tmp_path,
        manual={"F2": ManualAnswer(Level.FAIL, "crack")},
    )
    results = [c.analyse(frames, ctx) for c in ALL_CHECKS]
    return ReportData(
        camera=Camera(
            brand="SynthCam",
            model="SC-1",
            serial_read="SN0001",
            shutter_count_before=12345,
            shutter_count_after=12411,
        ),
        results=results,
        parameters=DEFAULT_1,
        app_version=__version__,
        kb_version="none",
        created=datetime(2026, 6, 1, 9, 30),
        sources=[SourceFile("f1", "0001-a.dng", "ab" * 32)],
        evidence_dir=tmp_path,
    )


def test_report_contents_english(tmp_path):
    html = render_report(_data(tmp_path), "en")
    assert '<html lang="en"' in html and "Camera check report" in html
    assert "Shutter count before" in html and "12345" in html and "12411" in html
    assert "0001" in html and "SN0001" not in html  # serial suffix only
    assert html.index("Blockers") < html.index("Suspect and fail results")
    assert "data:image/png;base64," in html  # evidence embedded
    assert "no buying or price advice" in html
    assert "0001-a.dng" in html and "ab" * 32 in html
    assert "do not prove" in html
    assert "default-1" in html and "Guess" in html  # thresholds with labels
    assert "Not tested" in html and "Needs a reference instrument" in html


def test_report_vietnamese_and_language_restored(tmp_path):
    i18n.set_language("en")
    html = render_report(_data(tmp_path), "vi")
    assert "Báo cáo kiểm tra máy ảnh" in html and "Nghi vấn" in html
    assert i18n.current_language() == "en"


def test_report_escapes_user_text(tmp_path):
    data = _data(tmp_path)
    data.camera.lens = "<script>alert(1)</script>"
    html = render_report(data, "en")
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html
