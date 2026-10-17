"""Helper polling with the button fallback after a time limit (FR-ACQ-11)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ..backends.protocol import BackendError, CameraBackend
from . import detectors as d

Clock = Callable[[], float]


@dataclass
class HelperState:
    detected: bool = False
    button_visible: bool = False  # the helper keeps watching after this turns on
    unavailable: bool = False  # the body gives no live view: button only
    elapsed_s: float = 0.0


@dataclass
class HelperWatcher:
    """Call ``poll`` on a timer. ``helper`` is one of H1 to H7."""

    helper: str
    backend: CameraBackend
    params: d.HelperParams = field(default_factory=d.HelperParams)
    clock: Clock = time.monotonic
    initial_lens: str | None = None
    initial_storage: tuple[str, ...] = ()
    wanted_focus: str = "AF"

    def __post_init__(self) -> None:
        self._start = self.clock()
        self._prev: d.Frame | None = None
        self.state = HelperState()
        caps = self.backend.capabilities()
        needs_live = self.helper in {"H1", "H2", "H3", "H4"}
        if needs_live and not caps.live_view:
            self.state.unavailable = True
            self.state.button_visible = True

    def poll(self) -> HelperState:
        st = self.state
        st.elapsed_s = self.clock() - self._start
        if st.elapsed_s >= self.params.timeout_s:
            st.button_visible = True
        if st.unavailable or st.detected:
            return st
        try:
            hit = self._check()
        except BackendError:
            st.unavailable = True
            st.button_visible = True
            return st
        if hit is None:
            st.unavailable = True
            st.button_visible = True
        elif hit:
            st.detected = True
        return st

    def _frame(self) -> d.Frame | None:
        raw = self.backend.live_view_frame()
        return None if raw is None else np.asarray(raw, dtype=np.uint8)

    def _check(self) -> bool | None:
        h = self.helper
        if h in {"H1", "H2", "H3"}:
            f = self._frame()
            if f is None:
                return None
            return {"H1": d.h1_dark, "H2": d.h2_flat, "H3": d.h3_chart}[h](f, self.params)
        if h == "H4":
            f = self._frame()
            if f is None:
                return None
            prev, self._prev = self._prev, f
            return False if prev is None else d.h4_steady(prev, f, self.params)
        if h == "H5":
            return d.h5_lens_changed(self.initial_lens, self.backend.device_info().lens)
        if h == "H7":
            return d.h7_card_present(self.initial_storage, self.backend.device_info().storage)
        if h == "H6":
            return None  # focus mode is not readable through the standard backend (V-22)
        raise ValueError(h)

    def press_button(self) -> None:
        """The user confirms the action by hand."""
        self.state.detected = True
