"""Reference photos of defects with credits (D-33, D-38, FR-GUI-07).

Photos come from openly licensed sources only. ``manifest.json`` lists each photo with its
author, licence and source; ``ATTRIBUTION.md`` repeats the list for the release. A topic with
no photo yet is shown without one; the maintainer adds photos (docs/REFERENCE-IMAGES.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent
MAX_PER_TOPIC = 4


@dataclass(frozen=True)
class ReferencePhoto:
    topic: str
    file: str
    author: str
    licence: str
    source: str

    @property
    def path(self) -> Path:
        return ROOT / self.file

    @property
    def credit(self) -> str:
        return f"{self.author}, {self.licence}"


def load_manifest(path: Path | None = None) -> list[ReferencePhoto]:
    manifest = path or ROOT / "manifest.json"
    if not manifest.exists():
        return []
    items = json.loads(manifest.read_text(encoding="utf-8"))
    return [ReferencePhoto(**item) for item in items]


def photos_for(topic: str, manifest: list[ReferencePhoto] | None = None) -> list[ReferencePhoto]:
    items = manifest if manifest is not None else load_manifest()
    return [p for p in items if p.topic == topic and p.path.exists()][:MAX_PER_TOPIC]


def all_credits(manifest: list[ReferencePhoto] | None = None) -> list[ReferencePhoto]:
    items = manifest if manifest is not None else load_manifest()
    return [p for p in items if p.path.exists()]
