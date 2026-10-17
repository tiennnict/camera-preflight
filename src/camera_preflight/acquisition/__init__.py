"""Acquisition: connected capture with retry and manual fallback."""

from .runner import ConnectedRunner, ManualFallback, settings_for

__all__ = ["ConnectedRunner", "ManualFallback", "settings_for"]
