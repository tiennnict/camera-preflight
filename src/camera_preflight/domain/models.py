"""Core data models (ARCHITECTURE sections 4 and 5.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AutomationLevel,
    Confidence,
    ExecPath,
    FrameKind,
    Label,
    Level,
    Mode,
    Severity,
)
from .message import Message


class Param(BaseModel):
    """A named threshold with its evidence label (FR-TST-05)."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float | int | str | bool
    label: Label
    note: str = ""


class ParameterSet(BaseModel):
    """Versioned verdict parameters (ARCHITECTURE section 4)."""

    model_config = ConfigDict(frozen=True)

    id: str
    params: tuple[Param, ...]

    def get(self, name: str) -> float:
        for p in self.params:
            if p.name == name:
                return float(p.value)
        raise KeyError(name)

    def label_of(self, name: str) -> Label:
        for p in self.params:
            if p.name == name:
                return p.label
        raise KeyError(name)


class FrameMeta(BaseModel):
    """Allowlisted metadata only (FR-META-02)."""

    model_config = ConfigDict(frozen=True)

    make: str | None = None
    model: str | None = None
    serial: str | None = None
    firmware: str | None = None
    lens: str | None = None
    iso: int | None = None
    exposure_s: float | None = None
    aperture: float | None = None
    focal_length_mm: float | None = None
    exposure_comp_ev: float | None = None
    metering_mode: str | None = None
    focus_mode: str | None = None
    af_point: str | None = None
    af_fine_tune: int | None = None
    shutter_type: str | None = None
    file_type: str | None = None
    file_number: int | None = None
    shutter_count: int | None = None
    temperature_c: float | None = None
    capture_time: datetime | None = None
    sub_second: float | None = None
    long_exposure_nr: bool | None = None
    high_iso_nr: bool | None = None
    software: str | None = None
    has_maker_notes: bool | None = None
    width: int | None = None
    height: int | None = None

    def capture_seconds(self) -> float | None:
        """Capture time as seconds, with the sub-second part when present."""
        if self.capture_time is None:
            return None
        return self.capture_time.timestamp() + (self.sub_second or 0.0)


@dataclass(frozen=True)
class CfaData:
    """Decoded sensor mosaic."""

    array: NDArray[np.float32]
    pattern: str
    black_level: float
    white_level: float

    @property
    def shape(self) -> tuple[int, int]:
        return self.array.shape  # type: ignore[return-value]


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    serial: str | None = None
    capture_time: datetime | None = None
    file_number: int | None = None
    edit_flags: tuple[str, ...] = ()


class GateRejection(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule: str
    message: Message


@dataclass
class Frame:
    id: str
    sha256: str
    source: Path
    meta: FrameMeta
    kind: FrameKind = FrameKind.OTHER
    cfa: CfaData | None = None
    provenance: Provenance = field(default_factory=Provenance)
    rejection: GateRejection | None = None

    @property
    def accepted(self) -> bool:
        return self.rejection is None


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    message: Message
    data: dict[str, Any] = {}


class EvidenceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    caption: Message
    sha256: str | None = None


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    check_id: str
    level: Level
    confidence: Confidence | None = None
    severity: Severity | None = None
    path: ExecPath
    findings: tuple[Finding, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    parameters: str = ""
    explanation: Message
    not_tested_reason: str | None = None


class Camera(BaseModel):
    brand: str | None = None
    model: str | None = None
    serial_read: str | None = None
    serial_entered: str | None = None
    firmware: str | None = None
    lens: str | None = None
    shutter_count_before: int | None = None
    shutter_count_after: int | None = None
    temperature_c: float | None = None


class Session(BaseModel):
    id: str
    started: datetime
    mode: Mode
    backend: str = "none"
    camera: Camera = Field(default_factory=Camera)
    app_version: str = ""
    kb_version: str = ""
    parameter_set: str = ""
    results: list[CheckResult] = Field(default_factory=list[CheckResult])


@dataclass(frozen=True)
class FrameRequirement:
    """What a check needs from a capture step (shown in upload mode, FR-GUI-01)."""

    kind: FrameKind
    count: int
    iso: int | None = None
    exposure_s: float | None = None
    aperture: float | None = None
    note_code: str = ""
    shutter_mode: str | None = None
    metering: str | None = None
    exposure_comp_ev: float | None = None
    tag: str = ""

    @property
    def key(self) -> str:
        """Stable key that links captured frames to this requirement."""
        parts = [self.kind.value]
        if self.tag:
            parts.append(self.tag)
        if self.iso is not None:
            parts.append(f"iso{self.iso}")
        if self.exposure_s is not None:
            parts.append(f"t{self.exposure_s:g}")
        if self.aperture is not None:
            parts.append(f"f{self.aperture:g}")
        if self.shutter_mode:
            parts.append(self.shutter_mode)
        if self.metering:
            parts.append(self.metering)
        if self.exposure_comp_ev is not None:
            parts.append(f"ev{self.exposure_comp_ev:+g}")
        return "/".join(parts)


class DeviceInfo(BaseModel):
    """What a backend or the first uploaded frame says about the body (group A)."""

    brand: str | None = None
    model: str | None = None
    serial: str | None = None
    firmware: str | None = None
    lens: str | None = None
    battery_percent: int | None = None
    shutter_count: int | None = None
    storage: tuple[str, ...] = ()
    af_fine_tune: int | None = None
    usb_mode: str | None = None


@dataclass(frozen=True)
class CheckSpec:
    """Declaration of a check (FR-TST-01)."""

    id: str
    group: str
    title: str
    paths: frozenset[ExecPath]
    automation: dict[Mode, AutomationLevel]
    requirements: tuple[FrameRequirement, ...] = ()
    max_shots: int = 0
    needs_sdk: frozenset[str] = frozenset()
    kb_fields: tuple[str, ...] = ()
    gate_rules: tuple[str, ...] = ()
