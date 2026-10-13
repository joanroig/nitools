"""Bounded audio conversion, atomic writes and progress shared by all exporters."""

import os
import re
import shutil
import tempfile
import time
from collections import deque
from pathlib import Path

from utils.audio_utils import trim_and_normalize_wav


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "Unknown"
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.IGNORECASE):
        name = "_" + name
    return name


def resolved_path(path):
    # Windows can return an extended-length spelling while a parallel writer
    # creates a previously absent parent. Keep containment/collision keys stable.
    value = str(Path(path).resolve())
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value)


class AudioExporter:
    def _start_export(self, worker_instance):
        self.summary = dict.fromkeys(("collections", "exported", "skipped", "missing", "errors", "filtered", "omitted", "cancelled"), 0)
        self._worker = worker_instance
        self._pending = deque()
        self._workers = min(4, os.cpu_count() or 1)
        self._executor = None
        self._completed, self._total, self._current_name = 0, 0, "Reading index"
        self._last_progress = 0

    def _copy(self, source: Path, target: Path):
        if self._executor is None:
            self._record_result(self._write_sample(source, target))
        else:
            self._pending.append(self._executor.submit(self._write_sample, source, target))
            # Bound pending work and memory, and keep cancellation responsive.
            if len(self._pending) >= self._workers * 2:
                self._record_result(self._pending.popleft().result())

    def _record_result(self, result):
        if result != "cancelled":
            self.summary[result] += 1
        self._report_progress()

    def _drain(self):
        while self._pending:
            self._record_result(self._pending.popleft().result())

    def _report_progress(self, force=False):
        worker = getattr(self, "_worker", None)
        if worker and hasattr(worker, "report_progress"):
            now = time.monotonic()
            if not force and now - self._last_progress < 0.1:
                return
            self._last_progress = now
            worker.report_progress(
                self._completed, self._total,
                f"{self._completed}/{self._total} {self.kind}s completed — {self._current_name}\n"
                f"{self.summary['exported']} exported · {self.summary['skipped']} skipped · "
                f"{self.summary['missing'] + self.summary['errors']} problems",
            )

    def _write_sample(self, source: Path, target: Path):
        temporary = None
        try:
            if self._worker and self._worker.cancel_requested():
                return "cancelled"
            if resolved_path(source) == resolved_path(target):
                raise ValueError("Output would overwrite the original sample; choose a separate output folder")
            if self.skip_existing and target.is_file():
                return "skipped"
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".nitools-", suffix=".wav", dir=target.parent, delete=False) as scratch:
                temporary = Path(scratch.name)
            if self.trim_silence or self.normalize or self.sample_rate or self.bit_depth or source.suffix.lower() != ".wav":
                trim_and_normalize_wav(
                    str(source), str(temporary), self.trim_silence, self.normalize,
                    self.sample_rate, self.bit_depth,
                )
            else:
                shutil.copy2(source, temporary)
            if self._worker and self._worker.cancel_requested():
                return "cancelled"
            temporary.replace(target)
            return "exported"
        except Exception as exc:
            self.logger.error("Could not export '%s' to '%s': %s", source, target, exc)
            return "errors"
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _cancelled(self):
        self.summary["cancelled"] = True
        self.logger.info("Export cancelled by user: %s files exported, %s skipped, %s unresolved paths, %s errors.",
                         self.summary["exported"], self.summary["skipped"], self.summary["missing"], self.summary["errors"])
        return 1
