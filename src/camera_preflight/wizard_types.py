"""Types shared between the acquisition and wizard layers (kept free of imports from either)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol


class IngestResult(Protocol):
    """Outcome of validating one file (the wizard's ``IngestOutcome`` satisfies this)."""

    @property
    def accepted(self) -> bool: ...


IngestFn = Callable[[Path, Any, Any, str, Sequence[Any], Any, str | None], IngestResult]
