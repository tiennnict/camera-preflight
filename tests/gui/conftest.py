import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings

from camera_preflight import i18n
from camera_preflight.gui.settings import UserSettings


@pytest.fixture
def settings_store(tmp_path):
    return QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def user_settings(tmp_path):
    i18n.set_language("en")
    return UserSettings(language="en", sessions_dir=str(tmp_path / "sessions"), sdk_dirs={})


@pytest.fixture(autouse=True)
def no_camera_on_usb(monkeypatch):
    """GUI tests never look at the real USB bus or SDKs: nothing is plugged in."""
    monkeypatch.setattr("camera_preflight.backends.discovery.present_brands", lambda: frozenset())
