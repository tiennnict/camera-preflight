"""Typed errors from the io layer; the wizard turns them into fallbacks (ARCHITECTURE section 7)."""

from __future__ import annotations


class IoError(Exception):
    """Base class; ``code`` is a message code resolved at render time."""

    code = "io.error"

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail or self.code)
        self.detail = detail


class UnsupportedFormat(IoError):
    code = "io.unsupported_format"


class RawDecodeError(IoError):
    code = "io.raw_decode_failed"


class MetadataError(IoError):
    code = "io.metadata_failed"


class ExifToolMissing(MetadataError):
    code = "io.exiftool_missing"
