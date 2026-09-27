#!/usr/bin/env python3
"""Persist a user-facing opportunity-radar report without overwriting prior runs."""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path


REPORT_NAME_RE = re.compile(r"^(?P<date>\d{8})-(?P<sequence>\d+)\.md$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save a report as YYYYMMDD-NN.md in the opportunity-radar reports directory."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Markdown draft to save; omit it to read the draft from standard input.",
    )
    return parser.parse_args()


def report_directory() -> Path:
    project_dir = Path(
        os.environ.get("OPPORTUNITY_RADAR_PROJECT_DIR", os.getcwd())
    ).expanduser()
    configured_dir = os.environ.get("OPPORTUNITY_RADAR_REPORT_DIR")
    if configured_dir:
        return Path(configured_dir).expanduser()
    return project_dir / ".opportunity-radar" / "reports"


def read_draft(input_path: Path | None) -> bytes:
    content = sys.stdin.buffer.read() if input_path is None else input_path.read_bytes()
    if not content.strip():
        raise ValueError("Report content must not be empty.")
    return content if content.endswith(b"\n") else content + b"\n"


def save_report(directory: Path, content: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    date_token = datetime.now().astimezone().strftime("%Y%m%d")
    highest = 0
    for candidate in directory.iterdir():
        match = REPORT_NAME_RE.match(candidate.name)
        if match and match.group("date") == date_token:
            highest = max(highest, int(match.group("sequence")))
    sequence = highest + 1
    while True:
        target = directory / f"{date_token}-{sequence:02d}.md"
        try:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
        except FileExistsError:
            sequence += 1
            continue
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        return target


def main() -> int:
    args = parse_args()
    try:
        content = read_draft(args.input)
        target = save_report(report_directory(), content)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
