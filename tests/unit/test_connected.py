from datetime import datetime

import numpy as np
import pytest

from camera_preflight.acquisition import ManualFallback
from camera_preflight.backends.protocol import CommandFailed
from camera_preflight.domain import Level, Mode
from camera_preflight.helpers import HelperParams, HelperWatcher
from camera_preflight.helpers import detectors as d
from camera_preflight.synth import Defects, SidecarReader, SynthCamera
from camera_preflight.synth.backend import SimBackend
from camera_preflight.wizard import Wizard


def make_rig(tmp_path, name="a"):
    cam = SynthCamera(
        defects=Defects(hot=[(100, 100), (100, 102), (102, 100)], hot_rate_e_s=2000.0),
        af_soft_points={"left": 3.0},
        af_fail_points=frozenset({"right"}),
    )
    work = tmp_path / f"cam-{name}"
    be = SimBackend(cam, work)
    be.open()
    w = Wizard(Mode.CONNECTED, tmp_path / f"sessions-{name}", reader=SidecarReader(work))
    w.use_backend(be, tmp_path / f"dl-{name}")
    return w, be


@pytest.fixture
def rig(tmp_path):
    return make_rig(tmp_path)


def test_automatic_step_reads_device_and_checks(rig):
    w, be = rig
    results = {r.check_id: r for r in w.run_connected_step("auto")}
    assert results["A1"].level is Level.PASS and results["A2"].level is Level.PASS
    assert results["A5"].level is Level.PASS and results["C1"].level is Level.PASS
    assert w.camera.shutter_count_before == 12345
    assert w.session.path.name.endswith("SC-1-0001")


def test_dark_group_and_flat_group_run_by_the_app(rig):
    w, be = rig
    w.run_connected_step("auto")
    r = {x.check_id: x for x in w.run_connected_step("dark")}
    assert r["B1"].level is Level.SUSPECT and r["B1"].path.value == "semi_automatic"
    flat = {x.check_id: x for x in w.run_connected_step("flat")}
    assert flat["B2"].level is Level.PASS and flat["C2"].level is Level.PASS
    assert flat["E1"].level is Level.PASS and flat["E5"].level is Level.PASS
    assert flat["B4"].level is Level.PASS


def test_chart_run_uses_af_points_and_records_tier1(rig):
    w, be = rig
    chart = {x.check_id: x for x in w.run_connected_step("chart")}
    assert chart["D3"].level is Level.SUSPECT and "left" in chart["D3"].explanation.params["points"]
    assert any(not a.focused for a in w.af_attempts["right"])
    assert chart["E3"].level is Level.PASS


def test_settings_restored_and_final_count(rig):
    w, be = rig
    w.run_connected_step("dark")
    assert w.finish_connected() is True
    assert be.restored and be.restored[0]["iso"] == 100
    assert w.camera.shutter_count_after > w.camera.shutter_count_before


def test_command_failure_retries_once_then_falls_back(rig, tmp_path):
    w, be = rig
    be.sim_command("fail_next", method="apply_settings", count=1)
    w.run_connected_step("dark")  # one failure: the retry succeeds
    w2, be2 = make_rig(tmp_path, "b")
    be2.sim_command("fail_next", method="apply_settings", count=2)
    with pytest.raises(ManualFallback) as exc:
        w2.run_connected_step("dark")
    assert exc.value.reason_code == "fallback.setting"
    key = exc.value.requirement_key
    be2.sim_command("fail_next", method="apply_settings", count=0)
    out = w2.run_connected_step("dark", manual_done=frozenset({key}))
    assert out


def test_rejected_frame_is_reshot_automatically(rig):
    w, be = rig
    req = w.states["dark"].step.requirements[0]
    be.cam.defects.hot_rate_e_s = 2000.0
    n = w.runner.run_requirement(req)
    assert n == req.count
    assert not [f for f in w.all_frames if not f.accepted]


def test_unplug_raises_disconnected_and_switch_keeps_results(rig):
    from camera_preflight.backends.protocol import Disconnected

    w, be = rig
    w.run_connected_step("auto")
    be.sim_command("disconnect")
    with pytest.raises(Disconnected):
        w.run_connected_step("dark")
    w.switch_to_upload()
    assert w.mode is Mode.UPLOAD and "A1" in w.results  # nothing lost (NFR-05)


def test_helpers_on_live_view():
    rng = np.random.default_rng(0)
    dark = np.clip(rng.normal(4, 1.5, (60, 80)), 0, 255).astype(np.uint8)
    flat = np.clip(rng.normal(190, 2, (60, 80)), 0, 255).astype(np.uint8)
    tex = np.kron(np.random.default_rng(3).random((15, 20)) > 0.5, np.ones((4, 4)))
    chart = (40 + 170 * tex).astype(np.uint8)
    normal = np.clip(rng.normal(120, 40, (60, 80)), 0, 255).astype(np.uint8)
    assert d.h1_dark(dark) and not d.h1_dark(normal)
    assert d.h2_flat(flat) and not d.h2_flat(chart) and not d.h2_flat(dark)
    assert d.h3_chart(chart) and not d.h3_chart(flat)
    assert d.h4_steady(flat, flat) and not d.h4_steady(flat, chart)
    assert d.h5_lens_changed("A", "B") and not d.h5_lens_changed("A", "A")
    assert d.h6_focus_mode(None, "AF") is None and d.h6_focus_mode("af", "AF")
    assert d.h7_card_present((), ("slot1",))


def test_watcher_detects_after_user_acts_and_offers_button(tmp_path):
    be = SimBackend(SynthCamera(), tmp_path / "c")
    be.open()
    be.sim_command("user_action", scene="dark", after_polls=3)
    ticks = iter(range(0, 1000, 5))
    w = HelperWatcher("H1", be, HelperParams(timeout_s=12), clock=lambda: float(next(ticks)))
    flags = [w.poll().detected for _ in range(5)]
    assert flags[0] is False and any(flags)
    # a user who never acts: button appears after the limit, watcher stays attached
    be2 = SimBackend(SynthCamera(), tmp_path / "c2")
    be2.open()
    t2 = iter(range(0, 1000, 8))
    w2 = HelperWatcher("H2", be2, HelperParams(timeout_s=12), clock=lambda: float(next(t2)))
    seen = [w2.poll().button_visible for _ in range(4)]
    assert not seen[0] and seen[-1] and not w2.state.detected
    w2.press_button()
    assert w2.state.detected
    _ = (datetime, CommandFailed)
