"""Result vocabulary shared by every layer (ARCHITECTURE section 4)."""

from enum import StrEnum


class Level(StrEnum):
    PASS = "pass"
    SUSPECT = "suspect"
    FAIL = "fail"
    NOT_TESTED = "not_tested"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(StrEnum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExecPath(StrEnum):
    TETHERED = "tethered"
    SEMI_AUTOMATIC = "semi_automatic"
    FILE_IMPORT = "file_import"
    MANUAL = "manual"


class AutomationLevel(StrEnum):
    AUTOMATIC = "automatic"
    HELPER = "helper"
    BUTTON = "button"
    UPLOAD = "upload"
    MANUAL = "manual"


class Mode(StrEnum):
    CONNECTED = "connected"
    UPLOAD = "upload"


class Phase(StrEnum):
    START = "start"
    BLOCKER = "blocker"
    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"
    MANUAL = "manual"
    RESULTS = "results"


class FrameKind(StrEnum):
    DARK = "dark"
    FLAT = "flat"
    CHART = "chart"
    BURST = "burst"
    OTHER = "other"


class Label(StrEnum):
    """Evidence labels (handoff section 0)."""

    SOURCED = "Sourced"
    INFERENCE = "Inference"
    GUESS = "Guess"
    UNVERIFIED = "Unverified"
