"""Synthetic frame generator with defect injection and ground truth."""

from .dng import write_dng
from .files import SidecarReader, write_frame, write_session
from .sensor import Defects, SensorSpec, synth_chart, synth_dark, synth_flat, truth
from .session import SynthCamera, af_attempts, build_frames

__all__ = [
    "Defects",
    "SensorSpec",
    "SidecarReader",
    "SynthCamera",
    "af_attempts",
    "build_frames",
    "synth_chart",
    "synth_dark",
    "synth_flat",
    "truth",
    "write_dng",
    "write_frame",
    "write_session",
]
