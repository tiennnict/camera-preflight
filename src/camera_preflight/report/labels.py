"""Fixed report texts (translated at render time)."""

from __future__ import annotations

from ..i18n import N_

LABELS: dict[str, str] = {
    "title": N_("Camera check report"),
    "created": N_("Created"),
    "language": N_("Report language"),
    "camera": N_("Camera"),
    "brand": N_("Brand"),
    "model": N_("Model"),
    "serial": N_("Serial (last 4)"),
    "firmware": N_("Firmware"),
    "lens": N_("Lens"),
    "count_before": N_("Shutter count before"),
    "count_after": N_("Shutter count after"),
    "temperature": N_("Sensor temperature"),
    "unknown": N_("Unknown"),
    "summary": N_("Summary"),
    "blockers": N_("Blockers"),
    "flagged": N_("Suspect and fail results"),
    "none_flagged": N_("Nothing suspect or failed."),
    "all_results": N_("All results"),
    "not_tested": N_("Not tested"),
    "reason": N_("Reason"),
    "ask": N_("Ask the seller"),
    "method": N_("Method"),
    "app_version": N_("App version"),
    "kb_version": N_("Knowledge base version"),
    "parameter_set": N_("Parameter set"),
    "thresholds": N_("Thresholds used"),
    "parameter": N_("Parameter"),
    "value": N_("Value"),
    "evidence_label": N_("Evidence label"),
    "frames": N_("Source files"),
    "evidence_files": N_("Evidence images"),
    "file": N_("File"),
    "sha256": N_("SHA-256"),
    "hash_note": N_(
        "Hashes show file integrity only. They do not prove the files were not altered."
    ),
    "disclaimer": N_(
        "This report lists measurements and suspected issues. It gives no buying or price advice."
    ),
    "confidence": N_("Confidence"),
    "path": N_("Path"),
    "severity": N_("Severity"),
    "findings": N_("Details"),
    "more_findings": N_("more not shown"),
    "label.Sourced": N_("Sourced"),
    "label.Inference": N_("Inference"),
    "label.Guess": N_("Guess"),
    "label.Unverified": N_("Unverified"),
    "session_issues": N_("Photo checks"),
    "known_issues": N_("Known issues of this model"),
}
