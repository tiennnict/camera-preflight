"""Default verdict parameters ``default-1`` with evidence labels (FR-TST-05, NFR-08).

Every threshold is a named parameter. Values labelled Guess are to be calibrated on real
cameras (V-07); they are not facts.
"""

from __future__ import annotations

from .enums import Label
from .models import Param, ParameterSet

_G, _I, _S = Label.GUESS, Label.INFERENCE, Label.SOURCED


def _p(name: str, value: float | int | str | bool, label: Label, note: str = "") -> Param:
    return Param(name=name, value=value, label=label, note=note)


DEFAULT_1 = ParameterSet(
    id="default-1",
    params=(
        # Acceptance gate (TEST-CATALOGUE section 1)
        _p(
            "gate.exposure_tol_ratio", 1.15, _G, "allowed ratio between requested and read exposure"
        ),
        _p(
            "gate.aperture_tol_ratio", 1.12, _G, "allowed ratio between requested and read f-number"
        ),
        _p("gate.flat_hist_lo", 0.50, _G, "flat frame mean, fraction of usable range"),
        _p("gate.flat_hist_hi", 0.80, _G, "flat frame mean, fraction of usable range"),
        _p("gate.clip_share_max", 0.0001, _G, "share of pixels at white level"),
        _p("gate.flicker_amp_max", 0.01, _G, "relative amplitude of periodic row banding"),
        _p(
            "gate.flicker_max_exposure_s",
            1 / 250,
            _I,
            "flicker rule applies at this speed or faster",
        ),
        _p("gate.dark_mean_max_frac", 0.01, _G, "dark mean above black level, fraction of range"),
        _p("gate.dark_leak_max_frac", 0.004, _G, "dark frame quadrant spread, fraction of range"),
        # B1 to B3 pixel defects
        _p("b1.k_sigma", 6.0, _G, "outlier threshold in robust sigmas"),
        _p("b1.min_excess_dn", 8.0, _G, "minimum excess over neighbours, DN"),
        _p("b1.repeat_min", 2, _G, "hot pixel must repeat in this many frames of a set"),
        _p("b1.allowance_per_mp", 5.0, _G, "isolated hot pixels tolerated per megapixel"),
        _p("b1.cluster_distance_px", 2, _I, "defects closer than this are one cluster"),
        _p("b2.rel_dev", 0.25, _G, "flat frame deviation from neighbours, relative"),
        _p(
            "b3.hot_growth_ratio", 1.5, _I, "excess growth between exposures that marks a hot pixel"
        ),
        # B4 dust, B5 uniformity, B6 noise
        _p("b4.blob_depth", 0.05, _G, "relative darkening that marks a mark"),
        _p("b4.min_area_px", 6, _G, "smallest mark, binned pixels"),
        _p("b4.heavy_count", 25, _G, "marks counted as heavy dust"),
        _p("b4.sensor_side_ratio", 0.5, _I, "depth at wide aperture / depth at small aperture"),
        _p("b4.linear_elongation", 6.0, _G, "major / minor axis of a linear mark"),
        _p("b4.linear_min_len_px", 25, _G, "shortest linear mark, binned pixels"),
        _p("b5.stripe_amp", 0.01, _G, "row or column profile amplitude after trend removal"),
        _p("b5.cast", 0.03, _G, "colour ratio deviation across the frame"),
        _p("b5.asymmetry", 0.04, _G, "left-right brightness asymmetry"),
        _p("b6.banding_ratio", 3.0, _G, "banding amplitude over the amplitude expected from noise"),
        _p("b6.banding_min_dn", 0.3, _G, "smallest banding amplitude reported, DN"),
        # C shutter
        _p("c1.stall_factor", 2.5, _G, "interval over median interval that marks a stall"),
        _p("c1.cv_max", 0.25, _G, "variation of burst intervals"),
        _p("c1.min_frames", 6, _G, "frames needed for burst rhythm"),
        _p("c1.fps_ratio_min", 0.8, _G, "measured over rated burst speed"),
        _p("c1.min_resolution_s", 0.01, _I, "timestamp resolution needed"),
        _p("c2.gradient_max", 0.02, _G, "curtain gradient along the travel axis, relative"),
        _p("c3.spread_ev_max", 0.1, _G, "spread of mean level over identical frames"),
        # D autofocus
        _p("af.timeout_s", 5.0, _G, "focus not acquired within this time"),
        _p("af.attempts", 3, _G, "attempts per point"),
        _p("af.fail_attempts", 2, _G, "failed attempts that make a point suspect"),
        _p("af.soft_ratio", 0.5, _G, "sharpness over reference sharpness"),
        _p("af.repeat_cv", 0.3, _I, "spread of sharpness across repeats"),
        # E metering
        _p("e1.spread_ev", 1 / 3, _G, "exposure spread across identical scenes"),
        _p("e2.mode_dev_ev", 0.5, _I, "difference between metering modes"),
        _p("e3.min_change_ev", 0.7, _I, "exposure change when the metered region changes"),
        _p("e4.mid_grey", 0.18, _S, "nominal mid-grey reflectance"),
        _p("e5.nonlinear_ev", 0.25, _I, "deviation from a straight line, compensation series"),
        _p("e6.jump_ev", 0.3, _I, "deviation from proportional level, ISO series"),
        _p("e7.step_ev", 0.25, _I, "deviation from expected brightness fall, aperture series"),
        # Shutter count plausibility (N-03)
        _p("count.rated_share_warn", 0.8, _G, "share of rated life that is shown as a warning"),
    ),
)

__all__ = ["DEFAULT_1"]
