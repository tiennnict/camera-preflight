"""User settings stored with QSettings (FR-SET-01 to FR-SET-03)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths


def default_sessions_dir() -> Path:
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(docs or Path.home()) / "camera-preflight" / "sessions"


def bundled_sdk_dir(brand: str) -> Path | None:
    """SDK files shipped next to the executable in the maintainer's binary release (D-47)."""
    if not getattr(sys, "frozen", False):
        return None
    folder = Path(sys.executable).resolve().parent / "sdk" / brand.lower()
    return folder if folder.is_dir() else None


def default_sdk_dir(brand: str) -> Path:
    bundled = bundled_sdk_dir(brand)
    if bundled is not None:
        return bundled
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    return Path(base or Path.home()) / "sdk" / brand.lower()


@dataclass
class UserSettings:
    language: str = ""  # empty: follow the OS
    theme: str = "system"
    reduced_motion: bool = False
    sessions_dir: str = ""
    sdk_dirs: dict[str, str] | None = None
    sdk_setup_seen: bool = False

    def sessions_path(self) -> Path:
        return Path(self.sessions_dir) if self.sessions_dir else default_sessions_dir()

    def sdk_path(self, brand: str) -> Path:
        if self.sdk_dirs and self.sdk_dirs.get(brand):
            return Path(self.sdk_dirs[brand])
        return default_sdk_dir(brand)


BRANDS = ("Canon", "Nikon", "Sony")


def load(store: QSettings | None = None) -> UserSettings:
    s = store or QSettings("camera-preflight", "camera-preflight")
    return UserSettings(
        language=str(s.value("language", "")),
        theme=str(s.value("theme", "system")),
        reduced_motion=str(s.value("reduced_motion", "false")).lower() == "true",
        sessions_dir=str(s.value("sessions_dir", "")),
        sdk_dirs={b: str(s.value(f"sdk/{b}", "")) for b in BRANDS},
        sdk_setup_seen=str(s.value("sdk_setup_seen", "false")).lower() == "true",
    )


def save(settings: UserSettings, store: QSettings | None = None) -> None:
    s = store or QSettings("camera-preflight", "camera-preflight")
    s.setValue("language", settings.language)
    s.setValue("theme", settings.theme)
    s.setValue("reduced_motion", settings.reduced_motion)
    s.setValue("sessions_dir", settings.sessions_dir)
    for b in BRANDS:
        s.setValue(f"sdk/{b}", (settings.sdk_dirs or {}).get(b, ""))
    s.setValue("sdk_setup_seen", settings.sdk_setup_seen)
    s.sync()
