from pathlib import Path

import pytest

from camera_preflight.checks import ManualAnswer
from camera_preflight.domain import Level, Mode, Phase
from camera_preflight.synth import Defects, SidecarReader, SynthCamera, write_session
from camera_preflight.wizard import Wizard, build_plan


@pytest.fixture(scope="module")
def session_files(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    cam = SynthCamera(
        defects=Defects(hot=[(100, 100), (100, 102), (102, 100)], hot_rate_e_s=2000.0)
    )
    files = write_session(cam, d)
    return d, files


def test_plan_phase_order_and_modes():
    for mode in Mode:
        plan = build_plan(mode)
        order = [s.phase for s in plan]
        assert order == sorted(order, key=list(Phase).index)  # FR-TST-09
        assert plan[0].phase is Phase.START and plan[-1].phase is Phase.RESULTS
    upload = {s.id for s in build_plan(Mode.UPLOAD)}
    assert {"first", "dark", "flat8", "flat22", "af"} <= upload
    connected = build_plan(Mode.CONNECTED)
    assert {c for s in connected for c in s.checks} >= {"A2", "A5"}  # connected only
    assert "A2" not in {c for s in build_plan(Mode.UPLOAD) for c in s.checks}


def test_every_check_in_a_plan_has_a_step():
    from camera_preflight.checks import checks_for

    for mode in Mode:
        planned = {c for s in build_plan(mode, sdk_available=frozenset({"sony"})) for c in s.checks}
        for check in checks_for(mode):
            if check.spec.id in {"C5"}:
                continue
            assert check.spec.id in planned, (mode, check.spec.id)


def test_upload_flow_end_to_end(tmp_path, session_files):
    src, files = session_files
    w = Wizard(Mode.UPLOAD, tmp_path / "sessions", reader=SidecarReader(src))
    seen_events = []
    w.subscribe(seen_events.append)
    w.go_to("first")
    first_key = next(k for k in files if k.startswith("flat/b2"))
    out = w.upload(files[first_key][:1], "first")
    assert out[0].requirement_key and w.device.model == "SC-1"
    assert w.session.path.name.endswith("SC-1-0001")

    w.go_to("dark")
    for key, paths in files.items():
        if key.startswith("dark/"):
            w.upload(paths, "dark")
    assert "B1" in w.results and w.results["B1"].level is Level.SUSPECT

    w.go_to("flat8")
    w.upload(files["flat/b2/f8"], "flat8")
    w.go_to("flat22")
    w.upload(files["flat/b4/f22"], "flat22")
    w.go_to("burst")
    w.upload(files["burst/c1"], "burst")
    w.go_to("blocker")
    w.answer("F2", ManualAnswer(Level.PASS))

    results = w.finalize()
    by_id = {r.check_id: r for r in results}
    assert by_id["B1"].level is Level.SUSPECT
    assert by_id["B2"].level is Level.PASS and by_id["B4"].level is Level.PASS
    assert by_id["C1"].level is Level.PASS
    assert by_id["C5"].not_tested_reason == "requires_reference_instrument"
    assert by_id["E1"].level is Level.NOT_TESTED  # nothing uploaded
    assert w.camera.shutter_count_before == 12345 and w.camera.shutter_count_after == 12345

    html = w.save_report("vi").read_text(encoding="utf-8")
    assert "Báo cáo" in html
    for name in ("session.json", "results.json", "frames.json", "report.html"):
        assert (w.session.path / name).exists()
    assert not (w.session.path / "frames.json.tmp").exists()
    w.close()


def test_wrong_settings_are_rejected_with_reason(tmp_path, session_files):
    src, files = session_files
    w = Wizard(Mode.UPLOAD, tmp_path / "s", reader=SidecarReader(src))
    w.go_to("dark")
    wrong = files["flat/b2/f8"][0]  # a flat photo uploaded to the dark step
    out = w.upload([wrong], "dark")[0]
    assert not out.accepted and out.rejection is not None
    assert out.rejection.rule in {"G1", "G7"}
    assert out.frame in w.all_frames and not out.frame.accepted  # kept as evidence
    assert "B1" not in w.results  # no verdict from rejected frames


def test_skip_makes_not_tested(tmp_path, session_files):
    src, _ = session_files
    w = Wizard(Mode.UPLOAD, tmp_path / "s2", reader=SidecarReader(src))
    w.skip_step("dark")
    assert w.results["B1"].not_tested_reason == "skipped_by_user"
    assert w.is_done(w.states["dark"].step)


def test_switch_to_upload_keeps_progress(tmp_path, session_files):
    src, _ = session_files
    w = Wizard(Mode.CONNECTED, tmp_path / "s3", reader=SidecarReader(src))
    w.answer("F1", ManualAnswer(Level.PASS))
    w.switch_to_upload()
    assert w.mode is Mode.UPLOAD and "F1" in w.results
    assert w.step.id != "start" or not w.is_done(w.step)


def test_no_resume_and_no_history(tmp_path, session_files):
    src, _ = session_files
    root = tmp_path / "s4"
    Wizard(Mode.UPLOAD, root, reader=SidecarReader(src))
    Wizard(Mode.UPLOAD, root, reader=SidecarReader(src))
    assert len(list(Path(root).iterdir())) == 2  # each launch is a new folder (FR-SES-01)
