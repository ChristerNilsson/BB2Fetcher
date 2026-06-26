#!/usr/bin/env python3
"""Move BB2 0000 buckets into year folders."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

YEAR_BUCKETS = {
    "0000 Diverse": "Diverse",
    "0000 Evenemang": "Evenemang",
}
RENAMES = {
    "0000 Klubbar": "Klubbar",
}


@dataclass(frozen=True)
class MoveAction:
    source: Path
    destination: Path


def configure_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def iter_year_bucket_actions(root: Path) -> list[MoveAction]:
    actions: list[MoveAction] = []

    for source_name, target_name in YEAR_BUCKETS.items():
        source_root = root / source_name
        if not source_root.exists():
            continue
        if not source_root.is_dir():
            raise NotADirectoryError(f"Inte en katalog: {source_root}")

        for year_dir in sorted(source_root.iterdir(), key=lambda path: path.name):
            if not year_dir.is_dir():
                raise NotADirectoryError(
                    f"Förväntade årtalskatalog under {source_root}: {year_dir}"
                )
            if not year_dir.name.isdecimal() or len(year_dir.name) != 4:
                raise ValueError(f"Ogiltigt årtal under {source_root}: {year_dir.name}")

            destination_root = root / year_dir.name / target_name
            for child in sorted(year_dir.iterdir(), key=lambda path: path.name):
                actions.append(MoveAction(child, destination_root / child.name))

    return actions


def iter_rename_actions(root: Path) -> list[MoveAction]:
    actions: list[MoveAction] = []
    for source_name, target_name in RENAMES.items():
        source = root / source_name
        if source.exists():
            actions.append(MoveAction(source, root / target_name))
    return actions


def planned_actions(root: Path) -> list[MoveAction]:
    if not root.exists():
        raise FileNotFoundError(f"Katalogen finns inte: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Inte en katalog: {root}")

    return iter_year_bucket_actions(root) + iter_rename_actions(root)


def validate_actions(actions: list[MoveAction], overwrite: bool) -> list[str]:
    errors: list[str] = []
    destinations: dict[Path, Path] = {}

    for action in actions:
        if not action.source.exists():
            errors.append(f"Källan saknas: {action.source}")

        previous_source = destinations.setdefault(action.destination, action.source)
        if previous_source != action.source:
            errors.append(
                f"Flera källor skulle skriva till {action.destination}: "
                f"{previous_source} och {action.source}"
            )

        if action.destination.exists() and not overwrite:
            errors.append(f"Målet finns redan: {action.destination}")
        if action.source == action.destination:
            errors.append(f"Källa och mål är samma: {action.source}")

    return errors


def format_report(actions: list[MoveAction], dry_run: bool) -> str:
    if not actions:
        return "Inga åtgärder hittades för 0000 Diverse, 0000 Evenemang eller 0000 Klubbar."

    heading = "Planerade åtgärder, inga ändringar genomförs:" if dry_run else "Planerade åtgärder:"
    lines = [heading]
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index:03}. Flytta: {action.source}")
        lines.append(f"     till:   {action.destination}")
    lines.append(f"Klart. Hittade {len(actions)} planerade åtgärder.")
    return "\n".join(lines)


def remove_empty_source_dirs(root: Path) -> int:
    removed = 0
    for source_name in YEAR_BUCKETS:
        source_root = root / source_name
        if not source_root.exists():
            continue

        for path in sorted(
            (candidate for candidate in source_root.rglob("*") if candidate.is_dir()),
            key=lambda candidate: len(candidate.parts),
            reverse=True,
        ):
            try:
                path.rmdir()
                removed += 1
            except OSError:
                pass

        try:
            source_root.rmdir()
            removed += 1
        except OSError:
            pass
    return removed


def execute_actions(actions: list[MoveAction], root: Path, overwrite: bool) -> tuple[int, int]:
    moved = 0
    overwritten = 0

    for action in actions:
        action.destination.parent.mkdir(parents=True, exist_ok=True)
        if action.destination.exists():
            if action.destination.is_dir():
                shutil.rmtree(action.destination)
            else:
                action.destination.unlink()
            overwritten += 1

        print(f"Flyttar: {action.source} -> {action.destination}")
        shutil.move(str(action.source), str(action.destination))
        moved += 1

    removed_dirs = remove_empty_source_dirs(root)
    return moved, overwritten + removed_dirs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Flytta innehåll från BB2/0000 Diverse och BB2/0000 Evenemang "
            "till respektive årskatalog samt byt namn på BB2/0000 Klubbar."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("BB2"),
        help="BB2-katalog att ändra (standard: BB2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="lista bara planerade åtgärder utan att flytta eller byta namn",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="skriv över befintliga mål om de redan finns",
    )
    return parser.parse_args()


def main() -> int:
    configure_output()
    args = parse_args()

    try:
        actions = planned_actions(args.root)
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
        moved, cleanup_count = execute_actions(actions, args.root, args.overwrite)
    except OSError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    print(
        f"Genomfört. Flyttade {moved} poster och tog bort/skrev över "
        f"{cleanup_count} gamla poster."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
