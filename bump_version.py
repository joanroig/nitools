#!/usr/bin/env python3
# This script is used by the GitHub Action defined in .github/workflows/create-release.yml
# It automatically bumps the application version based on the specified bump type.

import os
import sys
from typing import Literal

VERSION_FILE = os.path.join(os.path.dirname(__file__), "src", "utils", "version.py")

BUMP_TYPE = Literal["patch", "minor", "major"]

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

def main():
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py [patch|minor|major]", file=sys.stderr)
        sys.exit(1)
    bump = sys.argv[1]
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    new_version = None
    for line in lines:
        if line.strip().startswith("APP_VERSION ="):
            old_version = line.split("=")[1].strip().strip('"')
            new_version = bump_version(old_version, bump)
            new_lines.append(f'APP_VERSION = "{new_version}"\n')
        else:
            new_lines.append(line)
    if new_version is None:
        print("APP_VERSION not found in version.py", file=sys.stderr)
        sys.exit(1)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(new_version)


if __name__ == "__main__":
    main()
