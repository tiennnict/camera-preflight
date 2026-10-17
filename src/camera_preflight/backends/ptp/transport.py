"""Transports for PTP: bulk endpoints over libusb (R-03, second candidate after WPD)."""

from __future__ import annotations

from typing import Protocol

from ..protocol import BackendError, Disconnected


class Transport(Protocol):
    """Moves whole PTP containers. Implementations: ``UsbTransport``; a fake in the tests."""

    def send(self, data: bytes) -> None: ...

    def receive(self, timeout_s: float) -> bytes: ...

    def close(self) -> None: ...


class UsbTransport:
    """PTP over libusb or WinUSB through pyusb.

    [Unverified] Needs the WinUSB driver bound to the camera on Windows (Zadig). The WPD
    transport, which needs no driver change, is evaluated first in the spike (WP-40).
    """

    PTP_CLASS = 6

    def __init__(self, vid: int | None = None, pid: int | None = None) -> None:
        try:
            import usb.core  # type: ignore[import-not-found]
            import usb.util  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BackendError("pyusb is not installed") from exc
        self._usb = usb
        dev = self._find(usb.core, vid, pid)
        if dev is None:
            raise Disconnected("no PTP device found")
        dev.set_configuration()
        cfg = dev.get_active_configuration()
        intf = next(i for i in cfg if i.bInterfaceClass == self.PTP_CLASS)
        self._dev = dev
        self._out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            ),
        )
        self._in = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            ),
        )

    def _find(self, core, vid: int | None, pid: int | None):  # type: ignore[no-untyped-def]
        def is_ptp(dev):  # type: ignore[no-untyped-def]
            for cfg in dev:
                for intf in cfg:
                    if intf.bInterfaceClass == self.PTP_CLASS:
                        return True
            return False

        if vid is not None and pid is not None:
            return core.find(idVendor=vid, idProduct=pid)
        return core.find(custom_match=is_ptp)

    def send(self, data: bytes) -> None:
        try:
            self._out.write(data)
        except Exception as exc:
            raise Disconnected(str(exc)) from exc

    def receive(self, timeout_s: float) -> bytes:
        try:
            chunk = bytes(self._in.read(512 * 1024, int(timeout_s * 1000)))
        except Exception as exc:
            raise Disconnected(str(exc)) from exc
        return chunk

    def close(self) -> None:
        self._usb.util.dispose_resources(self._dev)
