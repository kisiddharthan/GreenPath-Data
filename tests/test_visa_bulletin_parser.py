import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def july_2026_feed(tmp_path: Path) -> dict:
    output_file = tmp_path / "july-2026.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "parser.generate_feed",
            "--url",
            (
                "https://travel.state.gov/content/travel/en/legal/"
                "visa-law0/visa-bulletin/2026/"
                "visa-bulletin-for-july-2026.html"
            ),
            "--html-file",
            "tests/fixtures/july-2026-official.html",
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Feed generation failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert output_file.exists()

    with output_file.open(encoding="utf-8") as file:
        return json.load(file)


def test_july_2026_feed_has_50_entries(
    july_2026_feed: dict,
) -> None:
    assert len(july_2026_feed["entries"]) == 50


def test_july_2026_eb2_india_values(
    july_2026_feed: dict,
) -> None:
    matching_entries = [
        entry
        for entry in july_2026_feed["entries"]
        if (
            entry["category"] == "EB-2"
            and entry["country"] == "India"
        )
    ]

    assert len(matching_entries) == 1

    entry = matching_entries[0]

    assert entry["finalActionDate"] == "U"
    assert entry["filingDate"] == "2015-01-15"


def test_category_country_pairs_are_unique(
    july_2026_feed: dict,
) -> None:
    pairs = [
        (entry["category"], entry["country"])
        for entry in july_2026_feed["entries"]
    ]

    assert len(pairs) == len(set(pairs))
