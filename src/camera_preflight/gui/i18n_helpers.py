"""Translation helper for GUI code: ``tr`` resolves in the current language."""

from __future__ import annotations

from .. import i18n


def tr(text: str) -> str:
    return i18n._(text) if text else ""
