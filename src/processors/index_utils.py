"""Shared cancellable discovery and progress for the three index builders."""

import os
import time
from pathlib import Path


def report_progress(worker, completed, total, message):
    if worker and hasattr(worker, 'report_progress'):
        worker.report_progress(completed, total, message)


def find_sources(folder, extension, worker=None):
    sources = []
    last_report = 0

    def failed(error):
        raise error

    for root, directories, files in os.walk(folder, onerror=failed):
        if worker and worker.cancel_requested():
            break
        directories.sort()
        sources.extend(str(Path(root) / name) for name in files if name.lower().endswith(extension))
        now = time.monotonic()
        if now - last_report >= 0.1:
            report_progress(worker, 0, 0, f"Scanning folders: {len(sources)} {extension} files found\n{root}")
            last_report = now
    return sorted(sources)
