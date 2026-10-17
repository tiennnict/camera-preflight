"""Write a synthetic session to disk as DNG files, and read their metadata back.

``SidecarReader`` returns the metadata saved next to each file. It stands in for ExifTool on
synthetic files, which carry no maker notes (shutter count, AF point) that a real camera writes.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..domain import Frame, FrameMeta
from ..io.errors import MetadataError
from ..io.session import sha256_of
from .dng import DngMeta, write_dng
from .session import SynthCamera, build_frames

_METERING = {"Multi-segment": 5, "Center-weighted": 2, "Spot": 3, "Average": 1}


def _dng_meta(m: FrameMeta, cam: SynthCamera) -> DngMeta:
    return DngMeta(
        make=m.make or cam.make,
        model=m.model or cam.model,
        serial=m.serial,
        lens=m.lens,
        iso=m.iso or 100,
        exposure_s=m.exposure_s or 0.01,
        aperture=m.aperture or 8.0,
        focal_length_mm=m.focal_length_mm or 50.0,
        exposure_comp_ev=m.exposure_comp_ev or 0.0,
        metering_mode=_METERING.get(m.metering_mode or "", 5),
        capture_time=m.capture_time or datetime(2026, 1, 1),
        sub_second=m.sub_second or 0.0,
        software=m.software,
        black_level=int(cam.spec.black_level),
        white_level=int(cam.spec.white_level),
    )


def write_frame(frame: Frame, cam: SynthCamera, directory: Path) -> Path:
    """One frame as a DNG plus a ``.meta.json`` sidecar. Burst frames without pixels get a blank."""
    import numpy as np

    path = directory / frame.source.name
    cfa = (
        frame.cfa.array
        if frame.cfa is not None
        else np.full((cam.spec.height, cam.spec.width), cam.spec.black_level, dtype=np.float32)
    )
    write_dng(path, cfa, _dng_meta(frame.meta, cam), cam.spec.pattern)
    (path.parent / (path.name + ".meta.json")).write_text(
        frame.meta.model_dump_json(), encoding="utf-8"
    )
    return path


def write_session(cam: SynthCamera, directory: Path) -> dict[str, list[Path]]:
    """Files for every requirement key of ``build_frames``."""
    directory.mkdir(parents=True, exist_ok=True)
    out: dict[str, list[Path]] = {}
    for key, frames in build_frames(cam).items():
        out[key] = [write_frame(f, cam, directory) for f in frames]
    return out


class SidecarReader:
    """Metadata lookup by file content hash, so copies made by the session still resolve."""

    name = "sidecar"

    def __init__(self, directory: Path) -> None:
        self._by_hash: dict[str, FrameMeta] = {}
        for side in directory.glob("*.meta.json"):
            data = side.with_name(side.name.removesuffix(".meta.json"))
            if data.exists():
                self._by_hash[sha256_of(data)] = FrameMeta.model_validate(
                    json.loads(side.read_text(encoding="utf-8"))
                )

    def read(self, path: Path) -> FrameMeta:
        meta = self._by_hash.get(sha256_of(path))
        if meta is None:
            raise MetadataError(f"no sidecar for {path.name}")
        return meta

    def close(self) -> None:
        return None
