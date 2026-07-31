from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]


def run_script(
    relative_path: str,
    *arguments: str,
) -> None:
    command = [
        sys.executable,
        str(ROOT_DIRECTORY / relative_path),
        *arguments,
    ]

    print()
    print("$", " ".join(command))

    subprocess.run(
        command,
        cwd=ROOT_DIRECTORY,
        check=True,
    )


def main() -> int:
    try:
        run_script(
            "scripts/archive_latest.py"
        )

        run_script(
            "scripts/build_history.py"
        )

        run_script(
            "scripts/validate_feeds.py"
	)
        print()
        print("MONTHLY FEED BUILD PASSED")

        return 0

    except subprocess.CalledProcessError as error:
        print()
        print(
            "MONTHLY FEED BUILD FAILED: "
            f"{error}",
            file=sys.stderr,
        )

        return error.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
