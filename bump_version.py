#!/usr/bin/env python3
"""Bump the version in place and print the new one. Used by create-release.yml.

    python bump_version.py --file pyproject.toml --bump patch --variable version
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

BUMP_TYPE = Literal["patch", "minor", "major"]

DEFAULT_FILE = "pyproject.toml"
DEFAULT_VARIABLE = "version"


def bump_version(version: str, bump: BUMP_TYPE) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version: {version}")
    major, minor, patch = map(int, parts)
    if bump == "patch":
        patch += 1
    elif bump == "minor":
        minor += 1
        patch = 0
    elif bump == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unknown bump type: {bump}")
    return f"{major}.{minor}.{patch}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump a semantic version assignment in a file.")
    parser.add_argument("--file", default=DEFAULT_FILE, help=f"File holding the version (default: {DEFAULT_FILE})")
    parser.add_argument("--bump", required=True, choices=["patch", "minor", "major"], help="Type of version bump")
    parser.add_argument("--variable", default=DEFAULT_VARIABLE, help=f"Name of the version assignment (default: {DEFAULT_VARIABLE})")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        path = Path(__file__).parent / path

    try:
        # newline="" keeps the original line endings intact on the round-trip
        with path.open("r", encoding="utf-8", newline="") as f:
            content = f.read()
    except OSError as e:
        print(f"Could not read {path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Matches both `version = "1.2.3"` (TOML) and `APP_VERSION = "1.2.3"` (Python)
    pattern = re.compile(
        rf'^(?P<prefix>\s*{re.escape(args.variable)}\s*=\s*)(?P<quote>["\'])(?P<version>[^"\']+)(?P=quote)',
        re.MULTILINE,
    )
    match = pattern.search(content)
    if match is None:
        print(f"'{args.variable}' assignment not found in {path}", file=sys.stderr)
        sys.exit(1)

    try:
        new_version = bump_version(match.group("version"), args.bump)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    replacement = f'{match.group("prefix")}{match.group("quote")}{new_version}{match.group("quote")}'
    content = content[: match.start()] + replacement + content[match.end():]
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(content)

    print(new_version)


if __name__ == "__main__":
    main()
