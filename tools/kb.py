"""Knowledge base tool: validate entries and export the JSON Schema (FR-KB-06).

Usage: python tools/kb.py validate|schema
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge-base"


def validate(root: Path = KB) -> int:
    from camera_preflight.knowledge import load_kb

    kb, problems = load_kb(root)
    for line in problems:
        print(line)
    print(f"{len(kb.entries)} entries, {len(kb.layouts)} layouts, {len(problems)} problems")
    return 1 if problems else 0


def schema(root: Path = KB) -> int:
    from camera_preflight.knowledge import AfLayout, ModelEntry

    out = root / "schema"
    out.mkdir(parents=True, exist_ok=True)
    (out / "model-entry.schema.json").write_text(
        json.dumps(ModelEntry.model_json_schema(), indent=2), encoding="utf-8"
    )
    (out / "af-layout.schema.json").write_text(
        json.dumps(AfLayout.model_json_schema(), indent=2), encoding="utf-8"
    )
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "validate"
    if cmd == "validate":
        return validate()
    if cmd == "schema":
        return schema()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
