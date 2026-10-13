"""Resolve serialized sample references without changing their filenames."""

import os
from pathlib import Path, PureWindowsPath


def reference_root(record: dict) -> Path:
    """Find the library root for a kit, or use a builder's explicit root."""
    if record.get("sample_root"):
        return Path(record["sample_root"])
    source = Path(record.get("path") or ".")
    if source.suffix.lower() not in {".nbkt", ".mxgrp"}:
        return source
    for folder in source.parents:
        if (folder / "Samples").is_dir():
            return folder
    return source.parent


def resolve_sample_path(reference: str, root: str | Path, *, maschine_library: bool = False) -> Path | None:
    """Resolve only the complete stored path; never search by basename.

    Windows separators are accepted in a library-relative reference on every
    platform. An unavailable absolute path remains unresolved, including a
    Windows absolute path opened on another platform.
    """
    if not isinstance(reference, str) or not reference or "\0" in reference:
        return None
    # Maschine's serialized library namespace is not a network server named
    # Samples. The legacy /Samples/ form has the same alias-path meaning.
    # Only these exact markers qualify; ordinary UNC paths stay
    # absolute, and the original string remains unchanged in the index.
    if maschine_library and reference.startswith(("//Samples/", "/Samples/")):
        reference = reference.lstrip("/")
    path = Path(reference.replace("\\", os.sep))
    if PureWindowsPath(reference).is_absolute() and os.name != "nt":
        return None
    if not path.is_absolute():
        path = Path(root) / path
    return path if path.is_file() else None


def sample_references(sample: dict) -> list[str]:
    """Accept both historical JSON shapes without deduplicating sample zones."""
    paths = sample.get("paths", sample.get("path", []))
    if isinstance(paths, str):
        return [paths] if paths else []
    if isinstance(paths, list):
        return paths
    raise ValueError("Sample paths must be a string or a list of strings")
