#!/usr/bin/env python3
"""Replace BB2 directory references with files or URL shortcuts.

By default the script validates and performs the planned renames/copies/URL file
creation. Use --dry-run to only list the planned actions.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

REF_PATTERN = re.compile(r"_([IFRL])(\d{5})|_([TCV])(\d+)")
TARGET_BASENAME = {
    "I": "Inbjudan",
    "F": "Fakta",
    "R": "Resultat",
    "L": "Länk",
    "T": "Turnering",
    "C": "Chess-Results",
    "V": "Video",
}


@dataclass(frozen=True)
class FileEntry:
    identifier: str
    reference: str
    relative_path: Path | None
    url: str | None


@dataclass(frozen=True)
class PlannedAction:
    directory: Path
    renamed_directory: Path
    tag: str
    file_id: str
    source: Path | None
    url: str | None
    destination: Path
    warning: str | None = None


def configure_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_file_index(index_path: Path) -> dict[str, FileEntry]:
    entries: dict[str, FileEntry] = {}

    with index_path.open(encoding="utf-8-sig") as source:
        for line_number, raw_line in enumerate(source, start=1):
            line = raw_line.strip()
            if not line:
                continue

            identifier, separator, value = line.partition(" : ")
            if not separator or not identifier.isdecimal():
                raise ValueError(f"Ogiltig rad {line_number}: {raw_line.rstrip()}")

            reference = value.strip()
            relative_path = None
            url = None
            if reference.startswith("files/"):
                file_name = reference[len("files/") :].strip()
                candidate = Path(file_name)
                if not file_name or candidate.is_absolute() or ".." in candidate.parts:
                    raise ValueError(
                        f"Ogiltig filsökväg på rad {line_number}: {reference}"
                    )
                relative_path = candidate
            elif is_url(reference):
                url = reference

            entries[identifier] = FileEntry(identifier, reference, relative_path, url)

    return entries


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def remove_file_refs(name: str) -> str:
    return REF_PATTERN.sub("", name)


def target_destination(
    directory: Path, tag: str, source: Path | None, url: str | None
) -> Path:
    suffix = ".url" if url is not None else source.suffix if source is not None else ""
    return directory / f"{TARGET_BASENAME[tag]}{suffix}"


def url_file_content(url: str) -> str:
    return f"[InternetShortcut]\nURL={url}\n"


def generated_url(tag: str, identifier: str) -> str | None:
    if tag == "T":
        return (
            "https://member.schack.se/ShowTournamentServlet"
            f"?id={identifier}&listingtype=2"
        )
    if tag == "C":
        return f"https://chess-results.com/tnr{identifier}.aspx?lan=6&art=4"
    if tag == "V":
        return f"https://player.vimeo.com/video/{identifier}"
    return None


def iter_directories(root: Path, excluded_names: set[str]) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Katalogen finns inte: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Inte en katalog: {root}")

    directories: list[Path] = []
    for directory, directory_names, _ in os.walk(root):
        directory_path = Path(directory)
        directory_names[:] = [
            name for name in directory_names if name not in excluded_names
        ]

        for directory_name in directory_names:
            directories.append(directory_path / directory_name)

    return sorted(
        directories, key=lambda path: path.relative_to(root).as_posix().casefold()
    )


def planned_actions(
    root: Path,
    files_root: Path,
    index: dict[str, FileEntry],
    excluded_names: set[str],
) -> list[PlannedAction]:
    actions: list[PlannedAction] = []

    for directory in iter_directories(root, excluded_names):
        matches = list(REF_PATTERN.finditer(directory.name))
        if not matches:
            continue

        renamed_directory = directory.with_name(remove_file_refs(directory.name))
        for match in matches:
            tag = match.group(1) or match.group(3)
            file_id = match.group(2) or match.group(4)
            source = None
            url = None
            warning = None

            url = generated_url(tag, file_id)
            if url is None:
                entry = index.get(file_id)
                if entry is None:
                    warning = f"saknas i filindex: {file_id}"
                elif entry.relative_path is not None:
                    source = files_root / entry.relative_path
                elif entry.url is not None:
                    url = entry.url
                else:
                    warning = f"varken lokal files/-post eller URL: {entry.reference}"

            actions.append(
                PlannedAction(
                    directory=directory,
                    renamed_directory=renamed_directory,
                    tag=tag,
                    file_id=file_id,
                    source=source,
                    url=url,
                    destination=target_destination(renamed_directory, tag, source, url),
                    warning=warning,
                )
            )

    return actions


def format_report(actions: list[PlannedAction], dry_run: bool) -> str:
    lines: list[str] = []
    if not actions:
        return (
            "Inga katalognamn med _I12345, _F12345, _R12345, _L12345, "
            "_T12345, _C12345 eller _V12345 hittades."
        )

    if dry_run:
        lines.append("Planerade åtgärder, inga ändringar genomförs:")
    else:
        lines.append("Planerade åtgärder:")
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index:03}. Katalog: {action.directory}")
        lines.append(f"     byt namn till: {action.renamed_directory}")
        if action.source is not None:
            lines.append(f"     kopiera:       {action.source}")
            lines.append(f"     till:          {action.destination}")
        elif action.url is not None:
            lines.append(f"     skapa url-fil: {action.destination}")
            lines.append(f"     innehåll:      [InternetShortcut]")
            lines.append(f"                   URL={action.url}")
        else:
            lines.append(f"     fil-id:        {action.tag}{action.file_id}")
            lines.append(f"     varning:       {action.warning}")
    lines.append(f"Klart. Hittade {len(actions)} planerade åtgärder.")
    return "\n".join(lines)


def validate_actions(actions: list[PlannedAction], overwrite: bool) -> list[str]:
    errors: list[str] = []
    rename_targets: dict[Path, Path] = {}
    output_targets: dict[Path, PlannedAction] = {}

    for action in actions:
        if action.warning is not None:
            errors.append(f"{action.directory}: {action.warning}")
            continue
        if action.source is None and action.url is None:
            errors.append(
                f"{action.directory}: saknar källa för {action.tag}{action.file_id}"
            )
            continue
        if action.source is not None and not action.source.exists():
            errors.append(f"{action.directory}: källfil saknas: {action.source}")
        if not action.directory.exists():
            errors.append(f"{action.directory}: katalogen saknas")

        previous_directory = rename_targets.setdefault(
            action.renamed_directory, action.directory
        )
        if previous_directory != action.directory:
            errors.append(
                f"{action.directory}: målkatalog krockar med {previous_directory}: "
                f"{action.renamed_directory}"
            )

        if action.renamed_directory.exists() and action.renamed_directory != action.directory:
            errors.append(
                f"{action.directory}: målkatalogen finns redan: "
                f"{action.renamed_directory}"
            )

        previous_action = output_targets.setdefault(action.destination, action)
        if previous_action != action:
            errors.append(
                f"{action.directory}: flera åtgärder skulle skriva till "
                f"{action.destination}"
            )

        existing_destination = action.directory / action.destination.name
        if not overwrite and existing_destination.exists():
            errors.append(
                f"{action.directory}: målfilen finns redan: {existing_destination}"
            )

    return errors


def execute_actions(actions: list[PlannedAction], overwrite: bool) -> tuple[int, int]:
    renamed_directories: dict[Path, Path] = {}
    renamed_count = written_count = 0

    execution_order = sorted(
        actions,
        key=lambda action: (
            len(action.directory.parts),
            str(action.directory).casefold(),
        ),
        reverse=True,
    )

    for action in execution_order:
        target_directory = renamed_directories.get(action.directory)
        if target_directory is None:
            print(f"Byter namn: {action.directory} -> {action.renamed_directory}")
            action.directory.rename(action.renamed_directory)
            renamed_directories[action.directory] = action.renamed_directory
            target_directory = action.renamed_directory
            renamed_count += 1

        destination = target_directory / action.destination.name
        if destination.exists() and overwrite:
            destination.unlink()

        if action.source is not None:
            print(f"Kopierar:   {action.source} -> {destination}")
            shutil.copy2(action.source, destination)
        else:
            assert action.url is not None
            print(f"Skapar URL: {destination}")
            destination.write_text(url_file_content(action.url), encoding="utf-8")
        written_count += 1

    return renamed_count, written_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ta bort _I/_F/_R/_L/_T/_C/_V-referenser ur BB2-katalognamn och "
            "kopiera motsvarande filer eller skapa .url-genvägar."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("BB2"),
        help="BB2-katalog att kontrollera (standard: BB2)",
    )
    parser.add_argument(
        "--files-root",
        type=Path,
        default=Path("BB2/files"),
        help="katalog med hämtade files-poster (standard: BB2/files)",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("json/file_index.txt"),
        help="sökväg till file_index.txt (standard: json/file_index.txt)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["files"],
        help="katalognamn under root som inte ska analyseras (standard: files)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="lista bara planerade åtgärder utan att byta namn, kopiera eller skapa filer",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "skriv över befintliga Inbjudan/Fakta/Resultat/Länk/"
            "Turnering/Chess-Results/Video-filer i målkatalogen"
        ),
    )
    return parser.parse_args()


def main() -> int:
    configure_output()
    args = parse_args()

    try:
        index = load_file_index(args.index)
        actions = planned_actions(
            args.root, args.files_root, index, set(args.exclude)
        )
        errors = validate_actions(actions, args.overwrite)
    except (OSError, ValueError) as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    print(format_report(actions, args.dry_run))
    if args.dry_run:
        print("Dry-run: inga ändringar genomfördes.")
        return 0

    if errors:
        print("", file=sys.stderr)
        print("FEL: Avbryter eftersom preflight hittade problem:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    try:
        renamed_count, written_count = execute_actions(actions, args.overwrite)
    except OSError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    print(
        f"Genomfört. Bytte namn på {renamed_count} kataloger och "
        f"skrev {written_count} filer."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
