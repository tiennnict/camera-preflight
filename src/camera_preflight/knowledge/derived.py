"""Derived tier and resolver (R-07, FR-KB-03, FR-KB-04).

The derived record is built from the session's own frames and never committed. The resolver
prefers curated values; derived values carry lowered confidence; absence is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..domain import Confidence, DeviceInfo, Frame
from .models import ModelEntry

Tier = Literal["curated", "derived", "none"]


@dataclass
class DerivedRecord:
    make: str | None = None
    model: str | None = None
    firmware: str | None = None
    lens: str | None = None
    sensor_size: tuple[int, int] | None = None
    shutter_types: set[str] = field(default_factory=set)
    af_points_seen: set[str] = field(default_factory=set)


def derive_record(frames: list[Frame], device: DeviceInfo | None = None) -> DerivedRecord:
    rec = DerivedRecord()
    if device:
        rec.make, rec.model, rec.firmware, rec.lens = (
            device.brand,
            device.model,
            device.firmware,
            device.lens,
        )
    for f in frames:
        m = f.meta
        rec.make = rec.make or m.make
        rec.model = rec.model or m.model
        rec.firmware = rec.firmware or m.firmware
        rec.lens = rec.lens or m.lens
        if m.width and m.height and rec.sensor_size is None:
            rec.sensor_size = (m.width, m.height)
        if m.shutter_type:
            rec.shutter_types.add(m.shutter_type)
        if m.af_point:
            rec.af_points_seen.add(m.af_point)
    return rec


@dataclass(frozen=True)
class Resolved:
    """A value together with where it came from."""

    value: object | None
    tier: Tier
    confidence_cap: Confidence | None = None


def resolve_rated_life(entry: ModelEntry | None) -> Resolved:
    if entry and entry.shutter.rated_life:
        rl = entry.shutter.rated_life
        return Resolved(rl.value, "curated", rl.confidence)
    return Resolved(None, "none")


def resolve_burst_fps(entry: ModelEntry | None) -> Resolved:
    if entry and entry.shutter.max_burst_fps:
        v = entry.shutter.max_burst_fps
        return Resolved(v.value, "curated", v.confidence)
    return Resolved(None, "none")


def resolve_af_point_count(entry: ModelEntry | None, derived: DerivedRecord) -> Resolved:
    if entry and entry.af.point_count:
        return Resolved(entry.af.point_count, "curated")
    if derived.af_points_seen:
        return Resolved(len(derived.af_points_seen), "derived", Confidence.LOW)
    return Resolved(None, "none")
