"""Generate GreenPath Data Format v1 from an official bulletin."""

from __future__ import annotations

import argparse
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

from parser.visa_bulletin_parser import (
    BulletinParserError,
    parse_bulletin_html,
    parse_bulletin_url,
)

DEFAULT_OUTPUT_PATH = Path(
    "docs/visa-bulletins.json"
)


def iso_timestamp(
    value: datetime,
) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def build_feed(
    source_url: str,
    html_file: Path | None = None,
) -> dict:
    retrieved_at = datetime.now(timezone.utc)

    if html_file is not None:
        if not html_file.exists():
            raise BulletinParserError(
                f"HTML file was not found: {html_file}"
            )

        html = html_file.read_text(
            encoding="utf-8"
        )

        bulletin_month, parsed_entries = (
            parse_bulletin_html(html)
        )
    else:
        bulletin_month, parsed_entries = (
            parse_bulletin_url(source_url)
        )

    generated_at = datetime.now(timezone.utc)

    entries = [
        {
            "bulletinMonth": bulletin_month.isoformat(),
            "category": entry.category,
            "country": entry.country,
            "finalActionDate": entry.final_action_date,
            "filingDate": entry.filing_date,
        }
        for entry in parsed_entries
    ]

    return {
        "schemaVersion": 1,
        "generatedAt": iso_timestamp(generated_at),
        "source": {
            "publisher": "U.S. Department of State",
            "bulletinType":
                "Employment-Based Visa Bulletin",
            "sourceURL": source_url,
            "retrievedAt": iso_timestamp(retrieved_at),
        },
        "entries": entries,
    }


def write_feed(
    feed: dict,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_suffix(
        ".json.tmp"
    )

    temporary_path.write_text(
        json.dumps(
            feed,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_path.replace(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a GreenPath v1 feed from an "
            "official Department of State bulletin."
        )
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Official Visa Bulletin webpage URL.",
    )

    parser.add_argument(
        "--html-file",
        type=Path,
        help=(
            "Optional local HTML file downloaded from the "
            "official Visa Bulletin page."
        ),
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON path.",
    )

    arguments = parser.parse_args()

    try:
        feed = build_feed(
            source_url=arguments.url,
            html_file=arguments.html_file,
        )

        if not feed["entries"]:
            raise BulletinParserError(
                "Parser generated an empty feed."
            )

        write_feed(
            feed,
            arguments.output,
        )

    except (
        BulletinParserError,
        requests.RequestException,
    ) as error:
        print(
            f"FEED GENERATION FAILED: {error}"
        )
        return 1

    print(
        "FEED GENERATION PASSED: "
        f"wrote {len(feed['entries'])} entries "
        f"to {arguments.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
