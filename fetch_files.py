#!/usr/bin/env python3
"""Download file_index.txt entries from Bildbank 2 to BB2/files."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL_ROOT = "https://storage.googleapis.com/bildbank2/files/"


def load_file_paths(index_path: Path) -> tuple[list[Path], int]:
    """Return unique files/... paths from file_index.txt and skipped URL count."""
    paths: list[Path] = []
    seen: set[str] = set()
    skipped_external = 0

    with index_path.open(encoding="utf-8-sig") as source:
        for line_number, raw_line in enumerate(source, start=1):
            line = raw_line.strip()
            if not line:
                continue

            _, separator, value = line.partition(" : ")
            if not separator:
                raise ValueError(f"Ogiltig rad {line_number}: {raw_line.rstrip()}")

            file_ref = value.strip()
            if not file_ref.startswith("files/"):
                skipped_external += 1
                continue

            relative_name = file_ref[len("files/") :]
            relative_path = Path(relative_name)
            if (
                not relative_name
                or relative_path.is_absolute()
                or ".." in relative_path.parts
            ):
                raise ValueError(f"Ogiltig filsökväg på rad {line_number}: {file_ref}")

            normalized = relative_path.as_posix()
            if normalized not in seen:
                seen.add(normalized)
                paths.append(relative_path)

    return paths, skipped_external


def url_for(relative_path: Path) -> str:
    quoted_path = urllib.parse.quote(relative_path.as_posix(), safe="/")
    return URL_ROOT + quoted_path


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


def fetch_files(
    index_path: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
    timeout: float = 30,
    dry_run: bool = False,
) -> tuple[int, int, int, int]:
    files, skipped_external = load_file_paths(index_path)
    print(f"{len(files)} unika filer hittade i {index_path}.")
    if skipped_external:
        print(f"{skipped_external} externa URL:er hoppas över.")

    downloaded = skipped_existing = failed = 0
    for index, relative_path in enumerate(files, start=1):
        destination = output_root / relative_path
        url = url_for(relative_path)

        if destination.exists() and not overwrite:
            skipped_existing += 1
            print(f"[{index}/{len(files)}] Finns redan: {destination}")
            continue

        if dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f"[{index}/{len(files)}] Skulle hämta: {url} -> {destination}")
            continue

        print(f"[{index}/{len(files)}] Hämtar: {url}")
        print(f"  till: {destination}")
        try:
            size = download(url, destination, timeout)
            downloaded += 1
            print(f"  klart: {format_size(size)}")
        except (OSError, urllib.error.URLError) as error:
            failed += 1
            print(f"  FEL: {error}", file=sys.stderr)

    return downloaded, skipped_existing, skipped_external, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hämta filer från json/file_index.txt till BB2/files."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("json/file_index.txt"),
        help="sökväg till file_index.txt (standard: json/file_index.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("BB2/files"),
        help="målkatalog (standard: BB2/files)",
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
        help="skapa katalogerna och visa vad som skulle hämtas",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        downloaded, skipped_existing, skipped_external, failed = fetch_files(
            args.index,
            args.output,
            overwrite=args.overwrite,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError) as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    print(
        "Klart. "
        f"Hämtade: {downloaded}, "
        f"fanns redan: {skipped_existing}, "
        f"externa överhoppade: {skipped_external}, "
        f"fel: {failed}."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
