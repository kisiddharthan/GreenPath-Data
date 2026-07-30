from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
ARCHIVE_DIRECTORY = ROOT_DIRECTORY / "feeds" / "archive"
OUTPUT_FILE = ROOT_DIRECTORY / "feeds" / "history.json"


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path}: {error}"
        ) from error


def extract_entries(
    payload: Any,
    source_path: Path,
) -> list[dict[str, Any]]:
    """
    Supports either:

    1. A top-level JSON array
    2. An object containing an `entries` array
    """

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("entries")
    else:
        entries = None

    if not isinstance(entries, list):
        raise ValueError(
            f"{source_path} must contain a JSON array "
            "or an object with an 'entries' array."
        )

    valid_entries: list[dict[str, Any]] = []

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"{source_path}: entry {index} is not an object."
            )

        valid_entries.append(entry)

    return valid_entries


def normalized_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def bulletin_month(entry: dict[str, Any]) -> str:
    value = entry.get("bulletinMonth")

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "Every history entry must contain a bulletinMonth."
        )

    return value.strip()


def unique_key(
    entry: dict[str, Any],
) -> tuple[str, str, str]:
    return (
        bulletin_month(entry),
        normalized_text(entry.get("category")),
        normalized_text(entry.get("country")),
    )


def sort_key(
    entry: dict[str, Any],
) -> tuple[str, str, str]:
    return (
        bulletin_month(entry),
        normalized_text(entry.get("category")),
        normalized_text(entry.get("country")),
    )


def build_history() -> list[dict[str, Any]]:
    if not ARCHIVE_DIRECTORY.exists():
        raise FileNotFoundError(
            f"Archive directory does not exist: "
            f"{ARCHIVE_DIRECTORY}"
        )

    archive_files = sorted(
        ARCHIVE_DIRECTORY.glob("*.json")
    )

    if not archive_files:
        raise ValueError(
            "No archived bulletin files were found."
        )

    entries_by_key: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = {}

    for archive_file in archive_files:
        print(f"Reading {archive_file.name}")

        payload = load_json(archive_file)
        entries = extract_entries(
            payload,
            archive_file,
        )

        for entry in entries:
            key = unique_key(entry)

            if key in entries_by_key:
                print(
                    "Replacing duplicate history entry: "
                    f"{key}"
                )

            entries_by_key[key] = entry

    history = sorted(
        entries_by_key.values(),
        key=sort_key,
    )

    return history


def write_history(
    history: list[dict[str, Any]],
) -> None:
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            history,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")


def main() -> int:
    try:
        history = build_history()
        write_history(history)

        months = {
            bulletin_month(entry)
            for entry in history
        }

        print()
        print("HISTORY GENERATION PASSED")
        print(f"Entries: {len(history)}")
        print(f"Bulletin months: {len(months)}")
        print(f"Output: {OUTPUT_FILE}")

        return 0

    except Exception as error:
        print(
            f"HISTORY GENERATION FAILED: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
