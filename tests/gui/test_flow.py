import pytest

from camera_preflight import i18n
from camera_preflight.domain import Level
from camera_preflight.gui.controller import Controller
from camera_preflight.gui.shell import MainWindow
from camera_preflight.gui.views.manual import ManualView
from camera_preflight.gui.views.results import ResultsView
from camera_preflight.gui.views.start import StartView
from camera_preflight.gui.views.upload import UploadView
from camera_preflight.synth import Defects, SidecarReader, SynthCamera, write_session

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    d = tmp_path_factory.mktemp("g")
    cam = SynthCamera(
        defects=Defects(hot=[(100, 100), (100, 102), (102, 100)], hot_rate_e_s=2000.0)
    )
    return d, write_session(cam, d)


def _window(qtbot, user_settings, settings_store, src):
    ctrl = Controller()
    win = MainWindow(user_settings, ctrl, settings_store)
    qtbot.addWidget(win)
    win.show()
    return win, ctrl


def test_home_has_no_history_and_start_goes_to_blocker(qtbot, user_settings, settings_store, files):
    src, _ = files
    win, ctrl = _window(qtbot, user_settings, settings_store, src)
    assert isinstance(win.view, StartView)
    assert not win.next_btn.isEnabled()
    win.start_session("")
    assert isinstance(win.view, ManualView)
    assert ctrl.wizard is not None and win.tree.topLevelItemCount() >= 4
    win.close()


def test_blocker_answer_and_stop(qtbot, user_settings, settings_store, files, monkeypatch):
    src, _ = files
    win, ctrl = _window(qtbot, user_settings, settings_store, src)
    win.start_session("")
    seen = []
    monkeypatch.setattr(win, "_blocker_found", lambda: seen.append(1))
    assert isinstance(win.view, ManualView)
    q = win.view.questions["F2"]
    q._buttons[Level.FAIL].click()
    assert seen and ctrl.wizard.results["F2"].severity.value == "blocker"
    win.close()


def test_upload_and_results(qtbot, user_settings, settings_store, files, monkeypatch):
    src, paths = files
    ctrl = Controller()
    win = MainWindow(user_settings, ctrl, settings_store)
    qtbot.addWidget(win)
    win.show()
    win.start_session("")
    ctrl.wizard.reader = SidecarReader(src)
    win.show_step("dark")
    assert isinstance(win.view, UploadView)
    for key, ps in paths.items():
        if key.startswith("dark/"):
            with qtbot.waitSignal(ctrl.jobDone, timeout=60000):
                win.view.upload(ps, key)
    assert "B1" in ctrl.wizard.results
    assert win.view.files_box.count() >= 18
    win.show_step("flat8")
    with qtbot.waitSignal(ctrl.jobDone, timeout=60000):
        win.view.upload(paths["flat/b2/f8"], "flat/b2/f8")
    pass
    win.show_step("results")
    assert isinstance(win.view, ResultsView)
    qtbot.waitUntil(lambda: win.view.save_btn.isEnabled(), timeout=90000)
    qtbot.wait(200)
    pass
    assert win.view.report_lang.currentData() == "en"
    win.close()


def test_language_switch_rebuilds_text(qtbot, user_settings, settings_store, files):
    src, _ = files
    win, _ = _window(qtbot, user_settings, settings_store, src)
    win.apply_language("vi")
    assert i18n.current_language() == "vi"
    assert win.settings_btn.text() == "Cài đặt"
    assert win.view.title.text() == "Kiểm tra máy ảnh cũ"
    win.apply_language("en")
    assert win.settings_btn.text() == "Settings"
    win.close()


def test_reduced_motion_shows_static_frame(qtbot):
    from camera_preflight.gui.animations import SCENES, AnimationPanel

    panel = AnimationPanel()
    qtbot.addWidget(panel)
    panel.set_reduced_motion(True)
    panel.show_scene(SCENES["body_cap"])
    assert not panel.pause_btn.isEnabled()
    assert panel._anim.state().name != "Running"
    panel.set_reduced_motion(False)
    panel.show_scene(SCENES["body_cap"])
    assert panel._anim.state().name == "Running"
    panel.stop()


def test_all_scenes_load(qtbot):
    from camera_preflight.gui.animations import SCENE_IDS, SCENES, ScenePlayer

    assert len(SCENE_IDS) == 24
    player = ScenePlayer()
    qtbot.addWidget(player)
    for sc in SCENES.values():
        player.load(sc)
        for t in (0.0, 0.5, 1.0):
            player.set_time(t)


def test_settings_dialog_round_trip(qtbot, user_settings):
    from camera_preflight.gui.views.settings_dialogs import SettingsDialog

    dlg = SettingsDialog(user_settings)
    qtbot.addWidget(dlg)
    dlg.theme.setCurrentIndex(dlg.theme.findData("dark"))
    dlg.motion.setChecked(True)
    out = dlg.result_settings()
    assert out.theme == "dark" and out.reduced_motion and out.language == "en"


def test_sdk_setup_can_be_skipped(qtbot, user_settings):
    from camera_preflight.gui.views.settings_dialogs import SdkSetupDialog

    dlg = SdkSetupDialog(user_settings)
    qtbot.addWidget(dlg)
    assert set(dlg.result_dirs()) == {"Canon", "Nikon", "Sony"}
    dlg.skip.click()
    assert dlg.result() == 0  # rejected: continue without SDK


def test_about_lists_credits_or_none(qtbot):
    from camera_preflight.gui.views.about import AboutDialog

    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()


def test_demo_connected_flow(qtbot, user_settings, settings_store, monkeypatch):
    from camera_preflight.domain import Mode

    ctrl = Controller()
    win = MainWindow(user_settings, ctrl, settings_store)
    qtbot.addWidget(win)
    win.show()
    monkeypatch.setattr(win, "_auto_advance", lambda: None)
    win.start_session("", demo=True)
    w = ctrl.wizard
    assert w is not None and w.mode is Mode.CONNECTED
    assert win.camera_label.text() == "SC-1"
    win.show_step("auto")
    from camera_preflight.gui.views.connected import ConnectedStepView

    assert isinstance(win.view, ConnectedStepView)
    qtbot.waitUntil(lambda: "A1" in w.results and not win.view.running, timeout=60000)
    # helper step: the simulated user fits the cap, the helper detects it, the app shoots
    win.show_step("dark")
    w.backend.call("sim", name="user_action", args={"scene": "dark", "after_polls": 2})
    qtbot.waitUntil(lambda: "B1" in w.results, timeout=120000)
    assert w.results["B1"].path.value == "semi_automatic"
    win.close()
    w.backend.close()
