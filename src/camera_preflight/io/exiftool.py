"""ExifTool metadata reader in ``-stay_open`` mode (P-05, D-42).

ExifTool is bundled with the release (``exiftool/`` next to the executable). Only allowlisted
tags are requested, so personal fields never reach the session (FR-META-02).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from ..domain import FrameMeta
from .errors import ExifToolMissing, MetadataError
from .fields import ALL_TAGS
from .metadata import normalise

_ENV = "CAMERA_PREFLIGHT_EXIFTOOL"
_READY = "{ready}"


def find_exiftool() -> list[str] | None:
    """Command line prefix for the bundled ExifTool, or None.

    Search order: environment override, the bundle next to the executable, then PATH (for
    development only; the user is never asked to supply ExifTool, D-42).
    """
    override = os.environ.get(_ENV)
    if override and Path(override).exists():
        return [override]
    roots: list[Path] = []
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        roots.append(Path(frozen))
    roots.append(Path(sys.executable).parent)
    roots.append(Path(__file__).resolve().parents[3] / "packaging" / "exiftool" / "bundle")
    for root in roots:
        for rel in ("exiftool/exiftool.exe", "exiftool/exiftool", "exiftool.exe"):
            candidate = root / rel
            if candidate.exists():
                return [str(candidate)]
    found = shutil.which("exiftool")
    return [found] if found else None


class ExifToolReader:
    name = "exiftool"

    def __init__(self, command: list[str] | None = None) -> None:
        cmd = command or find_exiftool()
        if not cmd:
            raise ExifToolMissing("exiftool not found")
        self._cmd = cmd
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None

    def _start(self) -> subprocess.Popen[str]:
        if self._proc and self._proc.poll() is None:
            return self._proc
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        self._proc = subprocess.Popen(
            [*self._cmd, "-stay_open", "True", "-@", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        return self._proc

    def _run(self, args: list[str]) -> str:
        with self._lock:
            proc = self._start()
            assert proc.stdin is not None and proc.stdout is not None
            try:
                proc.stdin.write("\n".join([*args, "-execute", ""]))
                proc.stdin.flush()
                lines: list[str] = []
                for line in proc.stdout:
                    if line.strip() == _READY:
                        break
                    lines.append(line)
                else:
                    raise MetadataError("exiftool ended unexpectedly")
            except (BrokenPipeError, OSError) as exc:
                self._proc = None
                raise MetadataError(str(exc)) from exc
        return "".join(lines)

    def read(self, path: Path) -> FrameMeta:
        args = ["-j", "-n", *(f"-{tag}" for tag in ALL_TAGS), str(path)]
        out = self._run(args)
        try:
            data = json.loads(out)[0]
        except (json.JSONDecodeError, IndexError) as exc:
            raise MetadataError(f"cannot parse metadata for {path.name}") from exc
        return normalise({k: v for k, v in data.items() if k != "SourceFile"})

    def version(self) -> str:
        out = subprocess.run([*self._cmd, "-ver"], capture_output=True, text=True, timeout=15)
        return out.stdout.strip()

    def close(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc and proc.poll() is None and proc.stdin:
            try:
                proc.stdin.write("-stay_open\nFalse\n")
                proc.stdin.flush()
                proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                proc.kill()
