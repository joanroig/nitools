"""Release content rules shared by PyInstaller and package verification."""

import json
from pathlib import Path
import re
import wave

RESOURCES = {
    "audio/.wav", "style.css", "hooks/plugin_runtime.py",
    *("icons/" + name + ".png" for name in (
        "arrow-right", "cog", "groups", "kits", "moai", "nitools-small",
        "nitools", "previews", "question", "terminal",
        "applemusic", "spotify", "bandcamp", "youtube")),
}
MICROSOFT_RUNTIME = re.compile(
    r"^(?P<base>(?:msvcp|vcruntime|concrt|vcomp|msvcr)\d+(?:_[a-z0-9_]+)?)(?:-[0-9a-f]+)?\.dll$", re.I)
PROHIBITED_SUFFIXES = {".mxgrp", ".mxprj", ".nbkt", ".nksf", ".nksn", ".nki", ".nicnt", ".vst3", ".vstpreset", ".fxp", ".fxb", ".ogg", ".mp3", ".aif", ".aiff", ".flac", ".ncw", ".gpr", ".i64"}


def checked_resources(root):
    root = Path(root)
    paths = [path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    actual = {path.relative_to(root).as_posix() for path in paths}
    if actual != RESOURCES:
        raise ValueError(f"Resource inventory changed; review before shipping. Added: {actual - RESOURCES}; missing: {RESOURCES - actual}")
    with wave.open(str(root / "audio/.wav"), "rb") as silence:
        if silence.getparams()[:4] != (2, 3, 48000, 2000) or any(silence.readframes(2001)):
            raise ValueError("The silence fixture changed or contains nonzero audio")
    return [(str(path), "resources/" + path.relative_to(root).parent.as_posix()) for path in paths]


def check_payload_name(name):
    normalized = name.replace("\\", "/")
    path = Path(normalized)
    if normalized.startswith('/') or '..' in path.parts or ':' in normalized:
        raise ValueError(f"Unsafe release payload path: {name}")
    if MICROSOFT_RUNTIME.match(path.name):
        raise ValueError(f"Microsoft runtime must not be bundled: {name}")
    if any(Path(part).suffix.casefold() in PROHIBITED_SUFFIXES for part in path.parts) or (path.suffix.casefold() == ".wav" and normalized != "resources/audio/.wav"):
        raise ValueError(f"Prohibited content in release payload: {name}")
    if normalized.startswith("resources/") and normalized[10:] not in RESOURCES:
        raise ValueError(f"Unreviewed resource in payload: {name}")
    if any(part.casefold() in {"in", "out", "tmp", "research", ".git"} for part in path.parts):
        raise ValueError(f"Local work must not be bundled: {name}")
    if path.name.casefold() in {"upids.json", "upids.txt", "nativeaccess.xml", "d3dcompiler_47.dll", "dxcompiler.dll", "dxil.dll"}:
        raise ValueError(f"Excluded vendor data or binary: {name}")


def without_microsoft_runtime(binaries, output):
    """Remove redistributables; retain only names/version requirements.

    NumPy wheels may rename MSVC DLLs. Runtime aliases are made from the user's
    installed System32 files in PyInstaller's private extraction directory.
    No Microsoft DLL bytes enter the release archive.
    """
    import pefile
    kept, aliases, versions = [], {}, {}
    for target, source, kind in binaries:
        match = MICROSOFT_RUNTIME.match(Path(target).name)
        if match is None:
            check_payload_name(target)
            kept.append((target, source, kind))
            continue
        system_name = match.group("base").lower() + ".dll"
        with pefile.PE(source, fast_load=True) as pe:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
            fixed = pe.VS_FIXEDFILEINFO[0]
            version = (fixed.FileVersionMS >> 16, fixed.FileVersionMS & 65535,
                       fixed.FileVersionLS >> 16, fixed.FileVersionLS & 65535)
        versions[system_name] = max(version, versions.get(system_name, (0, 0, 0, 0)))
        if Path(target).name.casefold() != system_name:
            aliases[target.replace("\\", "/")] = system_name
    if not versions:
        raise ValueError("No MSVC dependencies identified; the Windows build inventory needs review")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "runtime-aliases.json").write_text(json.dumps(aliases, indent=2), encoding="utf-8")
    (output / "runtime-requirements.txt").write_text(
        "".join(name + "|" + ".".join(map(str, version)) + "\n" for name, version in sorted(versions.items())), encoding="utf-8")
    return kept
