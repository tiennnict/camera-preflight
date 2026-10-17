"""PTP session: transactions and the standard operations."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ..protocol import CommandFailed
from . import codec
from .transport import Transport


@dataclass
class Response:
    code: int
    params: tuple[int, ...]
    data: bytes


class PtpSession:
    def __init__(self, transport: Transport, timeout_s: float = 10.0) -> None:
        self.t = transport
        self.timeout = timeout_s
        self._tid = 0
        self.opened = False

    def transact(
        self,
        op: int,
        params: tuple[int, ...] = (),
        data: bytes | None = None,
        timeout_s: float | None = None,
    ) -> Response:
        self._tid += 1
        tid = self._tid
        self.t.send(codec.Container(codec.CMD, op, tid, params).pack())
        if data is not None:
            self.t.send(codec.Container(codec.DATA, op, tid, (), data).pack())
        payload = b""
        wait = timeout_s or self.timeout
        while True:
            raw = self.t.receive(wait)
            c = codec.Container.unpack(raw)
            if c.type == codec.DATA:
                payload += c.payload
            elif c.type == codec.RESP:
                return Response(c.code, c.params, payload)
            # events are ignored here

    def ok(self, op: int, params: tuple[int, ...] = (), data: bytes | None = None) -> Response:
        r = self.transact(op, params, data)
        if r.code != codec.RC_OK:
            raise CommandFailed(f"PTP operation 0x{op:04X} returned 0x{r.code:04X}")
        return r

    # ---- standard operations ---------------------------------------------------------------
    def open(self, session_id: int = 1) -> None:
        r = self.transact(codec.OP_OPEN_SESSION, (session_id,))
        if r.code not in (codec.RC_OK, 0x201E):  # 0x201E: session already open
            raise CommandFailed(f"OpenSession returned 0x{r.code:04X}")
        self.opened = True

    def close(self) -> None:
        if self.opened:
            self.transact(codec.OP_CLOSE_SESSION)
            self.opened = False

    def device_info(self) -> codec.DeviceInfoData:
        return codec.parse_device_info(self.ok(codec.OP_GET_DEVICE_INFO).data)

    def get_prop(self, prop: int, fmt: str = "<H") -> int:
        data = self.ok(codec.OP_GET_PROP_VALUE, (prop,)).data
        return int(struct.unpack_from(fmt, data)[0])

    def set_prop(self, prop: int, value: int, fmt: str = "<H") -> None:
        self.ok(codec.OP_SET_PROP_VALUE, (prop,), struct.pack(fmt, value))

    def storage_ids(self) -> list[int]:
        data = self.ok(codec.OP_GET_STORAGE_IDS).data
        (n,) = struct.unpack_from("<I", data)
        return list(struct.unpack_from(f"<{n}I", data, 4))

    def object_handles(self, storage: int = 0xFFFFFFFF) -> list[int]:
        data = self.ok(codec.OP_GET_OBJECT_HANDLES, (storage, 0, 0)).data
        (n,) = struct.unpack_from("<I", data)
        return list(struct.unpack_from(f"<{n}I", data, 4))

    def object_name(self, handle: int) -> tuple[str, int]:
        """File name and size from the ObjectInfo dataset."""
        data = self.ok(codec.OP_GET_OBJECT_INFO, (handle,)).data
        size = struct.unpack_from("<I", data, 8)[0]
        name, _ = codec.read_string(data, 52)
        return name, size

    def get_object(self, handle: int) -> bytes:
        return self.ok(codec.OP_GET_OBJECT, (handle,)).data

    def initiate_capture(self) -> None:
        self.ok(codec.OP_INITIATE_CAPTURE, (0, 0))
