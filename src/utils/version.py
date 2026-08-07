"""App version, resolved at runtime from the ``version`` field of pyproject.toml.

Keep this module standard-library only: it is imported both as ``utils.version``
(app, with ``src`` on the path) and as ``src.utils.version`` (CI and bundlers).
"""

import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

DISTRIBUTION_NAME = "nitools"
FALLBACK_VERSION = "0.0.0"

# Configuration file version
CONFIG_VERSION = "1.0"


def _read_pyproject_version(pyproject: Path):
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) else None


def _candidate_pyproject_paths(module_file: Path):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # Bundled app: the rest of the tree is a temp dir, so don't walk it
        yield Path(meipass) / "pyproject.toml"
        return
    for parent in module_file.resolve().parents:
        yield parent / "pyproject.toml"


def resolve_app_version(module_file, distribution_name: str) -> str:
    for candidate in _candidate_pyproject_paths(Path(module_file)):
        version = _read_pyproject_version(candidate)
        if version:
            return version
    try:
        return distribution_version(distribution_name)
    except PackageNotFoundError:
        return FALLBACK_VERSION


def build_app_version_text(app_version: str) -> str:
    return (
        "<a href='https://github.com/joanroig/nitools' title='Visit NITools GitHub repository'>NITools</a>"
        " by <a href='http://instagram.com/moaibeats' title='Visit @moaibeats on Instagram'>@moaibeats</a>"
        f" - Version <a href='https://github.com/joanroig/nitools/releases' title='View releases'> {app_version}</a>"
    )


# App version
APP_VERSION = resolve_app_version(Path(__file__), distribution_name=DISTRIBUTION_NAME)

# Version text to be used application-wide
APP_VERSION_TEXT = build_app_version_text(APP_VERSION)
