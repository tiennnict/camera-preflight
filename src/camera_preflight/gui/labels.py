"""Text for requirements: card titles and parameter rows (UX section 9: key and value, no prose)."""

from __future__ import annotations

from ..domain import FrameKind, FrameRequirement
from ..gate.format import fmt_aperture, fmt_exposure
from ..i18n import N_
from .i18n_helpers import tr

_POINTS = {
    "centre": N_("Centre"),
    "left": N_("Left"),
    "right": N_("Right"),
    "top": N_("Top"),
    "bottom": N_("Bottom"),
}
_METERING = {
    "evaluative": N_("Evaluative"),
    "centre_weighted": N_("Centre-weighted"),
    "spot": N_("Spot"),
}


def point_name(name: str) -> str:
    return tr(_POINTS.get(name, name))


def requirement_title(req: FrameRequirement) -> str:
    tag = req.tag
    if req.kind is FrameKind.DARK:
        return tr("Dark, ISO {iso}, {exposure}").format(
            iso=req.iso, exposure=fmt_exposure(req.exposure_s)
        )
    if tag.startswith("af"):
        name = point_name(tag.split(":", 1)[1])
        return tr("Focus point: {point}").format(point=name)
    if tag == "first":
        return tr("Test photo")
    if tag == "c1":
        return tr("Burst of {count}").format(count=req.count)
    if tag == "b2":
        return tr("Flat, {aperture}").format(aperture=fmt_aperture(req.aperture))
    if tag == "b4":
        return tr("Flat, {aperture}").format(aperture=fmt_aperture(req.aperture))
    if tag == "c2":
        return tr("Flat, {exposure}").format(exposure=fmt_exposure(req.exposure_s))
    if tag == "c4":
        return tr("Flat, {exposure}, electronic shutter").format(
            exposure=fmt_exposure(req.exposure_s)
        )
    if tag == "c3":
        return tr("Flat, {count} identical photos").format(count=req.count)
    if tag == "e1":
        return tr("Even scene, auto exposure")
    if tag == "e2":
        return tr("Metering: {mode}").format(
            mode=tr(_METERING.get(req.metering or "", req.metering or ""))
        )
    if tag == "e3-bright":
        return tr("Spot on a bright area")
    if tag == "e3-dark":
        return tr("Spot on a dark area")
    if tag == "e5":
        return tr("Compensation {ev} EV").format(ev=f"{req.exposure_comp_ev:+g}")
    if tag == "e6":
        return tr("ISO {iso}").format(iso=req.iso)
    if tag == "e7":
        return tr("Aperture {aperture}").format(aperture=fmt_aperture(req.aperture))
    return tr("Photos")


def requirement_rows(req: FrameRequirement) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [(tr("File type"), tr("RAW"))]
    rows.append((tr("Noise reduction"), tr("Off")))
    if req.iso is not None:
        rows.append((tr("ISO"), str(req.iso)))
    if req.exposure_s is not None:
        rows.append((tr("Shutter"), fmt_exposure(req.exposure_s)))
    if req.aperture is not None:
        rows.append((tr("Aperture"), fmt_aperture(req.aperture)))
    if req.exposure_comp_ev is not None:
        rows.append((tr("Compensation"), f"{req.exposure_comp_ev:+g} EV"))
    if req.metering:
        rows.append((tr("Metering"), tr(_METERING.get(req.metering, req.metering))))
    if req.shutter_mode == "electronic":
        rows.append((tr("Shutter type"), tr("Electronic")))
    if req.kind is FrameKind.DARK:
        rows.append((tr("Sensor"), tr("Covered")))
    elif req.kind is FrameKind.FLAT:
        rows.append((tr("Target"), tr("Even, defocused")))
    elif req.kind is FrameKind.CHART:
        rows.append((tr("Focus"), tr("One point, AF-S")))
    elif req.tag == "c1":
        rows.append((tr("Drive"), tr("Fastest burst")))
    rows.append((tr("Photos"), str(req.count)))
    return rows
