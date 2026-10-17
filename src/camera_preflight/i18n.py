"""Internationalisation: one gettext catalogue for GUI, messages and report (D-15, P-04).

Source strings are English. Strings are marked with ``_()`` where they are shown at
once and with ``N_()`` where the text is stored and translated later.
"""

from __future__ import annotations

import gettext
import locale as _locale
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .domain.message import Message

DOMAIN = "camera_preflight"
LOCALE_DIR = Path(__file__).parent / "locale"
SUPPORTED = ("en", "vi")
DEFAULT = "en"

_translation: gettext.NullTranslations = gettext.NullTranslations()
_current = DEFAULT


def detect_language() -> str:
    """OS language when supported, else English (FR-SET-01)."""
    candidates: list[str] = []
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            candidates.append(value)
    try:
        lang = _locale.getlocale()[0]
    except (ValueError, TypeError):
        lang = None
    if lang:
        candidates.append(lang)
    if os.name == "nt":
        try:
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
            if (lcid & 0x3FF) == 0x2A:  # LANG_VIETNAMESE
                candidates.append("vi")
        except (AttributeError, OSError):
            pass
    for value in candidates:
        code = value.replace("-", "_").split("_")[0].lower()
        if code in SUPPORTED:
            return code
    return DEFAULT


def set_language(lang: str | None = None) -> str:
    """Select the catalogue; returns the language in effect."""
    global _translation, _current
    chosen = lang if lang in SUPPORTED else detect_language()
    _translation = gettext.translation(
        DOMAIN, localedir=str(LOCALE_DIR), languages=[chosen], fallback=True
    )
    _current = chosen
    return chosen


def current_language() -> str:
    return _current


def _(text: str) -> str:
    """Translate now."""
    return _translation.gettext(text)


def N_(text: str) -> str:
    """Mark for extraction; translate later with ``_()``."""
    return text


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


def render(message: Message) -> str:
    """Resolve a message code to text in the current language."""
    from .messages import MESSAGES

    template = MESSAGES.get(message.code)
    if template is None:
        return message.code
    text = _(template)
    try:
        return text.format(**message.params)
    except (KeyError, IndexError, ValueError):
        return text


set_language()
