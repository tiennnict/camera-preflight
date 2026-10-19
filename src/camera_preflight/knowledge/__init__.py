"""Knowledge base: curated tier (YAML) and derived tier (from the session's frames)."""

from .derived import (
    DerivedRecord,
    Resolved,
    derive_record,
    resolve_af_point_count,
    resolve_burst_fps,
    resolve_rated_life,
)
from .loader import KnowledgeBase, bundled_kb_root, default_kb, load_entry, load_kb, normalise_name
from .models import (
    SCHEMA_VERSION,
    AfLayout,
    AfPointSpec,
    KnownIssue,
    ModelEntry,
    SerialRange,
    SourcedValue,
)

__all__ = [
    "SCHEMA_VERSION",
    "AfLayout",
    "AfPointSpec",
    "DerivedRecord",
    "KnowledgeBase",
    "KnownIssue",
    "ModelEntry",
    "Resolved",
    "SerialRange",
    "SourcedValue",
    "bundled_kb_root",
    "default_kb",
    "derive_record",
    "load_entry",
    "load_kb",
    "normalise_name",
    "resolve_af_point_count",
    "resolve_burst_fps",
    "resolve_rated_life",
]
