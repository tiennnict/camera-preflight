"""Session folder and per-step upload (FR-SES-01, FR-SES-03, FR-SES-04, FR-ACQ-02).

Layout (SRS section 6.1)::

    <sessions>/<yyyymmdd-hhmmss>-<model>-<serial-suffix>/
      session.json  frames/  frames.json  evidence/  results.json  report.html
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..domain import Frame, FrameMeta, Provenance

SERIAL_SUFFIX = 4


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-") or "camera"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write through a temporary file and rename, so a crash never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    mode = "wb" if isinstance(data, bytes) else "w"
    with tmp.open(mode, **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as fh:  # type: ignore[arg-type]
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class SessionFolder:
    def __init__(self, path: Path, started: datetime) -> None:
        self.path = path
        self.started = started
        self.frames_dir = path / "frames"
        self.evidence_dir = path / "evidence"
        self._counter = 0

    @classmethod
    def create(cls, root: Path, started: datetime | None = None) -> SessionFolder:
        started = started or datetime.now()
        stamp = started.strftime("%Y%m%d-%H%M%S")
        path = root / f"{stamp}-pending"
        n = 1
        while path.exists():
            n += 1
            path = root / f"{stamp}-pending-{n}"
        (path / "frames").mkdir(parents=True)
        (path / "evidence").mkdir()
        return cls(path, started)

    def identify(self, model: str | None, serial: str | None) -> None:
        """Rename the folder once the body is known (atomic rename inside the same parent)."""
        suffix = (serial or "")[-SERIAL_SUFFIX:]
        name = "-".join(
            p
            for p in (self.started.strftime("%Y%m%d-%H%M%S"), _slug(model or "camera"), suffix)
            if p
        )
        target = self.path.with_name(name)
        n = 1
        while target.exists() and target != self.path:
            n += 1
            target = self.path.with_name(f"{name}-{n}")
        if target != self.path:
            os.replace(self.path, target)
            self.path = target
            self.frames_dir = target / "frames"
            self.evidence_dir = target / "evidence"

    def import_file(self, src: Path) -> tuple[Path, str]:
        """Copy a user-selected file into ``frames/``; the original is never touched (FR-SES-04)."""
        digest = sha256_of(src)
        self._counter += 1
        dest = self.frames_dir / f"{self._counter:04d}-{_slug(src.stem)}{src.suffix.lower()}"
        shutil.copyfile(src, dest)
        dest.chmod(stat.S_IREAD)
        return dest, digest

    def write_json(self, name: str, payload: Any) -> None:
        if isinstance(payload, BaseModel):
            payload = json.loads(payload.model_dump_json())
        atomic_write(
            self.path / name, json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        )

    def write_frames_index(self, frames: list[Frame]) -> None:
        self.write_json(
            "frames.json",
            [
                {
                    "id": f.id,
                    "file": f.source.name,
                    "sha256": f.sha256,
                    "kind": f.kind.value,
                    "meta": json.loads(f.meta.model_dump_json()),
                    "accepted": f.accepted,
                    "rejection": f.rejection.model_dump(mode="json") if f.rejection else None,
                }
                for f in frames
            ],
        )

    def evidence_path(self, name: str) -> Path:
        return self.evidence_dir / name


def make_frame(frame_id: str, copied: Path, digest: str, meta: FrameMeta) -> Frame:
    return Frame(
        id=frame_id,
        sha256=digest,
        source=copied,
        meta=meta,
        provenance=Provenance(
            serial=meta.serial,
            capture_time=meta.capture_time,
            file_number=meta.file_number,
            edit_flags=(),
        ),
    )
