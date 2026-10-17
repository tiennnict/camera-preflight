"""A pretend PTP camera for tests: answers the standard operations over a Transport."""

from __future__ import annotations

import struct

from camera_preflight.backends.ptp import codec


class FakePtpCamera:
    def __init__(
        self, manufacturer="Canon Inc.", model="EOS Test", serial="1234567", focus_ok=True
    ):
        self.info = codec.DeviceInfoData(
            standard_version=100,
            operations=[
                codec.OP_GET_DEVICE_INFO,
                codec.OP_OPEN_SESSION,
                codec.OP_CLOSE_SESSION,
                codec.OP_GET_STORAGE_IDS,
                codec.OP_GET_OBJECT_HANDLES,
                codec.OP_GET_OBJECT_INFO,
                codec.OP_GET_OBJECT,
                codec.OP_INITIATE_CAPTURE,
                codec.OP_GET_PROP_VALUE,
                codec.OP_SET_PROP_VALUE,
            ],
            properties=[
                codec.PROP_BATTERY,
                codec.PROP_ISO,
                codec.PROP_EXPOSURE_TIME,
                codec.PROP_FNUMBER,
                0xD1AC,
            ],
            manufacturer=manufacturer,
            model=model,
            device_version="3-1.1.0",
            serial=serial,
        )
        self.props = {
            codec.PROP_BATTERY: (b"B", 77),
            codec.PROP_ISO: (b"H", 100),
            codec.PROP_EXPOSURE_TIME: (b"I", 125),
            codec.PROP_FNUMBER: (b"H", 560),
            0xD1AC: (b"I", 4321),
        }
        self.objects: dict[int, tuple[str, bytes]] = {}
        self.focus_ok = focus_ok
        self.queue: list[bytes] = []
        self.sent_props: list[tuple[int, int]] = []
        self.closed = False

    def send(self, data: bytes) -> None:
        c = codec.Container.unpack(data)
        if c.type == codec.CMD:
            self._cmd = c
            if c.code != codec.OP_SET_PROP_VALUE:
                self._respond(c, b"")
        elif c.type == codec.DATA and self._cmd.code == codec.OP_SET_PROP_VALUE:
            prop = self._cmd.params[0]
            fmt = self.props[prop][0].decode()
            (val,) = struct.unpack("<" + fmt, c.payload[: struct.calcsize(fmt)])
            self.props[prop] = (self.props[prop][0], val)
            self.sent_props.append((prop, val))
            self._reply(self._cmd, codec.RC_OK)

    def _reply(self, c, code, data=b""):
        if data:
            self.queue.append(codec.Container(codec.DATA, c.code, c.transaction, (), data).pack())
        self.queue.append(codec.Container(codec.RESP, code, c.transaction).pack())

    def _respond(self, c, _):
        op = c.code
        if op == codec.OP_OPEN_SESSION:
            self._reply(c, codec.RC_OK)
        elif op == codec.OP_GET_DEVICE_INFO:
            self._reply(c, codec.RC_OK, codec.build_device_info(self.info))
        elif op == codec.OP_GET_STORAGE_IDS:
            self._reply(c, codec.RC_OK, struct.pack("<II", 1, 0x10001))
        elif op == codec.OP_GET_OBJECT_HANDLES:
            hs = sorted(self.objects)
            self._reply(c, codec.RC_OK, struct.pack(f"<I{len(hs)}I", len(hs), *hs))
        elif op == codec.OP_GET_OBJECT_INFO:
            name, data = self.objects[c.params[0]]
            head = bytearray(52)
            struct.pack_into("<I", head, 8, len(data))
            self._reply(c, codec.RC_OK, bytes(head) + codec.pack_string(name))
        elif op == codec.OP_GET_OBJECT:
            self._reply(c, codec.RC_OK, self.objects[c.params[0]][1])
        elif op == codec.OP_GET_PROP_VALUE:
            fmt, val = self.props[c.params[0]]
            self._reply(c, codec.RC_OK, struct.pack("<" + fmt.decode(), val))
        elif op == codec.OP_INITIATE_CAPTURE:
            if self.focus_ok:
                h = len(self.objects) + 1
                self.objects[h] = (f"IMG_{h:04d}.CR2", b"RAWDATA" * 10)
                self._reply(c, codec.RC_OK)
            else:
                self._reply(c, codec.RC_DEVICE_BUSY)
        elif op == codec.OP_CLOSE_SESSION:
            self.closed = True
            self._reply(c, codec.RC_OK)
        else:
            self._reply(c, codec.RC_GENERAL_ERROR)

    def receive(self, timeout_s: float) -> bytes:
        return self.queue.pop(0)

    def close(self) -> None:
        pass
