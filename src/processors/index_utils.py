"""Shared cancellable discovery and progress for the three index builders."""

import os
import json
import time
from pathlib import Path

from processors.parallel_decode import decoded_files
from utils.file_utils import atomic_write


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


def build_sample_index(sources, destination, decoder, process_file, *,
                       generate_txt, worker, logger, label):
    """Shared Battery/Groups coordination; format-specific metadata stays in callers."""
    destination = Path(destination)
    records, errors = [], []

    def cancelled():
        return worker is not None and worker.cancel_requested()

    def progress(completed, source=None):
        message = f"{completed}/{len(sources)} {label} processed"
        if source is not None:
            message += f" — {Path(source).stem}"
        report_progress(worker, completed, len(sources),
                        f"{message}\n{len(records)} decoded · {len(errors)} errors")

    progress(0)
    with decoded_files(sources, decoder, worker) as results:
        for number, (source, decoded, error) in enumerate(results, 1):
            if cancelled():
                break
            progress(number - 1, source)
            try:
                if error is not None:
                    raise ValueError(error)
                record = process_file(source, str(destination.parent),
                                      generate_txt=generate_txt, decoded=decoded)
                if record is not None:
                    records.append(record)
            except Exception as exc:
                errors.append({"path": source, "error": str(exc)})
                logger.error("Could not decode '%s': %s", source, exc)
            progress(number)
    if cancelled():
        logger.info("%s JSON build cancelled by user.", label.capitalize())
        return 1
    atomic_write(destination, (json.dumps(records, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    report_path = destination.with_suffix(".report.json")
    report = {"parser": "structured-v1", "files": len(sources),
              "decoded": len(records), "errors": errors}
    atomic_write(report_path, (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    incomplete = bool(errors) or not sources
    log = logger.error if incomplete else logger.info
    log("%s index %s: %s decoded, %s errors. Saved to %s; details: %s",
        label.capitalize(), "incomplete" if incomplete else "complete",
        len(records), len(errors), destination, report_path)
    return int(incomplete)
