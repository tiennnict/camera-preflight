"""Synthetic frame generator with defect injection and ground truth."""

from .dng import write_dng
from .sensor import Defects, SensorSpec, synth_chart, synth_dark, synth_flat, truth

__all__ = [
    "Defects",
    "SensorSpec",
    "synth_chart",
    "synth_dark",
    "synth_flat",
    "truth",
    "write_dng",
]
