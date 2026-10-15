
import re
import os
import tempfile
from pathlib import Path

def sanitize(s: str):
    """
    Make a string safe for filenames:
    - Strip leading/trailing whitespace
    - Replace spaces with underscores
    - Remove characters that are not alnum, underscore, hyphen or dot
    - Collapse repeated underscores
    """
    if not s:
        return "unknown"
    s = s.strip()
    s = s.replace(" ", "_")
    s = re.sub(r'[^A-Za-z0-9_\-\.]', '', s)
    s = re.sub(r'_+', '_', s)
    return s or "unknown"


def ensure_unique_path(folder: str, filename: str) -> str:
    """
    If filename already exists in folder, append _1, _2, ... until unique.
    Returns the absolute filepath.
    """
    base, ext = os.path.splitext(filename)
    candidate = filename
    n = 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base}_{n}{ext}"
        n += 1
    return os.path.join(folder, candidate)


def atomic_write(path, data):
    """Replace a file only after all bytes have been written and closed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.nitools-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
