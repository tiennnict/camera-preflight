"""Shutter count plausibility cross-checks (N-03, FR-REP-07).

Shown separately from the shutter count verdict. Each note states its basis; none is proof.
"""

from __future__ import annotations

from datetime import datetime

from ..domain import Frame, Message
from ..knowledge import ModelEntry


def plausibility_notes(
    count: int | None,
    frames: list[Frame],
    kb: ModelEntry | None,
    today: datetime | None = None,
) -> list[Message]:
    notes: list[Message] = []
    if count is None:
        return notes
    today = today or datetime.now()
    numbers = [f.meta.file_number for f in frames if f.meta.file_number is not None]
    if numbers and count < max(numbers) and max(numbers) < 9999:
        notes.append(
            Message(
                code="plausibility.below_file_number",
                params={"count": str(count), "file_number": str(max(numbers))},
            )
        )
    if count == 0 and numbers:
        notes.append(Message(code="plausibility.zero_with_files"))
    if kb and kb.release_year:
        years = max(today.year - kb.release_year, 1)
        per_year = count / years
        if per_year > 50_000:
            notes.append(
                Message(
                    code="plausibility.heavy_use",
                    params={"per_year": str(int(per_year)), "years": str(years)},
                )
            )
        if count < 100 and years >= 5:
            notes.append(Message(code="plausibility.unused", params={"years": str(years)}))
    return notes
