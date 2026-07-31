from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
FEEDS_DIRECTORY = ROOT_DIRECTORY / "feeds"
LATEST_FILE = FEEDS_DIRECTORY / "latest.json"
ARCHIVE_DIRECTORY = FEEDS_DIRECTORY / "archive"

MONTH_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$"
)


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as error:
        raise ValueError(
            f"Required file was not found: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {path}: {error}"
        ) from error


def extract_entries(
    payload: Any,
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("entries")
    else:
        entries = None

    if not isinstance(entries, list) or not entries:
        raise ValueError(
            "latest.json must contain a non-empty array "
            "or an object with a non-empty 'entries' array."
        )

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Entry {index} is not a JSON object."
            )

    return entries


def parse_bulletin_month(
    value: Any,
) -> date:
    if not isinstance(value, str):
        raise ValueError(
            "bulletinMonth must be a string."
        )

    match = MONTH_PATTERN.fullmatch(value.strip())

    if match is None:
        raise ValueError(
            "bulletinMonth must use YYYY-MM-DD format. "
            f"Received: {value!r}"
        )

    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError(
            f"Invalid bulletinMonth: {value}"
        ) from error

    if parsed.day != 1:
        raise ValueError(
            "bulletinMonth must be the first day of its month. "
            f"Received: {value}"
        )

    return parsed


def resolve_single_bulletin_month(
    entries: list[dict[str, Any]],
) -> date:
    months = {
        parse_bulletin_month(
            entry.get("bulletinMonth")
        )
        for entry in entries
    }

    if len(months) != 1:
        formatted = ", ".join(
            sorted(month.isoformat() for month in months)
        )

        raise ValueError(
            "latest.json must contain exactly one bulletin month. "
            f"Found: {formatted}"
        )

    return next(iter(months))


def normalized_json(
    payload: Any,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def archive_latest(
    *,
    replace_existing: bool = False,
) -> Path:
    payload = load_json(LATEST_FILE)
    entries = extract_entries(payload)
    bulletin_month = resolve_single_bulletin_month(
        entries
    )

    ARCHIVE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    archive_file = (
        ARCHIVE_DIRECTORY
        / f"{bulletin_month:%Y-%m}.json"
    )

    if archive_file.exists():
        existing_payload = load_json(archive_file)

        if normalized_json(existing_payload) == normalized_json(payload):
            print(
                f"Archive already current: {archive_file.name}"
            )

            return archive_file

        if not replace_existing:
            raise ValueError(
                f"{archive_file.name} already exists with "
                "different content. Review the difference before "
                "replacing it. To replace intentionally, rerun with "
                "--replace-existing."
            )

        print(
            f"Replacing existing archive: {archive_file.name}"
        )

    shutil.copyfile(
        LATEST_FILE,
        archive_file,
    )

    print(
        f"Archived {LATEST_FILE.name} "
        f"as {archive_file.name}"
    )

    return archive_file


def main() -> int:
    replace_existing = (
        "--replace-existing" in sys.argv[1:]
    )

    try:
        archive_latest(
            replace_existing=replace_existing
        )

        print("MONTHLY ARCHIVE PASSED")
        return 0

    except Exception as error:
        print(
            f"MONTHLY ARCHIVE FAILED: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
