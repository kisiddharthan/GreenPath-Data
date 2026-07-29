"""Parse employment-based tables from an official Visa Bulletin page."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag


COUNTRY_COLUMN_MAP = {
    "all chargeability areas except those listed": "Rest of World",
    "china-mainland born": "China",
    "china mainland born": "China",
    "india": "India",
    "mexico": "Mexico",
    "philippines": "Philippines",
}

CATEGORY_MAP = {
    "1st": "EB-1",
    "2nd": "EB-2",
    "3rd": "EB-3",
    "other workers": "EB-3 Other Workers",
    "4th": "EB-4",
    "certain religious workers": "EB-4 Certain Religious Workers",
    "5th unreserved": "EB-5 Unreserved",
    "5th set aside: rural": "EB-5 Rural",
    "5th set aside: high unemployment": "EB-5 High Unemployment",
    "5th set aside: infrastructure": "EB-5 Infrastructure",
}

FINAL_ACTION_HEADING = (
    "FINAL ACTION DATES FOR EMPLOYMENT-BASED PREFERENCE CASES"
)

FILING_HEADING = (
    "DATES FOR FILING OF EMPLOYMENT-BASED VISA APPLICATIONS"
)


class BulletinParserError(Exception):
    """Raised when the official bulletin cannot be parsed safely."""

@dataclass(frozen=True)
class ParsedEmploymentEntry:
    category: str
    country: str
    final_action_date: str
    filing_date: str


def normalize_text(value: str) -> str:
    return " ".join(
        value.replace("\xa0", " ")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .split()
    )


def comparison_text(value: str) -> str:
    return normalize_text(value).lower()


def fetch_html(
    url: str,
    timeout_seconds: int = 30,
) -> str:
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    if response.status_code == 403:
        raise BulletinParserError(
            "The Department of State blocked the automated "
            "request with HTTP 403. Save the official page as "
            "HTML and run the parser with --html-file."
        )

    response.raise_for_status()

    if not response.text.strip():
        raise BulletinParserError(
            "The official Visa Bulletin page returned empty HTML."
        )

    return response.text


def parse_bulletin_month(
    html: str,
) -> date:
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.find(
        lambda tag: (
            isinstance(tag, Tag)
            and tag.name in {"h1", "h2"}
            and "visa bulletin for" in comparison_text(
                tag.get_text(" ", strip=True)
            )
        )
    )

    if heading is None:
        raise BulletinParserError(
            "Could not find the Visa Bulletin page title."
        )

    title = normalize_text(
        heading.get_text(" ", strip=True)
    )

    match = re.search(
        r"Visa Bulletin For ([A-Za-z]+) (\d{4})",
        title,
        flags=re.IGNORECASE,
    )

    if match is None:
        raise BulletinParserError(
            f"Could not parse bulletin month from title: {title!r}"
        )

    month_name, year_text = match.groups()

    parsed = datetime.strptime(
        f"{month_name} {year_text}",
        "%B %Y",
    )

    return date(parsed.year, parsed.month, 1)


def find_heading(
    soup: BeautifulSoup,
    expected_text: str,
) -> Tag:
    """
    Locate the most specific heading element.

    The official bulletin contains nested and malformed paragraph
    elements, so substring matching can select a large parent <p>
    that starts before an unrelated table.
    """

    expected = normalize_header(expected_text)

    candidates: list[Tag] = []

    for tag in soup.find_all(
        [
            "u",
            "strong",
            "b",
            "h1",
            "h2",
            "h3",
            "h4",
            "p",
        ]
    ):
        text = normalize_header(
            tag.get_text(" ", strip=True)
        )

        if text == expected:
            candidates.append(tag)

    if not candidates:
        raise BulletinParserError(
            f"Could not locate section: {expected_text}"
        )

    # Prefer the smallest, most specific matching element.
    return min(
        candidates,
        key=lambda tag: len(
            normalize_text(
                tag.get_text(" ", strip=True)
            )
        ),
    )


def find_table_after_heading(
    heading: Tag,
    section_name: str,
) -> Tag:
    """
    Find the employment-based table following the exact section
    heading.
    """

    for table in heading.find_all_next("table"):
        rows = table_rows(table)

        if not rows or not rows[0]:
            continue

        first_header = normalize_header(
            rows[0][0]
        )

        if first_header.startswith(
            "employmentbased"
        ):
            return table

    raise BulletinParserError(
        "Could not locate an employment-based table after "
        f"{section_name}."
    )

def table_rows(
    table: Tag,
) -> list[list[str]]:
    rows: list[list[str]] = []

    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])

        values = [
            normalize_text(
                cell.get_text(" ", strip=True)
            )
            for cell in cells
        ]

        if values:
            rows.append(values)

    if len(rows) < 2:
        raise BulletinParserError(
            "Employment table contains too few rows."
        )

    return rows


def normalize_header(value: str) -> str:
    """Normalize table headings for reliable matching."""

    normalized = comparison_text(value)

    # Remove footnote markers and all punctuation/spacing.
    return re.sub(
        r"[^a-z0-9]",
        "",
        normalized,
    )

def normalize_category(value: str) -> str | None:
    """
    Convert Department of State employment row labels into
    stable GreenPath category names.
    """

    normalized = normalize_header(value)

    if normalized == "1st":
        return "EB-1"

    if normalized == "2nd":
        return "EB-2"

    if normalized == "3rd":
        return "EB-3"

    if "otherworkers" in normalized:
        return "EB-3 Other Workers"

    if normalized == "4th":
        return "EB-4"

    if "certainreligiousworkers" in normalized:
        return "EB-4 Certain Religious Workers"

    if "5thunreserved" in normalized:
        return "EB-5 Unreserved"

    if (
        "5thsetaside" in normalized
        and "rural" in normalized
    ):
        return "EB-5 Rural"

    if (
        "5thsetaside" in normalized
        and "highunemployment" in normalized
    ):
        return "EB-5 High Unemployment"

    if (
        "5thsetaside" in normalized
        and "infrastructure" in normalized
    ):
        return "EB-5 Infrastructure"

    return None
    
def identify_country_columns(
    header_row: list[str],
) -> dict[int, str]:
    columns: dict[int, str] = {}

    normalized_country_names = {
        "allchargeabilityareasexceptthoselisted":
            "Rest of World",
        "chinamainlandborn":
            "China",
        "india":
            "India",
        "mexico":
            "Mexico",
        "philippines":
            "Philippines",
    }

    for index, value in enumerate(header_row):
        normalized = normalize_header(value)

        for expected_header, canonical_name in (
            normalized_country_names.items()
        ):
            if expected_header in normalized:
                columns[index] = canonical_name
                break

    expected_countries = {
        "Rest of World",
        "China",
        "India",
        "Mexico",
        "Philippines",
    }

    found_countries = set(columns.values())

    if found_countries != expected_countries:
        formatted_headers = [
            f"{index}: {value!r} "
            f"→ {normalize_header(value)!r}"
            for index, value in enumerate(header_row)
        ]

        raise BulletinParserError(
            "Employment table country columns did not match "
            "the expected set.\n"
            f"Found countries: {sorted(found_countries)}\n"
            "Parsed header cells:\n"
            + "\n".join(formatted_headers)
        )

    return columns


def canonical_category(
    raw_value: str,
) -> str | None:
    normalized = comparison_text(raw_value)

    normalized = re.sub(
        r"\([^)]*\)",
        "",
        normalized,
    )

    normalized = normalize_text(normalized)

    if normalized.startswith("5th unreserved"):
        return "EB-5 Unreserved"

    if "rural" in normalized and "5th" in normalized:
        return "EB-5 Rural"

    if (
        "high unemployment" in normalized
        and "5th" in normalized
    ):
        return "EB-5 High Unemployment"

    if (
        "infrastructure" in normalized
        and "5th" in normalized
    ):
        return "EB-5 Infrastructure"

    for official_name, canonical_name in CATEGORY_MAP.items():
        if normalized == official_name:
            return canonical_name

    return None


def normalize_cutoff(
    value: str,
) -> str:
    normalized = normalize_text(value).upper()

    if normalized in {"C", "U"}:
        return normalized

    compact = re.sub(
        r"[^0-9A-Z]",
        "",
        normalized,
    )

    try:
        parsed = datetime.strptime(
            compact,
            "%d%b%y",
        )
    except ValueError as error:
        raise BulletinParserError(
            f"Unsupported cutoff value: {value!r}"
        ) from error

    return parsed.date().isoformat()


def parse_employment_table(
    table: Tag,
) -> dict[tuple[str, str], str]:
    rows = table_rows(table)

    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if (
                row
                and normalize_header(
                    row[0]
                ).startswith("employmentbased")
                and any(
                    "allchargeabilityareas"
                    in normalize_header(cell)
                    for cell in row
                )
            )
        ),
        None,
    )

    if header_index is None:
        raise BulletinParserError(
            "Could not find the employment table header."
        )

    country_columns = identify_country_columns(
        rows[header_index]
    )

    parsed: dict[tuple[str, str], str] = {}

    pending_category_text = ""

    for row in rows[header_index + 1 :]:
        if not row:
            continue

        raw_category_text = normalize_text(row[0])

        if (
            normalize_header(raw_category_text)
            == "5thsetaside"
            and len(row) == 1
        ):
            pending_category_text = raw_category_text
            continue

        if pending_category_text:
            raw_category_text = (
                f"{pending_category_text} "
                f"{raw_category_text}"
            )
            pending_category_text = ""

        category = normalize_category(
            raw_category_text
        )

        if category is None:
            continue

        for column_index, country in (
            country_columns.items()
        ):
            if column_index >= len(row):
                raise BulletinParserError(
                    f"Missing {country} value "
                    f"for {category}. "
                    f"Parsed row: {row!r}"
                )

            parsed[(category, country)] = (
                normalize_cutoff(
                    row[column_index]
                )
            )

    if not parsed:
        raise BulletinParserError(
            "No employment-based entries were parsed."
        )

    return parsed

def normalize_category(
    value: str,
) -> str | None:
    normalized = normalize_header(value)

    if normalized == "1st":
        return "EB-1"

    if normalized == "2nd":
        return "EB-2"

    if normalized == "3rd":
        return "EB-3"

    if "otherworkers" in normalized:
        return "EB-3 Other Workers"

    if normalized == "4th":
        return "EB-4"

    if "certainreligiousworkers" in normalized:
        return "EB-4 Certain Religious Workers"

    if "5thunreserved" in normalized:
        return "EB-5 Unreserved"

    if (
        "5thsetaside" in normalized
        and "highunemployment" in normalized
    ):
        return "EB-5 High Unemployment"

    if (
        "5thsetaside" in normalized
        and "infrastructure" in normalized
    ):
        return "EB-5 Infrastructure"

    if (
        "5thsetaside" in normalized
        and "rural" in normalized
    ):
        return "EB-5 Rural"

    return None
    
def combine_tables(
    final_action: dict[tuple[str, str], str],
    filing: dict[tuple[str, str], str],
) -> list[ParsedEmploymentEntry]:
    final_keys = set(final_action)
    filing_keys = set(filing)

    if final_keys != filing_keys:
        missing_from_filing = sorted(
            final_keys - filing_keys
        )

        missing_from_final = sorted(
            filing_keys - final_keys
        )

        raise BulletinParserError(
            "The Final Action and Filing tables do not "
            "contain identical category-country combinations. "
            f"Missing from filing: {missing_from_filing}. "
            f"Missing from final action: {missing_from_final}."
        )

    return [
        ParsedEmploymentEntry(
            category=category,
            country=country,
            final_action_date=final_action[
                (category, country)
            ],
            filing_date=filing[
                (category, country)
            ],
        )
        for category, country in sorted(final_keys)
    ]


def parse_bulletin_html(
    html: str,
) -> tuple[date, list[ParsedEmploymentEntry]]:
    soup = BeautifulSoup(html, "html.parser")

    bulletin_month = parse_bulletin_month(html)

    final_heading = find_heading(
        soup,
        FINAL_ACTION_HEADING,
    )

    filing_heading = find_heading(
        soup,
        FILING_HEADING,
    )

    final_table = find_table_after_heading(
        final_heading,
        FINAL_ACTION_HEADING,
    )

    filing_table = find_table_after_heading(
        filing_heading,
        FILING_HEADING,
    )

    final_action = parse_employment_table(
        final_table
    )

    filing = parse_employment_table(
        filing_table
    )

    entries = combine_tables(
        final_action,
        filing,
    )

    return bulletin_month, entries


def parse_bulletin_url(
    url: str,
) -> tuple[date, list[ParsedEmploymentEntry]]:
    html = fetch_html(url)
    return parse_bulletin_html(html)
