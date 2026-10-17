"""Backend host process: JSON lines over stdin and stdout (P-02, FR-CON-02, NFR-05).

A crash in a native SDK or USB stack ends this process, not the application. Run with
``python -m camera_preflight.backends.host --backend sim``.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .protocol import BackendError, CameraBackend, CaptureSettings


def make_backend(
    spec: str, sdk_dir: str | None = None, workdir: str | None = None
) -> CameraBackend:
    """``sim``, ``sim-faulty``, ``ptp-usb`` or ``sdk:<brand>``."""
    if spec.startswith("sim"):
        from ..synth.backend import SimBackend

        return SimBackend(workdir=Path(workdir) if workdir else None, faulty=spec == "sim-faulty")
    if spec == "ptp-usb":
        from .ptp.backend import open_usb_backend

        return open_usb_backend()
    if spec.startswith("sdk:"):
        from .sdk.loader import open_sdk_backend

        return open_sdk_backend(spec.split(":", 1)[1], Path(sdk_dir) if sdk_dir else None)
    raise BackendError(f"unknown backend {spec!r}")


def _encode(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        arr = np.asarray(value, dtype=np.uint8)
        return {"shape": list(arr.shape), "data": base64.b64encode(arr.tobytes()).decode("ascii")}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def handle(backend: CameraBackend, method: str, params: dict[str, Any]) -> Any:
    from .protocol import RemoteFile

    if method == "open":
        backend.open()
        return True
    if method == "close":
        backend.close()
        return True
    if method == "capabilities":
        return _encode(backend.capabilities())
    if method == "device_info":
        return _encode(backend.device_info())
    if method == "snapshot_settings":
        return backend.snapshot_settings()
    if method == "apply_settings":
        backend.apply_settings(CaptureSettings(**params["settings"]))
        return True
    if method == "restore_settings":
        backend.restore_settings(params["snapshot"])
        return True
    if method == "capture":
        out = backend.capture(CaptureSettings(**params["settings"]), float(params["timeout_s"]))
        return _encode(out)
    if method == "download":
        ref = RemoteFile(**params["ref"])
        return str(backend.download(ref, Path(params["dest_dir"])))
    if method == "sim":
        return backend.sim_command(params["name"], **params.get("args", {}))  # type: ignore[attr-defined]
    if method == "live_view_frame":
        return _encode(backend.live_view_frame())
    raise BackendError(f"unknown method {method!r}")


def serve(backend: CameraBackend, stdin: Any = None, stdout: Any = None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        reply: dict[str, Any] = {"id": msg.get("id")}
        try:
            reply["result"] = handle(backend, msg["method"], msg.get("params", {}))
        except BackendError as exc:
            reply["error"] = {"code": exc.code, "message": str(exc)}
        except Exception as exc:
            reply["error"] = {"code": "backend.error", "message": f"{type(exc).__name__}: {exc}"}
        stdout.write(json.dumps(reply) + "\n")
        stdout.flush()
        if msg.get("method") == "close":
            break


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", required=True)
    p.add_argument("--sdk-dir")
    p.add_argument("--workdir")
    args = p.parse_args(argv)
    backend = make_backend(args.backend, args.sdk_dir, args.workdir)
    serve(backend)
    return 0


if __name__ == "__main__":
    sys.exit(main())
