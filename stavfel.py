#!/usr/bin/env python3
"""List suspected spelling mistakes in the BB2 file catalog.

The script only reports suggestions. It never renames or edits files.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


def configure_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    replacement: str
    explanation: str


def compile_rule(pattern: str, replacement: str, explanation: str) -> Rule:
    return Rule(re.compile(pattern, re.IGNORECASE), replacement, explanation)


RULES = [
    compile_rule(r"Allsvenksan", "Allsvenskan", "omkastade bokstäver"),
    compile_rule(r"Slutresulat", "Slutresultat", "saknad bokstav i resultat"),
    compile_rule(r"Slutreultat", "Slutresultat", "saknad bokstav i resultat"),
    compile_rule(r"Resuktat", "Resultat", "fel bokstav i resultat"),
    compile_rule(
        r"Pasklovsturnerinen",
        "Påsklovsturneringen",
        "saknade svenska tecken och saknad bokstav",
    ),
    compile_rule(r"Pasklov", "Påsklov", "saknat svenskt tecken"),
    compile_rule(r"Hostlov", "Höstlov", "saknat svenskt tecken"),
    compile_rule(r"hostblixt", "höstblixt", "saknat svenskt tecken"),
    compile_rule(r"\bhogstadiet\b", "högstadiet", "saknat svenskt tecken"),
    compile_rule(r"Lagstadiet", "Lågstadiet", "saknat svenskt tecken"),
    compile_rule(
        r"Stockholmsmasterskapet",
        "Stockholmsmästerskapet",
        "saknat svenskt tecken",
    ),
    compile_rule(
        r"Foretagsmasterskapet",
        "Företagsmästerskapet",
        "saknade svenska tecken",
    ),
    compile_rule(
        r"Företagsmasterskapet",
        "Företagsmästerskapet",
        "saknat svenskt tecken",
    ),
    compile_rule(
        r"Schackfyranmastaren",
        "Schackfyranmästaren",
        "saknat svenskt tecken",
    ),
    compile_rule(
        r"Schack56mastaren",
        "Schack56mästaren",
        "saknat svenskt tecken",
    ),
    compile_rule(
        r"Schack56anMastaren",
        "Schack56anmästaren",
        "saknat svenskt tecken",
    ),
    compile_rule(r"Tjejtavlingen", "Tjejtävlingen", "saknat svenskt tecken"),
    compile_rule(r"Hastens", "Hästens", "saknat svenskt tecken"),
    compile_rule(r"\bVar\b", "Vår", "saknat svenskt tecken"),
    compile_rule(r"nyborjar", "nybörjar", "saknade svenska tecken"),
    compile_rule(r"Schackk56ans", "Schack56ans", "dubbel bokstav"),
]


@dataclass(frozen=True)
class Finding:
    path: Path
    original: str
    replacement: str
    suggested_path: Path
    explanation: str


@dataclass(frozen=True)
class UniqueWord:
    word: str
    file_number: str
    path: Path


TOKEN_PATTERN = re.compile(r"[A-Za-zÅÄÖåäöÉé]+")
JOSEFINA = "Josefina"
VALID_JOSEF_NAMES = {
    "jose",
    "josé",
    "josef",
    "josefin",
    "josefine",
    "josefina",
    "joseph",
    "josip",
}
BUILTIN_REFERENCE_WORDS = {
    "Alex",
    "Alexandr",
    "Alexandra",
    "Alexandre",
    "Alexander",
    "Alexandersson",
    "Alexei",
    "Alexis",
    "Allsvenskan",
    "Damallsvenskan",
    "Josef",
    "Josefin",
    "Josefina",
    "Josefine",
    "Joseph",
    "Josip",
}


def preserve_case(match: re.Match[str], replacement: str) -> str:
    text = match.group(0)
    if text.isupper():
        return replacement.upper()
    if text[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def replace_match(text: str, rule: Rule) -> str:
    return rule.pattern.sub(lambda match: preserve_case(match, rule.replacement), text)


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left

    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def normalize_key(word: str) -> str:
    return unicodedata.normalize("NFC", word).casefold()


def load_reference_text(source: str) -> str:
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(
            source, headers={"User-Agent": "BB2Fetcher/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8-sig")
    return Path(source).read_text(encoding="utf-8-sig")


def load_reference_words(sources: list[str]) -> set[str]:
    words = set(BUILTIN_REFERENCE_WORDS)
    for source in sources:
        text = load_reference_text(source)
        for match in TOKEN_PATTERN.finditer(text):
            words.add(match.group(0))
    return words


def reference_candidates_by_initial(
    words: set[str],
) -> dict[str, dict[int, list[str]]]:
    candidates: dict[str, dict[int, dict[str, str]]] = {}
    for word in words:
        key = normalize_key(word)
        if len(key) < 4:
            continue
        candidates.setdefault(key[:1], {}).setdefault(len(key), {}).setdefault(
            key, word
        )
    return {
        initial: {
            length: sorted(values.values(), key=str.casefold)
            for length, values in values_by_length.items()
        }
        for initial, values_by_length in candidates.items()
    }


def fuzzy_distance_limit(word: str) -> int:
    length = len(word)
    if length >= 9:
        return 3
    if length >= 6:
        return 2
    return 1


def best_reference_suggestion(
    token: str, candidates: dict[str, dict[int, list[str]]]
) -> str | None:
    key = normalize_key(token)
    if len(key) < 5:
        return None

    max_distance = fuzzy_distance_limit(key)
    best: tuple[int, str] | None = None
    by_length = candidates.get(key[:1], {})
    for length in range(len(key) - max_distance, len(key) + max_distance + 1):
        for candidate in by_length.get(length, []):
            candidate_key = normalize_key(candidate)
            if candidate_key == key:
                return None

            distance = levenshtein(key, candidate_key)
            if distance > max_distance:
                continue
            if best is None or (distance, candidate.casefold()) < (
                best[0],
                best[1].casefold(),
            ):
                best = (distance, candidate)

    return None if best is None else best[1]


def reference_suggestion(
    name: str, candidates: dict[str, dict[int, list[str]]]
) -> tuple[str, str] | None:
    for match in TOKEN_PATTERN.finditer(name):
        suggestion = best_reference_suggestion(match.group(0), candidates)
        if suggestion is None:
            continue
        corrected_name = (
            name[: match.start()]
            + preserve_case(match, suggestion)
            + name[match.end() :]
        )
        return corrected_name, suggestion
    return None


def is_probable_josefina_misspelling(token: str) -> bool:
    normalized = normalize_key(token)
    if normalized in VALID_JOSEF_NAMES:
        return False
    if not normalized.startswith("jos") or "f" not in normalized:
        return False
    if not 7 <= len(normalized) <= 9:
        return False
    return levenshtein(normalized, JOSEFINA.casefold()) <= 2


def josefina_suggestion(name: str) -> str | None:
    for match in TOKEN_PATTERN.finditer(name):
        if is_probable_josefina_misspelling(match.group(0)):
            return (
                name[: match.start()]
                + preserve_case(match, JOSEFINA)
                + name[match.end() :]
            )
    return None


def iter_catalog_paths(root: Path, excluded_names: set[str]) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Katalogen finns inte: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Inte en katalog: {root}")

    paths: list[Path] = []
    for directory, directory_names, file_names in os.walk(root):
        directory_path = Path(directory)
        directory_names[:] = [
            name for name in directory_names if name not in excluded_names
        ]

        for directory_name in directory_names:
            paths.append(directory_path / directory_name)
        for file_name in file_names:
            paths.append(directory_path / file_name)

    return sorted(paths, key=lambda path: path.relative_to(root).as_posix().lower())


def file_numbers(paths: list[Path]) -> dict[Path, str]:
    return {path: f"F{index:06}" for index, path in enumerate(paths, start=1)}


def iter_words(paths: list[Path]) -> list[tuple[str, Path]]:
    words: list[tuple[str, Path]] = []
    for path in paths:
        for match in TOKEN_PATTERN.finditer(unicodedata.normalize("NFC", path.name)):
            words.append((match.group(0), path))
    return words


def words_occurring_once(
    paths: list[Path], numbers: dict[Path, str], reference_keys: set[str]
) -> list[UniqueWord]:
    original_by_key: dict[str, str] = {}
    path_by_key: dict[str, Path] = {}
    counter: Counter[str] = Counter()

    for word, path in iter_words(paths):
        key = word.casefold()
        original_by_key.setdefault(key, word)
        path_by_key.setdefault(key, path)
        counter[key] += 1

    return sorted(
        (
            UniqueWord(original_by_key[key], numbers[path_by_key[key]], path_by_key[key])
            for key, count in counter.items()
            if count == 1 and key not in reference_keys
        ),
        key=lambda unique_word: unique_word.word.casefold(),
    )


def find_spelling_errors(
    root: Path,
    paths: list[Path],
    reference_candidates: dict[str, dict[int, list[str]]],
    limit: int,
) -> list[Finding]:
    findings: list[Finding] = []

    for path in paths:
        path_had_finding = False
        normalized_name = unicodedata.normalize("NFC", path.name)

        if normalized_name != path.name:
            suggested_path = path.with_name(normalized_name)
            findings.append(
                Finding(
                    path=path,
                    original=path.name,
                    replacement=normalized_name,
                    suggested_path=suggested_path,
                    explanation="normalisera Unicode till NFC",
                )
            )
            if len(findings) >= limit:
                return findings
            path_had_finding = True

        for rule in RULES:
            if not rule.pattern.search(path.name):
                continue

            corrected_name = replace_match(path.name, rule)
            findings.append(
                Finding(
                    path=path,
                    original=path.name,
                    replacement=corrected_name,
                    suggested_path=path.with_name(corrected_name),
                    explanation=rule.explanation,
                )
            )
            if len(findings) >= limit:
                return findings
            path_had_finding = True

        if path_had_finding:
            continue

        corrected_name = josefina_suggestion(path.name)
        if corrected_name and corrected_name != path.name:
            findings.append(
                Finding(
                    path=path,
                    original=path.name,
                    replacement=corrected_name,
                    suggested_path=path.with_name(corrected_name),
                    explanation="generell namnmatchning nära Josefina",
                )
            )
            if len(findings) >= limit:
                return findings

        reference_match = reference_suggestion(path.name, reference_candidates)
        if reference_match is not None:
            corrected_name, suggestion = reference_match
            findings.append(
                Finding(
                    path=path,
                    original=path.name,
                    replacement=corrected_name,
                    suggested_path=path.with_name(corrected_name),
                    explanation=f"nära referensord/medlemsnamn: {suggestion}",
                )
            )
            if len(findings) >= limit:
                return findings

    return findings


def format_report(
    root: Path,
    findings: list[Finding],
    unique_words: list[UniqueWord],
    numbers: dict[Path, str],
    limit: int,
) -> str:
    lines: list[str] = []

    if findings:
        lines.append(f"Stavfel i {root}:")
        for index, finding in enumerate(findings, start=1):
            lines.append(f"{index:03}. {finding.path}")
            lines.append(f"     fel:      {finding.original}")
            lines.append(f"     förslag:  {finding.replacement}")
            lines.append(f"     ändra ej: {finding.suggested_path}")
            lines.append(f"     orsak:    {finding.explanation}")

        if len(findings) >= limit:
            lines.append(f"Avbröt efter {limit} stavfel.")
        else:
            lines.append(f"Klart. Hittade {len(findings)} stavfel.")
    else:
        lines.append(f"Inga stavfel hittades i {root}.")

    lines.append("")
    lines.append(f"Ord som bara förekommer en gång i {root}:")
    used_numbers: set[str] = set()
    for unique_word in unique_words:
        used_numbers.add(unique_word.file_number)
        lines.append(f"{unique_word.word}\t{unique_word.file_number}")
    lines.append(f"Klart. Hittade {len(unique_words)} unika engångsord.")

    lines.append("")
    lines.append("Filnummer:")
    number_to_path = {number: path for path, number in numbers.items()}
    for number in sorted(used_numbers):
        lines.append(f"{number}\t{number_to_path[number]}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lista misstänkta stavfel i BB2:s filkatalog. "
            "Programmet gör inga ändringar."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("BB2"),
        help="katalog att kontrollera (standard: BB2)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["files"],
        help="katalognamn under root som inte ska analyseras (standard: files)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="max antal stavfel att skriva ut (standard: 1000)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("stavfel.txt"),
        help="rapportfil (standard: stavfel.txt)",
    )
    parser.add_argument(
        "--word-list",
        action="append",
        default=[],
        help="svensk ordlista som fil eller URL; kan anges flera gånger",
    )
    parser.add_argument(
        "--member-list",
        action="append",
        default=[],
        help=(
            "medlems-/namnlista från Sveriges Schackförbund som fil eller URL; "
            "kan anges flera gånger"
        ),
    )
    return parser.parse_args()


def main() -> int:
    configure_output()
    args = parse_args()
    if args.limit < 1:
        print("FEL: --limit måste vara minst 1.", file=sys.stderr)
        return 1

    try:
        paths = iter_catalog_paths(args.root, set(args.exclude))
        numbers = file_numbers(paths)
        reference_words = load_reference_words(args.word_list + args.member_list)
        reference_keys = {normalize_key(word) for word in reference_words}
        reference_candidates = reference_candidates_by_initial(reference_words)
        findings = find_spelling_errors(
            args.root, paths, reference_candidates, args.limit
        )
        unique_words = words_occurring_once(paths, numbers, reference_keys)
    except OSError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1

    report = format_report(args.root, findings, unique_words, numbers, args.limit)
    args.log.write_text(report + "\n", encoding="utf-8-sig")
    print(report)
    print(f"Rapport skriven till {args.log}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
