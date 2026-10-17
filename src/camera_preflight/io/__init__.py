"""Input and output: RAW decoding, metadata, upload and session folder."""

from .errors import ExifToolMissing, IoError, MetadataError, RawDecodeError, UnsupportedFormat
from .exiftool import ExifToolReader, find_exiftool
from .metadata import MetadataReader, normalise
from .raw import decode_raw, is_jpeg, is_raw
from .session import SessionFolder, atomic_write, make_frame, sha256_of
from .tiffmeta import TiffMetadataReader


def default_reader() -> MetadataReader:
    """Bundled ExifTool when present, else the in-house reader (D-42)."""
    if find_exiftool():
        try:
            return ExifToolReader()
        except ExifToolMissing:
            pass
    return TiffMetadataReader()


__all__ = [
    "ExifToolMissing",
    "ExifToolReader",
    "IoError",
    "MetadataError",
    "MetadataReader",
    "RawDecodeError",
    "SessionFolder",
    "TiffMetadataReader",
    "UnsupportedFormat",
    "atomic_write",
    "decode_raw",
    "default_reader",
    "find_exiftool",
    "is_jpeg",
    "is_raw",
    "make_frame",
    "normalise",
    "sha256_of",
]
