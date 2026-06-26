#!/usr/bin/env python3
"""Create the complete BB2 tree and download its images from bilder.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

URL_TEMPLATE = "https://storage.googleapis.com/bildbank2/Home/{image_id}.jpg"


def image_entries(
    node: dict[str, object], relative_dir: Path = Path()
) -> Iterator[tuple[Path, str, int]]:
    """Yield (relative file path, image id, expected size) from a JSON tree."""
    for name, value in node.items():
        path = relative_dir / name
        if isinstance(value, dict):
            yield from image_entries(value, path)
        elif (
            isinstance(value, list)
            and len(value) >= 6
            and isinstance(value[-1], str)
            and isinstance(value[2], int)
        ):
            yield path, value[-1], value[2]
        else:
            raise ValueError(f"Ogiltig bildpost i bilder.json: {path}")


def load_tree(json_path: Path) -> dict[str, object]:
    with json_path.open(encoding="utf-8-sig") as source:
        data = json.load(source)

    if not isinstance(data, dict):
        raise ValueError("Roten i bilder.json måste vara ett objekt.")
    return data


def download(url: str, destination: Path, timeout: float) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    bytes_written = 0

    request = urllib.request.Request(
        url, headers={"User-Agent": "BB2Fetcher/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise OSError(f"HTTP {response.status}")
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    bytes_written += len(chunk)
        os.replace(temporary, destination)
        return bytes_written
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def format_size(size: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")


def forecast(elapsed: float, downloaded_bytes: int, remaining_bytes: int) -> str:
    if elapsed <= 0 or downloaded_bytes <= 0:
        return "prognos saknas"
    seconds_left = remaining_bytes / (downloaded_bytes / elapsed)
    finish = datetime.now() + timedelta(seconds=seconds_left)
    return (
        f"klart cirka {finish:%Y-%m-%d %H:%M}"
        f" ({timedelta(seconds=round(seconds_left))} kvar)"
    )


def fetch_images(
    json_path: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
    timeout: float = 30,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    tree = load_tree(json_path)
    entries = list(image_entries(tree))
    total_size = sum(expected_size for _, _, expected_size in entries)
    print(f"{len(entries)} bilder, totalt cirka {format_size(total_size)}.")

    downloaded = skipped = failed = 0
    pending: list[tuple[Path, str, int]] = []
    for relative_path, image_id, expected_size in entries:
        destination = output_root / relative_path
        if destination.exists() and not overwrite:
            skipped += 1
        else:
            pending.append((relative_path, image_id, expected_size))

    if skipped:
        print(f"{skipped} filer finns redan och hoppas över.")

    pending_size = sum(expected_size for _, _, expected_size in pending)
    started = time.monotonic()
    received_bytes = processed_expected_bytes = 0

    for index, (relative_path, image_id, expected_size) in enumerate(
        pending, start=1
    ):
        destination = output_root / relative_path
        url = URL_TEMPLATE.format(image_id=image_id)

        if dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f"[{index}/{len(pending)}] Skulle hämta: {destination}")
            continue

        print(f"[{index}/{len(pending)}] Hämtar: {destination}")
        try:
            received_bytes += download(url, destination, timeout)
            downloaded += 1
        except (OSError, urllib.error.URLError) as error:
            failed += 1
            print(f"  FEL: {url}: {error}", file=sys.stderr)
        processed_expected_bytes += expected_size

        elapsed = time.monotonic() - started
        remaining_bytes = max(0, pending_size - processed_expected_bytes)
        print(
            f"  {format_size(received_bytes)} hämtat, "
            f"{forecast(elapsed, received_bytes, remaining_bytes)}"
        )

    return downloaded, skipped, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Skapa hela BB2-trädet och hämta bilderna i bilder.json."
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("bilder.json"),
        help="sökväg till bilder.json (standard: bilder.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("BB2"),
        help="målkatalog (standard: BB2)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="hämta om filer som redan finns",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="timeout per HTTP-anrop i sekunder (standard: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="skapa katalogerna men hämta inga filer",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        downloaded, skipped, failed = fetch_images(
            args.json,
            args.output,
            overwrite=args.overwrite,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    print(
        f"Klart. Hämtade: {downloaded}, fanns redan: {skipped}, fel: {failed}."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
