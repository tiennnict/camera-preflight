"""Knowledge base schema (ARCHITECTURE section 5.2, R-07, FR-KB-01, FR-KB-02).

Every curated value carries a source and a confidence. Models are validated strictly: an
unknown key is an error, so a typo in a contributor's file is caught by CI.
"""

from __future__ import annotations

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


class KnownIssue(_Strict):
    id: str
    description: str
    scope: str | None = None
    confirming_test: str
    confidence: Confidence
    source: str = Field(min_length=3)


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
