"""Frame acceptance rules G1 to G7 (TEST-CATALOGUE section 1, R-14, N-02)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..analysis.common import binned_signal
from ..domain import (
    Confidence,
    Frame,
    FrameKind,
    FrameRequirement,
    GateRejection,
    Message,
    ParameterSet,
)
from ..io.raw import is_raw
from .format import fmt_aperture, fmt_exposure, fmt_iso, fmt_percent

KNOWN_EDITORS = (
    "photoshop",
    "lightroom",
    "gimp",
    "capture one",
    "darktable",
    "rawtherapee",
    "dxo",
    "affinity",
    "luminar",
    "paint.net",
    "pixelmator",
    "on1",
)


@dataclass(frozen=True)
class GateProfile:
    """Rules a capture step applies to each frame."""

    kind: FrameKind
    iso: int | None = None
    exposure_s: float | None = None
    aperture: float | None = None
    require_raw: bool = True
    require_nr_off: bool = True
    check_histogram: bool = False
    check_clipping: bool = False
    check_flicker: bool = False
    check_dark: bool = False
    af_point: str | None = None
    af_decoder_verified: bool = False

    @classmethod
    def for_requirement(cls, req: FrameRequirement) -> GateProfile:
        flat = req.kind is FrameKind.FLAT
        return cls(
            kind=req.kind,
            iso=req.iso,
            exposure_s=req.exposure_s,
            aperture=req.aperture,
            check_histogram=flat and req.exposure_s is not None,
            check_clipping=req.kind in (FrameKind.FLAT, FrameKind.CHART)
            and req.exposure_s is not None,
            check_flicker=flat and req.exposure_s is not None,
            check_dark=req.kind is FrameKind.DARK,
        )


@dataclass
class ProvenanceReport:
    issues: list[Message] = field(default_factory=list)
    confidence_cap: Confidence | None = None


def _reject(rule: str, code: str, **params: str) -> GateRejection:
    return GateRejection(rule=rule, message=Message(code=code, params=dict(params)))


def _fraction_mean(frame: Frame) -> float | None:
    if frame.cfa is None:
        return None
    cfa = frame.cfa
    sig = binned_signal(cfa.array, cfa.pattern, cfa.black_level)
    usable = max(cfa.white_level - cfa.black_level, 1.0)
    return float(sig.mean()) / usable


def periodic_banding(profile: NDArray[np.float64]) -> float:
    """Amplitude (relative) of the strongest periodic component of a row profile."""
    n = profile.size
    if n < 16:
        return 0.0
    x = np.linspace(-1, 1, n)
    detrended = profile - np.polyval(np.polyfit(x, profile, 2), x)
    spectrum = np.abs(np.fft.rfft(detrended * np.hanning(n))) * 2 / (n / 2)
    # periods of 4 rows up to a quarter of the frame
    low = max(int(n / (n / 4)), 4)
    high = max(int(n / 4), low + 1)
    band = spectrum[low:high]
    return float(band.max()) if band.size else 0.0


def evaluate(
    frame: Frame,
    profile: GateProfile,
    params: ParameterSet,
    reference_serial: str | None = None,
    requested_af_point: str | None = None,
) -> GateRejection | None:
    """First failing rule, or None when the frame is accepted."""
    meta = frame.meta

    # G1 Settings
    if profile.require_raw and not is_raw(frame.source):
        return _reject("G1", "gate.not_raw", found=frame.source.suffix.lstrip(".").upper() or "?")
    if profile.iso is not None and meta.iso != profile.iso:
        return _reject("G1", "gate.iso", found=fmt_iso(meta.iso), needed=fmt_iso(profile.iso))
    if profile.exposure_s is not None:
        tol = params.get("gate.exposure_tol_ratio")
        got = meta.exposure_s
        if got is None or not (profile.exposure_s / tol <= got <= profile.exposure_s * tol):
            return _reject(
                "G1",
                "gate.exposure",
                found=fmt_exposure(got),
                needed=fmt_exposure(profile.exposure_s),
            )
    if profile.aperture is not None:
        tol = params.get("gate.aperture_tol_ratio")
        got_f = meta.aperture
        if got_f is None or not (profile.aperture / tol <= got_f <= profile.aperture * tol):
            return _reject(
                "G1",
                "gate.aperture",
                found=fmt_aperture(got_f),
                needed=fmt_aperture(profile.aperture),
            )
    if profile.require_nr_off and (meta.long_exposure_nr or meta.high_iso_nr):
        return _reject("G1", "gate.nr_on")

    # G5 Provenance: same body
    if reference_serial and meta.serial and meta.serial != reference_serial:
        return _reject("G5", "gate.serial_mismatch", found=meta.serial, needed=reference_serial)

    if frame.cfa is None:
        return _reject("G1", "gate.no_raw_data")
    cfa = frame.cfa
    usable = max(cfa.white_level - cfa.black_level, 1.0)

    # G2 Histogram
    if profile.check_histogram:
        mean = _fraction_mean(frame)
        lo, hi = params.get("gate.flat_hist_lo"), params.get("gate.flat_hist_hi")
        if mean is not None and mean < lo:
            return _reject(
                "G2",
                "gate.too_dark",
                found=fmt_percent(mean),
                needed=f"{lo * 100:.0f}-{hi * 100:.0f}",
            )
        if mean is not None and mean > hi:
            return _reject(
                "G2",
                "gate.too_bright",
                found=fmt_percent(mean),
                needed=f"{lo * 100:.0f}-{hi * 100:.0f}",
            )

    # G3 Clipping
    if profile.check_clipping:
        share = float(np.mean(cfa.array >= cfa.white_level * 0.995))
        limit = params.get("gate.clip_share_max")
        if share > limit:
            return _reject(
                "G3", "gate.clipping", found=fmt_percent(share), needed=fmt_percent(limit)
            )

    # G4 Flicker
    if profile.check_flicker and (
        profile.exposure_s is None
        or profile.exposure_s <= params.get("gate.flicker_max_exposure_s")
    ):
        sig = binned_signal(cfa.array, cfa.pattern, cfa.black_level).astype(np.float64)
        rows = sig.mean(axis=1) / max(float(sig.mean()), 1e-6)
        amp = periodic_banding(rows)
        limit = params.get("gate.flicker_amp_max")
        if amp > limit:
            return _reject("G4", "gate.flicker", found=fmt_percent(amp), needed=fmt_percent(limit))

    # G6 AF point (only where a decoder is verified for the model)
    found_point = meta.af_point
    if (
        requested_af_point
        and found_point
        and profile.af_decoder_verified
        and found_point != requested_af_point
    ):
        return _reject("G6", "gate.af_point", found=found_point, needed=requested_af_point)

    # G7 Darkness
    if profile.check_dark:
        mean = _fraction_mean(frame) or 0.0
        limit = params.get("gate.dark_mean_max_frac")
        if mean > limit:
            return _reject(
                "G7", "gate.not_dark", found=fmt_percent(mean), needed=fmt_percent(limit)
            )
        h, w = cfa.shape
        quads = [
            cfa.array[: h // 2, : w // 2].mean(),
            cfa.array[: h // 2, w // 2 :].mean(),
            cfa.array[h // 2 :, : w // 2].mean(),
            cfa.array[h // 2 :, w // 2 :].mean(),
        ]
        spread = float(max(quads) - min(quads)) / usable
        leak = params.get("gate.dark_leak_max_frac")
        if spread > leak:
            return _reject(
                "G7", "gate.light_leak", found=fmt_percent(spread), needed=fmt_percent(leak)
            )
    return None


def check_provenance(frames: list[Frame], entered_serial: str | None = None) -> ProvenanceReport:
    """Set-level provenance checks (N-02): flags and confidence cap, no rejection here."""
    report = ProvenanceReport()
    if not frames:
        return report
    serials = {f.meta.serial for f in frames if f.meta.serial}
    if not serials:
        report.issues.append(Message(code="provenance.no_serial"))
        report.confidence_cap = Confidence.MEDIUM
    elif len(serials) > 1:
        report.issues.append(
            Message(code="provenance.mixed_serials", params={"count": str(len(serials))})
        )
        report.confidence_cap = Confidence.LOW
    if entered_serial and serials and entered_serial not in serials:
        report.issues.append(Message(code="provenance.entered_serial_differs"))
        report.confidence_cap = Confidence.LOW
    edited = [
        f.id
        for f in frames
        if f.meta.software and any(e in f.meta.software.lower() for e in KNOWN_EDITORS)
    ]
    if edited:
        report.issues.append(Message(code="provenance.edited", params={"count": str(len(edited))}))
        report.confidence_cap = Confidence.LOW
    if any(f.meta.has_maker_notes is False for f in frames):
        report.issues.append(Message(code="provenance.no_maker_notes"))
        report.confidence_cap = report.confidence_cap or Confidence.MEDIUM
    stamped = [(f.meta.file_number, f.meta.capture_seconds()) for f in frames]
    both = [(n, t) for n, t in stamped if n is not None and t is not None]
    if len(both) >= 3:
        by_number = [t for _, t in sorted(both, key=lambda x: x[0])]
        if any(b < a for a, b in itertools.pairwise(by_number)):
            report.issues.append(Message(code="provenance.order"))
            report.confidence_cap = Confidence.LOW
    return report


def lower(a: Confidence, cap: Confidence | None) -> Confidence:
    """The lower of a confidence and an optional cap."""
    if cap is None:
        return a
    order = {Confidence.HIGH: 2, Confidence.MEDIUM: 1, Confidence.LOW: 0}
    return a if order[a] <= order[cap] else cap
