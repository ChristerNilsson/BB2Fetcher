#!/usr/bin/env python3
"""Create the BB2/2011 tree and download its images from bilder.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

YEAR = "2011"
URL_TEMPLATE = "https://storage.googleapis.com/bildbank2/Home/{image_id}.jpg"


def image_entries(
    node: dict[str, object], relative_dir: Path = Path()
) -> Iterator[tuple[Path, str]]:
    """Yield (relative file path, image id) pairs from a JSON directory tree."""
    for name, value in node.items():
        path = relative_dir / name
        if isinstance(value, dict):
            yield from image_entries(value, path)
        elif (
            isinstance(value, list)
            and len(value) >= 6
            and isinstance(value[-1], str)
        ):
            yield path, value[-1]
        else:
            raise ValueError(f"Ogiltig bildpost i bilder.json: {path}")


def load_year(json_path: Path) -> dict[str, object]:
    with json_path.open(encoding="utf-8-sig") as source:
        data = json.load(source)

    if not isinstance(data, dict):
        raise ValueError("Roten i bilder.json måste vara ett objekt.")

    year = data.get(YEAR)
    if not isinstance(year, dict):
        raise ValueError(f"Katalogen {YEAR!r} saknas i bilder.json.")
    return year


def download(url: str, destination: Path, timeout: float) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")

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
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def fetch_images(
    json_path: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
    timeout: float = 30,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    year_tree = load_year(json_path)
    year_root = output_root / YEAR
    entries = list(image_entries(year_tree))

    downloaded = skipped = failed = 0
    for index, (relative_path, image_id) in enumerate(entries, start=1):
        destination = year_root / relative_path
        url = URL_TEMPLATE.format(image_id=image_id)

        if destination.exists() and not overwrite:
            skipped += 1
            print(f"[{index}/{len(entries)}] Finns redan: {destination}")
            continue

        if dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f"[{index}/{len(entries)}] Skulle hämta: {destination}")
            continue

        print(f"[{index}/{len(entries)}] Hämtar: {destination}")
        try:
            download(url, destination, timeout)
            downloaded += 1
        except (OSError, urllib.error.URLError) as error:
            failed += 1
            print(f"  FEL: {url}: {error}", file=sys.stderr)

    return downloaded, skipped, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Skapa BB2/2011 och hämta bilderna som anges i bilder.json."
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
