#!/usr/bin/env python3

"""Validate a GreenPath Data Format v1 feed."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SUPPORTED_SCHEMA_VERSION = 1

ALLOWED_CATEGORIES = {
    "EB-1",
    "EB-2",
    "EB-3",
    "EB-3 Other Workers",
    "EB-4",
    "EB-4 Certain Religious Workers",
    "EB-5 Unreserved",
    "EB-5 Rural",
    "EB-5 High Unemployment",
    "EB-5 Infrastructure",
}

ALLOWED_COUNTRIES = {
    "Rest of World",
    "China",
    "India",
    "Mexico",
    "Philippines",
}

REQUIRED_TOP_LEVEL_FIELDS = {
    "schemaVersion",
    "generatedAt",
    "source",
    "entries",
}

REQUIRED_SOURCE_FIELDS = {
    "publisher",
    "bulletinType",
    "sourceURL",
    "retrievedAt",
}

REQUIRED_ENTRY_FIELDS = {
    "bulletinMonth",
    "category",
    "country",
    "finalActionDate",
    "filingDate",
}


class FeedValidationError(Exception):
    """Raised when the GreenPath feed does not pass validation."""


def parse_iso_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FeedValidationError(
            f"{field_name} must be a non-empty ISO-8601 timestamp."
        )

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise FeedValidationError(
            f"{field_name} is not a valid ISO-8601 timestamp: {value!r}"
        ) from error

    if parsed.tzinfo is None:
        raise FeedValidationError(
            f"{field_name} must include a timezone."
        )

    return parsed.astimezone(timezone.utc)


def parse_calendar_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise FeedValidationError(
            f"{field_name} must be a yyyy-MM-dd string."
        )

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise FeedValidationError(
            f"{field_name} is not a valid yyyy-MM-dd date: {value!r}"
        ) from error


def validate_url(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FeedValidationError(
            f"{field_name} must be a non-empty URL."
        )

    parsed = urlparse(value)

    if parsed.scheme != "https" or not parsed.netloc:
        raise FeedValidationError(
            f"{field_name} must be a valid HTTPS URL: {value!r}"
        )


def validate_cutoff(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FeedValidationError(
            f"{field_name} must contain C, U, or a yyyy-MM-dd date."
        )

    normalized = value.strip()

    if normalized in {"C", "U"}:
        return

    parse_calendar_date(normalized, field_name)


def require_exact_fields(
    object_value: dict[str, Any],
    required_fields: set[str],
    object_name: str,
) -> None:
    missing = required_fields - object_value.keys()

    if missing:
        raise FeedValidationError(
            f"{object_name} is missing required field(s): "
            f"{', '.join(sorted(missing))}"
        )


def validate_entry(
    entry: Any,
    index: int,
) -> tuple[str, str, str]:
    location = f"entries[{index}]"

    if not isinstance(entry, dict):
        raise FeedValidationError(
            f"{location} must be a JSON object."
        )

    require_exact_fields(
        entry,
        REQUIRED_ENTRY_FIELDS,
        location,
    )

    bulletin_month_value = entry["bulletinMonth"]
    bulletin_month = parse_calendar_date(
        bulletin_month_value,
        f"{location}.bulletinMonth",
    )

    if bulletin_month.day != 1:
        raise FeedValidationError(
            f"{location}.bulletinMonth must be the first day "
            f"of a month: {bulletin_month_value!r}"
        )

    category = entry["category"]

    if category not in ALLOWED_CATEGORIES:
        raise FeedValidationError(
            f"{location}.category is unsupported: {category!r}"
        )

    country = entry["country"]

    if country not in ALLOWED_COUNTRIES:
        raise FeedValidationError(
            f"{location}.country is unsupported: {country!r}"
        )

    validate_cutoff(
        entry["finalActionDate"],
        f"{location}.finalActionDate",
    )

    validate_cutoff(
        entry["filingDate"],
        f"{location}.filingDate",
    )

    return bulletin_month_value, category, country


def validate_feed(feed: Any) -> None:
    if not isinstance(feed, dict):
        raise FeedValidationError(
            "The feed root must be a JSON object."
        )

    require_exact_fields(
        feed,
        REQUIRED_TOP_LEVEL_FIELDS,
        "feed",
    )

    schema_version = feed["schemaVersion"]

    if not isinstance(schema_version, int):
        raise FeedValidationError(
            "schemaVersion must be an integer."
        )

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise FeedValidationError(
            "Unsupported schemaVersion: "
            f"{schema_version}. Expected "
            f"{SUPPORTED_SCHEMA_VERSION}."
        )

    generated_at = parse_iso_timestamp(
        feed["generatedAt"],
        "generatedAt",
    )

    source = feed["source"]

    if not isinstance(source, dict):
        raise FeedValidationError(
            "source must be a JSON object."
        )

    require_exact_fields(
        source,
        REQUIRED_SOURCE_FIELDS,
        "source",
    )

    publisher = source["publisher"]

    if not isinstance(publisher, str) or not publisher.strip():
        raise FeedValidationError(
            "source.publisher must be a non-empty string."
        )

    bulletin_type = source["bulletinType"]

    if not isinstance(bulletin_type, str) or not bulletin_type.strip():
        raise FeedValidationError(
            "source.bulletinType must be a non-empty string."
        )

    validate_url(
        source["sourceURL"],
        "source.sourceURL",
    )

    retrieved_at = parse_iso_timestamp(
        source["retrievedAt"],
        "source.retrievedAt",
    )

    if generated_at < retrieved_at:
        raise FeedValidationError(
            "generatedAt cannot be earlier than "
            "source.retrievedAt."
        )

    entries = feed["entries"]

    if not isinstance(entries, list):
        raise FeedValidationError(
            "entries must be a JSON array."
        )

    if not entries:
        raise FeedValidationError(
            "entries must contain at least one bulletin entry."
        )

    identities: set[tuple[str, str, str]] = set()

    for index, entry in enumerate(entries):
        identity = validate_entry(entry, index)

        if identity in identities:
            bulletin_month, category, country = identity

            raise FeedValidationError(
                "Duplicate bulletin entry found for "
                f"{bulletin_month}, {category}, {country}."
            )

        identities.add(identity)


def load_json(path: Path) -> Any:
    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as input_file:
            return json.load(input_file)

    except FileNotFoundError as error:
        raise FeedValidationError(
            f"Feed file was not found: {path}"
        ) from error

    except json.JSONDecodeError as error:
        raise FeedValidationError(
            "Invalid JSON at "
            f"line {error.lineno}, column {error.colno}: "
            f"{error.msg}"
        ) from error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a GreenPath Data Format v1 feed."
    )

    parser.add_argument(
        "feed_path",
        type=Path,
        help="Path to visa-bulletins.json",
    )

    arguments = parser.parse_args()

    try:
        feed = load_json(arguments.feed_path)
        validate_feed(feed)

    except FeedValidationError as error:
        print(f"VALIDATION FAILED: {error}", file=sys.stderr)
        return 1

    entry_count = len(feed["entries"])

    print(
        "VALIDATION PASSED: "
        f"{arguments.feed_path} contains "
        f"{entry_count} valid entries."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
