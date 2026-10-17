"""Knowledge base: curated tier (YAML) and derived tier (from the session's frames)."""

from .derived import (
    DerivedRecord,
    Resolved,
    derive_record,
    resolve_af_point_count,
    resolve_burst_fps,
    resolve_rated_life,
)
from .loader import KnowledgeBase, load_entry, load_kb, normalise_name
from .models import (
    SCHEMA_VERSION,
    AfLayout,
    AfPointSpec,
    KnownIssue,
    ModelEntry,
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
    "SourcedValue",
    "derive_record",
    "load_entry",
    "load_kb",
    "normalise_name",
    "resolve_af_point_count",
    "resolve_burst_fps",
    "resolve_rated_life",
]
