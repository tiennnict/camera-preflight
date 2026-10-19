"""Load and validate curated entries (FR-KB-01, FR-KB-06, NFR-16: safe YAML only)."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import AfLayout, ModelEntry


def normalise_name(brand: str | None, model: str | None) -> str:
    text = f"{brand or ''} {model or ''}".lower()
    text = re.sub(r"\b(canon|nikon|sony|corporation|eos|digital|camera)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def load_entry(path: Path) -> ModelEntry:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ModelEntry.model_validate(data)


def load_layout(path: Path) -> AfLayout:
    return AfLayout.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@dataclass
class KnowledgeBase:
    entries: list[ModelEntry] = field(default_factory=list)
    layouts: dict[str, AfLayout] = field(default_factory=dict)
    _index: dict[str, ModelEntry] = field(default_factory=dict)

    def add(self, entry: ModelEntry) -> None:
        self.entries.append(entry)
        for name in entry.names():
            self._index[normalise_name(entry.brand, name)] = entry

    def find(self, make: str | None, model: str | None) -> ModelEntry | None:
        key = normalise_name(make, model)
        if key in self._index:
            return self._index[key]
        # Metadata often carries the model without the brand, or with a different brand string.
        for brand in ("Canon", "Nikon", "Sony"):
            alt = normalise_name(brand, model)
            if alt in self._index:
                return self._index[alt]
        return None


def load_kb(root: Path) -> tuple[KnowledgeBase, list[str]]:
    """Load every entry under ``root``; returns the base and a list of problems."""
    kb = KnowledgeBase()
    problems: list[str] = []
    layouts_dir = root / "layouts"
    if layouts_dir.is_dir():
        for p in sorted(layouts_dir.glob("*.yaml")):
            try:
                kb.layouts[p.stem] = load_layout(p)
            except (ValidationError, yaml.YAMLError, OSError) as exc:
                problems.append(f"{p}: {exc}")
    for brand in ("canon", "nikon", "sony"):
        for p in sorted((root / brand).glob("*.yaml")) if (root / brand).is_dir() else []:
            try:
                entry = load_entry(p)
            except (ValidationError, yaml.YAMLError, OSError) as exc:
                problems.append(f"{p}: {exc}")
                continue
            if entry.brand.lower() != brand:
                problems.append(f"{p}: brand {entry.brand} does not match folder {brand}")
            if entry.af.layout_ref and entry.af.layout_ref not in kb.layouts:
                problems.append(f"{p}: unknown AF layout {entry.af.layout_ref!r}")
            if entry.release_year and not entry.release_year_source:
                problems.append(f"{p}: release_year needs release_year_source (FR-KB-02)")
            kb.add(entry)
    return kb, problems


def bundled_kb_root() -> Path:
    """The ``knowledge-base`` folder: next to the executable's data in a frozen build, the
    repository root otherwise."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen) / "knowledge-base"
    return Path(__file__).resolve().parents[3] / "knowledge-base"


@lru_cache(maxsize=1)
def default_kb() -> KnowledgeBase:
    """The curated base shipped with the app; empty when the folder is missing. Entries with
    problems are left out (the validator reports them in CI)."""
    root = bundled_kb_root()
    if not root.is_dir():
        return KnowledgeBase()
    kb, _problems = load_kb(root)
    return kb
