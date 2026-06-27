#!/usr/bin/env python3
"""Write images in BB2 that are missing EXIF DateTimeOriginal."""

from __future__ import annotations

import argparse
import os
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".png",
    ".webp",
}
EXIF_HEADER = b"Exif\x00\x00"
TAG_DATETIME = 0x0132
TAG_EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL = 0x9003
TIFF_TYPE_SIZES = {
    1: 1,  # BYTE
    2: 1,  # ASCII
    3: 2,  # SHORT
    4: 4,  # LONG
    5: 8,  # RATIONAL
    7: 1,  # UNDEFINED
    9: 4,  # SLONG
    10: 8,  # SRATIONAL
}
TAG_NAMES = {
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x011A: "XResolution",
    0x011B: "YResolution",
    0x0128: "ResolutionUnit",
    0x0131: "Software",
    0x0132: "DateTime",
    0x0213: "YCbCrPositioning",
    0x8298: "Copyright",
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8769: "ExifIFDPointer",
    0x8822: "ExposureProgram",
    0x8827: "ISOSpeedRatings",
    0x9000: "ExifVersion",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0x9101: "ComponentsConfiguration",
    0x9201: "ShutterSpeedValue",
    0x9202: "ApertureValue",
    0x9204: "ExposureBiasValue",
    0x9205: "MaxApertureValue",
    0x9207: "MeteringMode",
    0x9208: "LightSource",
    0x9209: "Flash",
    0x920A: "FocalLength",
    0x927C: "MakerNote",
    0x9286: "UserComment",
    0xA000: "FlashpixVersion",
    0xA001: "ColorSpace",
    0xA002: "PixelXDimension",
    0xA003: "PixelYDimension",
    0xA005: "InteroperabilityIFDPointer",
    0xA20E: "FocalPlaneXResolution",
    0xA20F: "FocalPlaneYResolution",
    0xA210: "FocalPlaneResolutionUnit",
    0xA217: "SensingMethod",
    0xA300: "FileSource",
    0xA301: "SceneType",
    0xA401: "CustomRendered",
    0xA402: "ExposureMode",
    0xA403: "WhiteBalance",
    0xA404: "DigitalZoomRatio",
    0xA405: "FocalLengthIn35mmFilm",
    0xA406: "SceneCaptureType",
    0xA407: "GainControl",
    0xA408: "Contrast",
    0xA409: "Saturation",
    0xA40A: "Sharpness",
    0xA40C: "SubjectDistanceRange",
}


@dataclass(frozen=True)
class ExifAttribute:
    ifd: str
    tag: int
    name: str
    value: str


@dataclass(frozen=True)
class ImageInspection:
    path: Path
    date_taken: str | None
    attributes: list[ExifAttribute]
    error: str | None = None


def configure_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def iter_images(root: Path, date_filter: str | None) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Katalogen finns inte: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Inte en katalog: {root}")

    images: list[Path] = []
    for directory, _, file_names in os.walk(root):
        directory_path = Path(directory)
        for file_name in file_names:
            path = directory_path / file_name
            if path.suffix.casefold() in IMAGE_EXTENSIONS:
                if date_filter and date_filter not in path.relative_to(root).as_posix():
                    continue
                images.append(path)

    return sorted(images, key=lambda path: path.relative_to(root).as_posix().casefold())


def read_ascii_value(
    data: bytes,
    byte_order: str,
    value_type: int,
    count: int,
    raw_value: bytes,
) -> str | None:
    if value_type != 2 or count <= 1:
        return None

    size = TIFF_TYPE_SIZES[value_type] * count
    if size <= 4:
        value = raw_value[:size]
    else:
        offset = struct.unpack(byte_order + "I", raw_value)[0]
        if offset < 0 or offset + size > len(data):
            return None
        value = data[offset : offset + size]

    text = value.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
    return text or None


def read_long_value(data: bytes, byte_order: str, value_type: int, raw_value: bytes) -> int | None:
    if value_type == 4:
        return struct.unpack(byte_order + "I", raw_value)[0]
    if value_type == 3:
        return struct.unpack(byte_order + "H", raw_value[:2])[0]
    return None


def entry_value_bytes(
    data: bytes,
    byte_order: str,
    value_type: int,
    count: int,
    raw_value: bytes,
) -> bytes | None:
    type_size = TIFF_TYPE_SIZES.get(value_type)
    if type_size is None or count < 0:
        return None

    size = type_size * count
    if size <= 4:
        return raw_value[:size]

    offset = struct.unpack(byte_order + "I", raw_value)[0]
    if offset < 0 or offset + size > len(data):
        return None
    return data[offset : offset + size]


def rational_text(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return f"{numerator}/0"
    if numerator % denominator == 0:
        return str(numerator // denominator)
    return f"{numerator}/{denominator} ({numerator / denominator:.6g})"


def decode_value(
    data: bytes,
    byte_order: str,
    value_type: int,
    count: int,
    raw_value: bytes,
) -> str:
    value = entry_value_bytes(data, byte_order, value_type, count, raw_value)
    if value is None:
        return "<ogiltigt värde>"

    try:
        if value_type == 2:
            return value.split(b"\x00", 1)[0].decode("ascii", errors="replace")
        if value_type == 3:
            values = struct.unpack(byte_order + "H" * count, value)
            return ", ".join(str(item) for item in values)
        if value_type == 4:
            values = struct.unpack(byte_order + "I" * count, value)
            return ", ".join(str(item) for item in values)
        if value_type == 5:
            values = []
            for offset in range(0, len(value), 8):
                numerator, denominator = struct.unpack(
                    byte_order + "II", value[offset : offset + 8]
                )
                values.append(rational_text(numerator, denominator))
            return ", ".join(values)
        if value_type == 7:
            if len(value) <= 32:
                return value.hex(" ")
            return f"{value[:32].hex(' ')} ... ({len(value)} bytes)"
        if value_type == 9:
            values = struct.unpack(byte_order + "i" * count, value)
            return ", ".join(str(item) for item in values)
        if value_type == 10:
            values = []
            for offset in range(0, len(value), 8):
                numerator, denominator = struct.unpack(
                    byte_order + "ii", value[offset : offset + 8]
                )
                values.append(rational_text(numerator, denominator))
            return ", ".join(values)
    except struct.error:
        return "<kunde inte avkoda>"

    if len(value) <= 32:
        return value.hex(" ")
    return f"{value[:32].hex(' ')} ... ({len(value)} bytes)"


def parse_ifd_attributes(
    data: bytes,
    byte_order: str,
    offset: int,
    ifd_name: str,
    *,
    follow_exif_ifd: bool,
) -> tuple[list[ExifAttribute], str | None, int | None]:
    if offset < 0 or offset + 2 > len(data):
        return [], None, None

    entry_count = struct.unpack(byte_order + "H", data[offset : offset + 2])[0]
    entry_start = offset + 2
    entry_end = entry_start + entry_count * 12
    if entry_end > len(data):
        return [], None, None

    attributes: list[ExifAttribute] = []
    datetime_original = None
    exif_ifd_offset = None

    for entry_offset in range(entry_start, entry_end, 12):
        entry = data[entry_offset : entry_offset + 12]
        tag, value_type, count = struct.unpack(byte_order + "HHI", entry[:8])
        raw_value = entry[8:12]
        name = TAG_NAMES.get(tag, f"Tag0x{tag:04X}")
        value = decode_value(data, byte_order, value_type, count, raw_value)
        attributes.append(ExifAttribute(ifd_name, tag, name, value))

        if tag == TAG_DATETIME_ORIGINAL:
            datetime_original = read_ascii_value(
                data, byte_order, value_type, count, raw_value
            )
        elif follow_exif_ifd and tag == TAG_EXIF_IFD:
            exif_ifd_offset = read_long_value(data, byte_order, value_type, raw_value)

    return attributes, datetime_original, exif_ifd_offset


def parse_ifd(
    data: bytes,
    byte_order: str,
    offset: int,
    *,
    follow_exif_ifd: bool,
) -> tuple[str | None, str | None, int | None]:
    if offset < 0 or offset + 2 > len(data):
        return None, None, None

    entry_count = struct.unpack(byte_order + "H", data[offset : offset + 2])[0]
    entry_start = offset + 2
    entry_end = entry_start + entry_count * 12
    if entry_end > len(data):
        return None, None, None

    datetime_original = None
    datetime_fallback = None
    exif_ifd_offset = None

    for entry_offset in range(entry_start, entry_end, 12):
        entry = data[entry_offset : entry_offset + 12]
        tag, value_type, count = struct.unpack(byte_order + "HHI", entry[:8])
        raw_value = entry[8:12]

        if tag == TAG_DATETIME_ORIGINAL:
            datetime_original = read_ascii_value(
                data, byte_order, value_type, count, raw_value
            )
        elif tag == TAG_DATETIME:
            datetime_fallback = read_ascii_value(
                data, byte_order, value_type, count, raw_value
            )
        elif follow_exif_ifd and tag == TAG_EXIF_IFD:
            exif_ifd_offset = read_long_value(data, byte_order, value_type, raw_value)

    return datetime_original, datetime_fallback, exif_ifd_offset


def parse_tiff_datetime_original(data: bytes) -> str | None:
    if len(data) < 8:
        return None

    marker = data[:2]
    if marker == b"II":
        byte_order = "<"
    elif marker == b"MM":
        byte_order = ">"
    else:
        return None

    if struct.unpack(byte_order + "H", data[2:4])[0] != 42:
        return None

    first_ifd_offset = struct.unpack(byte_order + "I", data[4:8])[0]
    datetime_original, _, exif_ifd_offset = parse_ifd(
        data, byte_order, first_ifd_offset, follow_exif_ifd=True
    )
    if datetime_original:
        return datetime_original

    if exif_ifd_offset is None:
        return None

    datetime_original, _, _ = parse_ifd(
        data, byte_order, exif_ifd_offset, follow_exif_ifd=False
    )
    return datetime_original


def parse_tiff_exif(data: bytes) -> tuple[str | None, list[ExifAttribute]]:
    if len(data) < 8:
        return None, []

    marker = data[:2]
    if marker == b"II":
        byte_order = "<"
    elif marker == b"MM":
        byte_order = ">"
    else:
        return None, []

    if struct.unpack(byte_order + "H", data[2:4])[0] != 42:
        return None, []

    first_ifd_offset = struct.unpack(byte_order + "I", data[4:8])[0]
    attributes, datetime_original, exif_ifd_offset = parse_ifd_attributes(
        data, byte_order, first_ifd_offset, "IFD0", follow_exif_ifd=True
    )

    if exif_ifd_offset is not None:
        exif_attributes, exif_datetime_original, _ = parse_ifd_attributes(
            data, byte_order, exif_ifd_offset, "ExifIFD", follow_exif_ifd=False
        )
        attributes.extend(exif_attributes)
        datetime_original = datetime_original or exif_datetime_original

    return datetime_original, attributes


def read_next_jpeg_marker(source: BinaryIO) -> int | None:
    current = source.read(1)
    while current and current != b"\xff":
        current = source.read(1)

    if not current:
        return None

    marker = source.read(1)
    while marker == b"\xff":
        marker = source.read(1)

    if not marker or marker == b"\x00":
        return None
    return marker[0]


def jpeg_datetime_original(path: Path) -> str | None:
    with path.open("rb") as source:
        if source.read(2) != b"\xff\xd8":
            return None

        while True:
            marker = read_next_jpeg_marker(source)
            if marker is None or marker == 0xDA:
                return None
            if marker in {0xD8, 0xD9}:
                continue

            raw_length = source.read(2)
            if len(raw_length) != 2:
                return None

            segment_length = int.from_bytes(raw_length, "big")
            if segment_length < 2:
                return None

            payload_size = segment_length - 2
            if marker != 0xE1:
                source.seek(payload_size, os.SEEK_CUR)
                continue

            block = source.read(payload_size)
            if len(block) != payload_size:
                return None
            if not block.startswith(EXIF_HEADER):
                continue

            value = parse_tiff_datetime_original(block[len(EXIF_HEADER) :])
            if value:
                return value


def jpeg_exif(path: Path) -> tuple[str | None, list[ExifAttribute]]:
    with path.open("rb") as source:
        if source.read(2) != b"\xff\xd8":
            return None, []

        all_attributes: list[ExifAttribute] = []
        while True:
            marker = read_next_jpeg_marker(source)
            if marker is None or marker == 0xDA:
                return None, all_attributes
            if marker in {0xD8, 0xD9}:
                continue

            raw_length = source.read(2)
            if len(raw_length) != 2:
                return None, all_attributes

            segment_length = int.from_bytes(raw_length, "big")
            if segment_length < 2:
                return None, all_attributes

            payload_size = segment_length - 2
            if marker != 0xE1:
                source.seek(payload_size, os.SEEK_CUR)
                continue

            block = source.read(payload_size)
            if len(block) != payload_size:
                return None, all_attributes
            if not block.startswith(EXIF_HEADER):
                continue

            datetime_original, attributes = parse_tiff_exif(
                block[len(EXIF_HEADER) :]
            )
            all_attributes.extend(attributes)
            if datetime_original:
                return datetime_original, all_attributes


def date_taken(path: Path) -> str | None:
    suffix = path.suffix.casefold()

    if suffix in {".tif", ".tiff"}:
        data = path.read_bytes()
        return parse_tiff_datetime_original(data)

    if suffix in {".jpg", ".jpeg"}:
        return jpeg_datetime_original(path)

    return None


def inspect_exif(path: Path) -> ImageInspection:
    try:
        suffix = path.suffix.casefold()
        if suffix in {".tif", ".tiff"}:
            date_value, attributes = parse_tiff_exif(path.read_bytes())
        elif suffix in {".jpg", ".jpeg"}:
            date_value, attributes = jpeg_exif(path)
        else:
            date_value, attributes = None, []
        return ImageInspection(path, date_value, attributes)
    except OSError as error:
        return ImageInspection(path, None, [], str(error))


def inspect_image(path: Path) -> tuple[Path, bool, str | None]:
    try:
        return path, bool(date_taken(path)), None
    except OSError as error:
        return path, False, str(error)


def find_missing_date_taken(
    root: Path, workers: int, date_filter: str | None
) -> tuple[list[ImageInspection], int]:
    missing: list[ImageInspection] = []
    unreadable = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for inspection in executor.map(inspect_exif, iter_images(root, date_filter)):
            if inspection.error is not None:
                unreadable += 1
                print(
                    f"FEL: kunde inte läsa {inspection.path}: {inspection.error}",
                    file=sys.stderr,
                )
            if not inspection.date_taken:
                missing.append(inspection)

    return missing, unreadable


def format_report(missing: list[ImageInspection]) -> str:
    lines: list[str] = []
    for inspection in missing:
        lines.append(str(inspection.path))
        if inspection.attributes:
            for attribute in inspection.attributes:
                lines.append(
                    f"  {attribute.ifd}.{attribute.name} "
                    f"(0x{attribute.tag:04X}): {attribute.value}"
                )
        else:
            lines.append("  EXIF: saknas")
        lines.append("")
    return "\n".join(lines).rstrip()


def default_workers() -> int:
    return min(32, (os.cpu_count() or 1) + 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Skriv alla bilder i BB2 som saknar EXIF DateTimeOriginal "
            "till date_taken.txt."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("BB2"),
        help="BB2-katalog att kontrollera (standard: BB2)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers(),
        help=f"antal parallella lästrådar (standard: {default_workers()})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("date_taken.txt"),
        help="rapportfil (standard: date_taken.txt)",
    )
    parser.add_argument(
        "--date",
        default="2025-07-12",
        help="lista bara bilder vars sökväg innehåller detta datum (standard: 2025-07-12)",
    )
    return parser.parse_args()


def main() -> int:
    configure_output()
    args = parse_args()
    if args.workers < 1:
        print("FEL: --workers måste vara minst 1.", file=sys.stderr)
        return 1

    try:
        missing, unreadable = find_missing_date_taken(
            args.root, args.workers, args.date
        )
    except OSError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    args.output.write_text(format_report(missing) + "\n", encoding="utf-8")

    print(
        f"Klart. {len(missing)} bilder saknar date taken."
        f" Urval: {args.date}."
        f" Oläsbara filer: {unreadable}."
        f" Rapport skriven till {args.output}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
