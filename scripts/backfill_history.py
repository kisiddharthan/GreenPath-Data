from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
ARCHIVE_DIRECTORY = ROOT_DIRECTORY / "feeds" / "archive"


BULLETINS = [
    (
        "2026-06",
        "https://travel.state.gov/content/travel/en/legal/"
        "visa-law0/visa-bulletin/2026/"
        "visa-bulletin-for-june-2026.html",
        "fixtures/june-2026-official.html",
    ),
    (
        "2026-05",
        "https://travel.state.gov/content/travel/en/legal/"
        "visa-law0/visa-bulletin/2026/"
        "visa-bulletin-for-may-2026.html",
        "fixtures/may-2026-official.html",
    ),
    (
        "2026-04",
        "https://travel.state.gov/content/travel/en/legal/"
        "visa-law0/visa-bulletin/2026/"
        "visa-bulletin-for-april-2026.html",
        "fixtures/april-2026-official.html",
    ),
]


def run_parser(
    month: str,
    url: str,
    html_file: str,
) -> None:
    output_file = (
        ARCHIVE_DIRECTORY
        / f"{month}.json"
    )

    if output_file.exists():
        print(
            f"Skipping existing archive: "
            f"{output_file.name}"
        )
        return

    command = [
        "bash",
        str(
            ROOT_DIRECTORY
            / "scripts"
            / "generate_official_feed.sh"
        ),
        url,
        html_file,
        str(output_file),
    ]

    print()
    print("$", " ".join(command))

    subprocess.run(
        command,
        cwd=ROOT_DIRECTORY,
        check=True,
    )


def run_python_script(
    relative_path: str,
) -> None:
    command = [
        sys.executable,
        str(ROOT_DIRECTORY / relative_path),
    ]

    print()
    print("$", " ".join(command))

    subprocess.run(
        command,
        cwd=ROOT_DIRECTORY,
        check=True,
    )


def main() -> int:
    ARCHIVE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        for month, url, html_file in BULLETINS:
            run_parser(
                month,
                url,
                html_file,
            )

        run_python_script(
            "scripts/build_history.py"
        )

        run_python_script(
            "scripts/validate_feeds.py"
        )

        print()
        print("HISTORICAL BACKFILL PASSED")

        return 0

    except subprocess.CalledProcessError as error:
        print(
            "HISTORICAL BACKFILL FAILED: "
            f"{error}",
            file=sys.stderr,
        )

        return error.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
