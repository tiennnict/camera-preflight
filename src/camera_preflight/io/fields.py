"""Versioned metadata field allowlist (FR-META-02, NFR-07).

Only the tags named here are ever requested or stored. Owner name, copyright, GPS, Wi-Fi and
similar personal fields are not on the list and are never read into the session.
"""

from __future__ import annotations

ALLOWLIST_VERSION = "1"

# Field name -> ExifTool tag names in priority order.
EXIFTOOL_TAGS: dict[str, tuple[str, ...]] = {
    "make": ("Make",),
    "model": ("Model",),
    "serial": ("SerialNumber", "BodySerialNumber", "CameraSerialNumber", "InternalSerialNumber"),
    "firmware": ("FirmwareVersion", "Firmware", "FirmwareRevision"),
    "lens": ("LensModel", "LensType", "LensID", "Lens"),
    "iso": ("ISO",),
    "exposure_s": ("ExposureTime",),
    "aperture": ("FNumber", "Aperture"),
    "focal_length_mm": ("FocalLength",),
    "exposure_comp_ev": ("ExposureCompensation",),
    "metering_mode": ("MeteringMode",),
    "focus_mode": ("FocusMode",),
    "af_point": ("AFPointSelected", "AFPoint", "AFPointsSelected", "FocusLocation"),
    "af_fine_tune": ("AFFineTuneAdj", "AFFineTune"),
    "shutter_type": ("ShutterType", "ElectronicShutter"),
    "file_type": ("FileType",),
    "file_number": ("FileNumber", "ImageNumber"),
    "shutter_count": ("ShutterCount", "ShutterCount2", "ImageCount"),
    "temperature_c": ("CameraTemperature", "SensorTemperature"),
    "capture_time": ("DateTimeOriginal",),
    "sub_second": ("SubSecTimeOriginal",),
    "long_exposure_nr": ("LongExposureNoiseReduction", "LongExposureNoiseReduction2"),
    "high_iso_nr": ("HighISONoiseReduction", "HighISONoiseReduction2"),
    "software": ("Software",),
    "width": ("ImageWidth",),
    "height": ("ImageHeight",),
}

# Present only to report whether maker notes exist; the content is never read.
MAKER_NOTE_TAG = "MakerNote"

ALL_TAGS: tuple[str, ...] = tuple(
    dict.fromkeys(tag for tags in EXIFTOOL_TAGS.values() for tag in tags)
) + (MAKER_NOTE_TAG,)
