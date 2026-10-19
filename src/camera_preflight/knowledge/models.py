"""Knowledge base schema (ARCHITECTURE section 5.2, R-07, FR-KB-01, FR-KB-02).

Every curated value carries a source and a confidence. Models are validated strictly: an
unknown key is an error, so a typo in a contributor's file is caught by CI.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain import Confidence

SCHEMA_VERSION = 1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourcedValue(_Strict):
    value: float | int | str
    source: str = Field(min_length=3)
    confidence: Confidence


class ShutterInfo(_Strict):
    type: Literal["mechanical", "electronic", "both", "efcs"] | None = None
    rated_life: SourcedValue | None = None
    max_burst_fps: SourcedValue | None = None


class AfInfo(_Strict):
    point_count: int | None = Field(default=None, ge=0)
    layout_ref: str | None = None
    metadata_decoder: Literal["verified", "unverified"] = "unverified"
    max_response_s: SourcedValue | None = None


class FirmwareInfo(_Strict):
    version: str
    date: str | None = None
    source: str = Field(min_length=3)


class BackendHints(_Strict):
    no_sdk: Literal["canon_ptp", "nikon_ext", "sony_remote", "libgphoto2", "none"] = "none"
    usb_mode_note: str | None = None


class SerialRange(_Strict):
    """Inclusive range of serial numbers as the manufacturer lists them (same length, digits)."""

    first: str = Field(pattern=r"^\d+$")
    last: str = Field(pattern=r"^\d+$")


IssueMatch = Literal["applies", "may_apply", "not_applicable"]


def _version_key(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text))


class KnownIssue(_Strict):
    """A documented fault of a model or of some units (FR-KB-01). ``serials``, ``serial_pattern``
    and ``firmware_below`` narrow it to the units the source names; without them it concerns
    every unit of the model. It is a warning to check, never a verdict (FR-VER-04)."""

    id: str
    description: str
    description_vi: str | None = None
    scope: str | None = None
    serials: list[SerialRange] = []
    serial_pattern: str | None = None  # regular expression on the serial, e.g. Canon digit rules
    firmware_from: str | None = None  # brought in by this firmware version
    firmware_below: str | None = None  # fixed by this firmware version and later
    serviced_mark: str | None = None  # how a unit already serviced is marked
    lookup_url: str | None = None  # the manufacturer's serial checker
    confirming_test: str
    confidence: Confidence
    source: str = Field(min_length=3)

    @field_validator("serial_pattern")
    @classmethod
    def _pattern(cls, v: str | None) -> str | None:
        if v is not None:
            re.compile(v)
        return v

    def match(self, serial: str | None, firmware: str | None) -> IssueMatch:
        """Whether the issue concerns this unit, from what is known about it."""
        have = _version_key(firmware or "")
        if have and self.firmware_below:
            fixed = _version_key(self.firmware_below)
            if fixed and have >= fixed:
                return "not_applicable"
        if have and self.firmware_from:
            start = _version_key(self.firmware_from)
            if start and have < start:
                return "not_applicable"
        narrowed = bool(self.serials or self.serial_pattern)
        if not narrowed:
            return "applies"
        digits = re.sub(r"\D", "", serial or "")
        if not digits:
            return "may_apply"
        if self.serial_pattern and re.fullmatch(self.serial_pattern, digits):
            return "applies"
        for r in self.serials:
            if len(digits) == len(r.first) and int(r.first) <= int(digits) <= int(r.last):
                return "applies"
        return "not_applicable"


class ModelEntry(_Strict):
    schema_version: int = SCHEMA_VERSION
    brand: Literal["Canon", "Nikon", "Sony"]
    model: str
    aliases: list[str] = []
    release_year: int | None = Field(default=None, ge=1990, le=2100)
    release_year_source: str | None = None
    shutter: ShutterInfo = ShutterInfo()
    af: AfInfo = AfInfo()
    firmware_latest: FirmwareInfo | None = None
    backend_hints: BackendHints = BackendHints()
    known_issues: list[KnownIssue] = []
    controls: list[str] = []

    @field_validator("schema_version")
    @classmethod
    def _version(cls, v: int) -> int:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {v}")
        return v

    def names(self) -> list[str]:
        return [self.model, *self.aliases]


class AfPointSpec(_Strict):
    name: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    kind: Literal["cross", "line", "area"] = "cross"


class AfLayout(_Strict):
    schema_version: int = SCHEMA_VERSION
    name: str
    points: list[AfPointSpec]
