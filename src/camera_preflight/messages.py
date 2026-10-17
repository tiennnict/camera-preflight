"""Registry of translatable message templates, keyed by message code.

Checks, the gate and the wizard return ``Message(code, params)``. The English text lives
here; ``i18n.render`` resolves it in the user's language. Keep texts short (D-44).
"""

from __future__ import annotations

from .i18n import N_

MESSAGES: dict[str, str] = {}


def register(entries: dict[str, str]) -> None:
    for code, text in entries.items():
        if code in MESSAGES and MESSAGES[code] != text:
            raise ValueError(f"message code registered twice: {code}")
        MESSAGES[code] = text


# Codes are added by the module that owns them; see ``messages_*`` sections below.
register(
    {
        "level.pass": N_("Pass"),
        "level.suspect": N_("Suspect"),
        "level.fail": N_("Fail"),
        "level.not_tested": N_("Not tested"),
        "confidence.high": N_("High confidence"),
        "confidence.medium": N_("Medium confidence"),
        "confidence.low": N_("Low confidence"),
        "severity.blocker": N_("Blocker"),
        "severity.high": N_("High"),
        "severity.medium": N_("Medium"),
        "severity.low": N_("Low"),
        "path.automatic": N_("Automatic"),
        "path.semi_automatic": N_("Semi-automatic"),
        "path.file_import": N_("From uploaded files"),
        "path.manual": N_("Manual"),
        "mode.connected": N_("Connected"),
        "mode.upload": N_("Upload"),
    }
)
