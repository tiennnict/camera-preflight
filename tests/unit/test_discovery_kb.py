"""Camera detection order, USB brand scan, capture timeouts and known-issue matching."""

from __future__ import annotations

from pathlib import Path

from camera_preflight.acquisition.runner import ConnectedRunner
from camera_preflight.backends.discovery import Candidate, candidates, detect
from camera_preflight.backends.protocol import CaptureSettings
from camera_preflight.backends.usb_scan import brands_in
from camera_preflight.knowledge import KnownIssue, bundled_kb_root, default_kb, load_kb


def _sdk_tree(tmp_path: Path) -> dict[str, Path]:
    (tmp_path / "nikon" / "D7200").mkdir(parents=True)
    (tmp_path / "nikon" / "D7200" / "Type0017.md3").write_bytes(b"m")
    (tmp_path / "nikon" / "Z").mkdir()
    (tmp_path / "nikon" / "Z" / "ControlServiceLayer.dll").write_bytes(b"d")
    for sub in ("a", "b"):
        (tmp_path / "canon" / sub).mkdir(parents=True)
        (tmp_path / "canon" / sub / "EDSDK.dll").write_bytes(b"c")
    return {"nikon": tmp_path / "nikon", "canon": tmp_path / "canon", "sony": tmp_path / "x"}


def test_brands_from_usb_instance_ids():
    ids = [r"USB\VID_04B0&PID_0444\6000123", r"USB\VID_046D&PID_C52B\5", r"USB\ROOT_HUB30\4"]
    assert brands_in(ids) == frozenset({"nikon"})
    assert brands_in([r"USB\VID_04A9&PID_32B4\0", r"USB\VID_054C&PID_0CCC\1"]) == {"canon", "sony"}


def test_candidates_only_for_brands_on_usb(tmp_path: Path):
    dirs = _sdk_tree(tmp_path)
    got = candidates(dirs, frozenset({"nikon"}), ptp=False)
    assert [c.library.name for c in got if c.library] == ["Type0017.md3", "ControlServiceLayer.dll"]
    every = candidates(dirs, None, ptp=True)
    assert sum(1 for c in every if c.brand == "canon") == 1  # one EDSDK copy is enough
    assert every[-1].spec == "ptp-usb"


def test_detect_reports_nothing_at_once_when_no_camera_is_plugged(tmp_path: Path):
    calls: list[Candidate] = []
    result = detect(
        sdk_dirs=_sdk_tree(tmp_path),
        scan=lambda: frozenset(),
        attempt=lambda c, _w: calls.append(c),  # type: ignore[func-returns-value]
    )
    assert not result.found and calls == []


def test_detect_tries_each_nikon_module_until_one_opens(tmp_path: Path):
    tried: list[str] = []

    def attempt(c: Candidate, _w: Path | None):
        tried.append(c.library.name if c.library else c.spec)
        return ("D7200", "Nikon") if c.library and c.library.suffix == ".md3" else None

    result = detect(
        sdk_dirs=_sdk_tree(tmp_path), scan=lambda: frozenset({"nikon"}), attempt=attempt
    )
    assert result.found and result.camera == "D7200" and result.spec == "sdk:nikon"
    assert result.sdk_dir is not None and result.sdk_dir.name == "Type0017.md3"
    assert tried == ["Type0017.md3"]


def test_detect_hints_when_a_camera_cannot_be_opened(tmp_path: Path):
    dirs = _sdk_tree(tmp_path)
    failed = detect(sdk_dirs=dirs, scan=lambda: frozenset({"nikon"}), attempt=lambda c, w: None)
    assert not failed.found and failed.hint_code == "detect.failed" and failed.seen_brand == "nikon"
    no_sdk = detect(sdk_dirs=dirs, scan=lambda: frozenset({"sony"}), attempt=lambda c, w: None)
    assert no_sdk.hint_code == "detect.no_sdk" and no_sdk.seen_brand == "sony"


def test_capture_timeout_covers_long_exposures():
    runner = ConnectedRunner.__new__(ConnectedRunner)
    runner.timeout_s = 20.0
    assert runner.capture_timeout(CaptureSettings(exposure_s=30.0)) >= 30.0 * 2
    assert runner.capture_timeout(CaptureSettings(burst=8)) == 160.0


def _issue(**kw) -> KnownIssue:
    base = {
        "id": "x",
        "description": "d",
        "confirming_test": "B4",
        "confidence": "high",
        "source": "src",
    }
    return KnownIssue.model_validate({**base, **kw})


def test_known_issue_matching_by_serial_range_pattern_and_firmware():
    ranged = _issue(serials=[{"first": "3020001", "last": "3023644"}])
    assert ranged.match("3020500", None) == "applies"
    assert ranged.match("3030000", None) == "not_applicable"
    assert ranged.match(None, None) == "may_apply"
    canon = _issue(serial_pattern=r"0\d{4}[12]\d{6}")
    assert canon.match("012341567890", None) == "applies"
    assert canon.match("112341567890", None) == "not_applicable"
    fw = _issue(firmware_from="2.00", firmware_below="2.10")
    assert fw.match(None, "2.00") == "applies"
    assert fw.match(None, "ILCE-7M3 v2.10") == "not_applicable"
    assert fw.match(None, "1.10") == "not_applicable"
    assert _issue().match(None, None) == "applies"


def test_shipped_knowledge_base_is_valid_and_loaded_by_default():
    kb, problems = load_kb(bundled_kb_root())
    assert problems == []
    assert kb.find("NIKON CORPORATION", "NIKON D7200") is not None
    assert kb.find("Canon", "Canon EOS 70D") is not None
    assert kb.find("SONY", "ILCE-9") is not None
    for entry in kb.entries:
        for issue in entry.known_issues:
            assert issue.source.startswith("https://") and issue.description_vi
    assert default_kb().find("Nikon", "D750") is not None
