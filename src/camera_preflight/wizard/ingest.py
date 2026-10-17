"""Bring one file into a session: copy, read, decode, validate (FR-ACQ-02, FR-GATE-01 to 03)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from ..domain import (
    Frame,
    FrameKind,
    FrameMeta,
    FrameRequirement,
    GateRejection,
    Message,
    ParameterSet,
)
from ..gate import GateProfile, evaluate
from ..io import MetadataError, MetadataReader, RawDecodeError, SessionFolder, UnsupportedFormat
from ..io.raw import decode_raw, is_raw
from ..io.session import make_frame


@dataclass
class IngestOutcome:
    file: Path
    frame: Frame
    requirement_key: str | None
    rejection: GateRejection | None

    @property
    def accepted(self) -> bool:
        return self.rejection is None


_METERING_NAMES = {
    "evaluative": "Multi-segment",
    "centre_weighted": "Center-weighted",
    "spot": "Spot",
}


def _distance(meta: FrameMeta, req: FrameRequirement) -> int:
    """How many of the requested settings the frame misses (picks the closest requirement)."""
    miss = 0
    if req.iso is not None and meta.iso != req.iso:
        miss += 1
    if req.exposure_s is not None and (
        meta.exposure_s is None or abs(meta.exposure_s / req.exposure_s - 1) > 0.15
    ):
        miss += 1
    if req.aperture is not None and (
        meta.aperture is None or abs(meta.aperture / req.aperture - 1) > 0.12
    ):
        miss += 1
    if req.exposure_comp_ev is not None and (
        meta.exposure_comp_ev is None or abs(meta.exposure_comp_ev - req.exposure_comp_ev) > 0.2
    ):
        miss += 1
    if req.metering is not None and meta.metering_mode != _METERING_NAMES.get(req.metering):
        miss += 1
    if req.shutter_mode == "electronic" and (meta.shutter_type or "").lower() != "electronic":
        miss += 1
    return miss


def ingest_file(
    src: Path,
    session: SessionFolder,
    reader: MetadataReader,
    frame_id: str,
    requirements: Sequence[FrameRequirement],
    params: ParameterSet,
    reference_serial: str | None = None,
    *,
    af_decoder_verified: bool = False,
    requested_af_point: str | None = None,
) -> IngestOutcome:
    copied, digest = session.import_file(src)
    try:
        meta = reader.read(copied)
    except MetadataError:
        meta = FrameMeta()
    frame = make_frame(frame_id, copied, digest, meta)
    kind = requirements[0].kind if requirements else FrameKind.OTHER
    frame.kind = kind
    # Decode RAW; a file that cannot be decoded is kept as evidence and rejected.
    decode_failure: GateRejection | None = None
    if is_raw(copied):
        try:
            frame.cfa = decode_raw(copied)
        except (UnsupportedFormat, RawDecodeError) as exc:
            code = exc.code
            decode_failure = GateRejection(rule="G1", message=Message(code=code))
    if not requirements:
        frame.rejection = decode_failure
        return IngestOutcome(src, frame, None, decode_failure)

    ranked = sorted(requirements, key=lambda r: _distance(meta, r))
    best_rejection: GateRejection | None = None
    chosen: FrameRequirement | None = None
    for req in ranked:
        profile = replace(GateProfile.for_requirement(req), af_decoder_verified=af_decoder_verified)
        if decode_failure is not None:
            rej = decode_failure
        else:
            rej = evaluate(
                frame,
                profile,
                params,
                reference_serial=reference_serial,
                requested_af_point=requested_af_point,
            )
        if rej is None:
            chosen = req
            best_rejection = None
            break
        if best_rejection is None:
            best_rejection = rej
    if chosen is None:
        frame.rejection = best_rejection
        frame.kind = ranked[0].kind
        return IngestOutcome(src, frame, ranked[0].key, best_rejection)
    frame.kind = chosen.kind
    return IngestOutcome(src, frame, chosen.key, None)
