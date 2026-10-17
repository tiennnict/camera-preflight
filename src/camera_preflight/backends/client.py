"""Client for the backend host: starts the process and speaks JSON lines (FR-CON-08)."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from ..domain import DeviceInfo
from .protocol import (
    BackendError,
    Capabilities,
    CaptureOutcome,
    CaptureSettings,
    CommandFailed,
    Disconnected,
    NotSupported,
    RemoteFile,
)

_ERRORS = {
    "backend.not_supported": NotSupported,
    "backend.command_failed": CommandFailed,
    "backend.disconnected": Disconnected,
}


class BackendClient:
    """Implements ``CameraBackend`` by calling the host process."""

    def __init__(
        self, spec: str, *, sdk_dir: Path | None = None, workdir: Path | None = None
    ) -> None:
        self.name = f"host:{spec}"
        cmd = [sys.executable, "-m", "camera_preflight.backends.host", "--backend", spec]
        if sdk_dir:
            cmd += ["--sdk-dir", str(sdk_dir)]
        if workdir:
            cmd += ["--workdir", str(workdir)]
        flags = 0x08000000 if os.name == "nt" else 0
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=flags,
        )
        self._lock = threading.Lock()
        self._next = 0

    def call(self, method: str, **params: Any) -> Any:
        with self._lock:
            if self._proc.poll() is not None:
                raise Disconnected("backend host has ended")
            self._next += 1
            msg = {"id": self._next, "method": method, "params": params}
            assert self._proc.stdin is not None and self._proc.stdout is not None
            try:
                self._proc.stdin.write(json.dumps(msg) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
            except (BrokenPipeError, OSError) as exc:
                raise Disconnected(str(exc)) from exc
            if not line:
                raise Disconnected("backend host closed the connection")
        reply = json.loads(line)
        if "error" in reply:
            exc_type = _ERRORS.get(reply["error"]["code"], BackendError)
            raise exc_type(reply["error"]["message"])
        return reply["result"]

    # ---- CameraBackend ----------------------------------------------------------------
    def open(self) -> None:
        self.call("open")

    def close(self) -> None:
        try:
            self.call("close")
        except BackendError:
            pass
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        # A host that already ended leaves unflushed text in the stdin wrapper; closing it here
        # keeps the error out of the garbage collector.
        for pipe in (self._proc.stdin, self._proc.stdout):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass

    def capabilities(self) -> Capabilities:
        data = self.call("capabilities")
        data["sdk_features"] = tuple(data.get("sdk_features", ()))
        return Capabilities(**data)

    def device_info(self) -> DeviceInfo:
        return DeviceInfo.model_validate(self.call("device_info"))

    def snapshot_settings(self) -> dict[str, Any]:
        return dict(self.call("snapshot_settings"))

    def apply_settings(self, settings: CaptureSettings) -> None:
        self.call("apply_settings", settings=asdict(settings))

    def restore_settings(self, snapshot: dict[str, Any]) -> None:
        self.call("restore_settings", snapshot=snapshot)

    def capture(self, settings: CaptureSettings, timeout_s: float) -> CaptureOutcome:
        data = self.call("capture", settings=asdict(settings), timeout_s=timeout_s)
        files = [RemoteFile(**f) for f in data.get("files", [])]
        return CaptureOutcome(
            ok=data["ok"],
            files=files,
            focus_failed=data["focus_failed"],
            timed_out=data["timed_out"],
        )

    def download(self, ref: RemoteFile, dest_dir: Path) -> Path:
        return Path(self.call("download", ref=asdict(ref), dest_dir=str(dest_dir)))

    def live_view_frame(self) -> np.ndarray | None:
        data = self.call("live_view_frame")
        if data is None:
            return None
        raw = base64.b64decode(data["data"])
        return np.frombuffer(raw, dtype=np.uint8).reshape(data["shape"])

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None
