from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
FEEDS_DIRECTORY = ROOT_DIRECTORY / "feeds"
LATEST_FILE = FEEDS_DIRECTORY / "latest.json"
HISTORY_FILE = FEEDS_DIRECTORY / "history.json"
ARCHIVE_DIRECTORY = FEEDS_DIRECTORY / "archive"

REQUIRED_FIELDS = {
    "bulletinMonth",
    "category",
    "country",
    "finalActionDate",
    "filingDate",
}


def load_entries(
    path: Path,
) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as error:
        raise ValueError(
            f"Missing file: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path}: {error}"
        ) from error

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("entries")
    else:
        entries = None

    if not isinstance(entries, list):
        raise ValueError(
            f"{path} does not contain an entries array."
        )

    return entries


def normalize(value: Any) -> str:
    return str(value or "").strip().casefold()


def validate_date_value(
    value: Any,
    field_name: str,
    source: Path,
) -> None:
    if not isinstance(value, str):
        raise ValueError(
            f"{source}: {field_name} must be a string."
        )

    normalized = value.strip().upper()

    if normalized in {"C", "U"}:
        return

    try:
        date.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(
            f"{source}: invalid {field_name}: {value!r}"
        ) from error


def entry_key(
    entry: dict[str, Any],
) -> tuple[str, str, str]:
    return (
        str(entry["bulletinMonth"]).strip(),
        normalize(entry["category"]),
        normalize(entry["country"]),
    )


def validate_entries(
    entries: list[dict[str, Any]],
    source: Path,
) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"{source}: entry {index} is not an object."
            )

        missing = REQUIRED_FIELDS - entry.keys()

        if missing:
            raise ValueError(
                f"{source}: entry {index} is missing "
                f"{sorted(missing)}."
            )

        try:
            bulletin_month = date.fromisoformat(
                str(entry["bulletinMonth"])
            )
        except ValueError as error:
            raise ValueError(
                f"{source}: invalid bulletinMonth at "
                f"entry {index}."
            ) from error

        if bulletin_month.day != 1:
            raise ValueError(
                f"{source}: bulletinMonth must use the "
                "first day of the month."
            )

        validate_date_value(
            entry["finalActionDate"],
            "finalActionDate",
            source,
        )

        validate_date_value(
            entry["filingDate"],
            "filingDate",
            source,
        )

        key = entry_key(entry)

        if key in keys:
            raise ValueError(
                f"{source}: duplicate entry {key}."
            )

        keys.add(key)

    return keys


def main() -> int:
    try:
        latest_entries = load_entries(LATEST_FILE)
        history_entries = load_entries(HISTORY_FILE)

        latest_keys = validate_entries(
            latest_entries,
            LATEST_FILE,
        )

        history_keys = validate_entries(
            history_entries,
            HISTORY_FILE,
        )

        archive_files = sorted(
            ARCHIVE_DIRECTORY.glob("*.json")
        )

        if not archive_files:
            raise ValueError(
                "No archive files were found."
            )

        archive_keys: set[
            tuple[str, str, str]
        ] = set()

        for archive_file in archive_files:
            entries = load_entries(archive_file)

            file_keys = validate_entries(
                entries,
                archive_file,
            )

            duplicate_keys = (
                archive_keys & file_keys
            )

            if duplicate_keys:
                raise ValueError(
                    "Duplicate category/country/month entries "
                    f"across archive files: {duplicate_keys}"
                )

            archive_keys.update(file_keys)

        if history_keys != archive_keys:
            missing_from_history = (
                archive_keys - history_keys
            )

            unexpected_in_history = (
                history_keys - archive_keys
            )

            raise ValueError(
                "history.json does not match the archive. "
                f"Missing: {missing_from_history}; "
                f"Unexpected: {unexpected_in_history}"
            )

        if not latest_keys.issubset(history_keys):
            raise ValueError(
                "latest.json entries are not present in "
                "history.json."
            )

        month_count = len(
            {
                key[0]
                for key in history_keys
            }
        )

        print("FEED VALIDATION PASSED")
        print(
            f"Latest entries: {len(latest_keys)}"
        )
        print(
            f"History entries: {len(history_keys)}"
        )
        print(
            f"Bulletin months: {month_count}"
        )

        return 0

    except Exception as error:
        print(
            f"FEED VALIDATION FAILED: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
