"""Shared exact-reference export for Battery kits and Maschine groups."""

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from formats.sample_paths import reference_root, resolve_sample_path, sample_references
from processors.audio_export import AudioExporter, resolved_path, safe_name
from models.matrix_config import MatrixConfig
from models.pad_filter_config import PadFilterConfig


class SampleCollectionProcessor(AudioExporter):
    """Export every stored sample zone and retain the recorded pad numbers."""

    def __init__(
        self, json_path, output_folder, *, kind, logger, trim_silence=False,
        normalize=False, sample_rate=None, bit_depth=None, matrix=None,
        enable_matrix=True, filter_pads=False, pad_filter=None,
        include_preview=False, skip_existing=False, fill_blanks=None,
    ):
        self.json_path = json_path
        self.output_folder = output_folder
        self.kind = kind
        self.logger = logger
        self.trim_silence = trim_silence
        self.normalize = normalize
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.matrix = MatrixConfig() if matrix is None else matrix
        if isinstance(self.matrix, dict):
            self.matrix = MatrixConfig(pads=self.matrix)
        self.enable_matrix = enable_matrix
        self.filter_pads = filter_pads
        self.pad_filter = PadFilterConfig() if pad_filter is None else pad_filter
        if isinstance(self.pad_filter, dict):
            self.pad_filter = PadFilterConfig(pads=self.pad_filter)
        self.include_preview = include_preview
        self.skip_existing = skip_existing
        self.fill_blanks = fill_blanks
        self.summary = {}
        self._executor = None

    def _matches_filter(self, samples: list[dict]) -> bool:
        if not self.filter_pads:
            return True
        for pad, keywords in self.pad_filter.pads.items():
            names = " ".join(
                str(sample.get("name", "")) + " " + " ".join(sample_references(sample))
                for sample in samples if sample.get("pad") == pad
            ).lower()
            if not any(keyword.lower() in names for keyword in keywords):
                return False
        return True

    def _fill_blank(self, pad: int, target_pad: int, folder: Path):
        source = Path(self.fill_blanks)
        if source.is_dir():
            choices = sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() == ".wav")
            source = random.choice(choices) if choices else None
        if source is None or not source.is_file():
            self.summary["missing"] += 1
            self.logger.error("No valid file to fill blank pad %s: %s", pad, self.fill_blanks)
            return
        self._copy(source, folder / f"{target_pad:02d}_{safe_name(source.stem)}.wav")

    def _export_record(self, record: dict, worker_instance):
        name = str(record.get(self.kind) or "Unknown")
        samples = record.get("samples", [])
        renderer = getattr(self, '_instrument_renderer', None)
        if renderer is not None:
            from formats.maschine import parse_maschine
            original = record.get('source_file')
            if not original or not Path(original).is_file():
                raise ValueError('Instrument rendering requires the original .mxgrp; rebuild the index if it has moved')
            samples = parse_maschine(Path(original).read_bytes(), include_plugin_state=True)['samples']
        if not self._matches_filter(samples):
            self.summary["filtered"] += 1
            return
        if renderer is not None:
            renderer.prepare_record(record, samples)
        folder = Path(self.output_folder)
        if record.get("expansion"):
            folder /= safe_name(str(record["expansion"]))
        folder /= safe_name(name)
        if not resolved_path(folder).is_relative_to(resolved_path(self.output_folder)):
            raise ValueError(f"Export folder resolves outside the selected output folder: {folder}")
        folder_key = str(resolved_path(folder)).casefold()
        if folder_key in self._output_folders:
            raise ValueError(f"Two records target the same export folder: {folder}")
        self._output_folders.add(folder_key)
        folder.mkdir(parents=True, exist_ok=True)
        root = reference_root(record)
        maschine_library = record.get("source") == "Maschine" and record.get("parser") == "structured-v1"

        # Each zone has an output slot, even if several pads reference the same
        # file or one pad has two zones pointing to the same file.
        by_pad: dict[int, list[tuple[str, bool]]] = {}
        empty_pads = set()
        occupied_pads = set()
        instruments = {}
        for sample in samples:
            pad = sample.get("pad")
            if not isinstance(pad, int) or pad < 1:
                raise ValueError(f"{name}: invalid pad number {pad!r}")
            refs = sample_references(sample)
            if sample.get("type") == "empty":
                empty_pads.add(pad)
                continue
            occupied_pads.add(pad)
            if sample.get("type") in {"instrument", "plugin", "no_sample"} and not refs:
                if renderer is not None and sample.get('instrument'):
                    instruments[pad] = sample
                    continue
                self.summary["omitted"] += 1
                continue
            if not refs:
                self.summary["missing"] += 1
                self.logger.error("[%s] pad %s: sample has no stored path", name, pad)
            metadata = [ref for ref in sample.get('sample_references', []) if ref.get('path')]
            for index, reference in enumerate(refs):
                namespace = maschine_library
                if index < len(metadata) and metadata[index].get('path') == reference:
                    namespace = namespace and metadata[index].get('path_kind', 2) == 2
                by_pad.setdefault(pad, []).append((reference, namespace))

        pads = set(by_pad) | set(instruments)
        if self.fill_blanks:
            pads.update(set(range(1, 17)) - occupied_pads)
            pads.update(empty_pads - occupied_pads)
        targets = set()
        for pad in sorted(pads):
            if worker_instance and worker_instance.cancel_requested():
                return False
            target_pad = self.matrix.pads.get(pad, pad) if self.enable_matrix else pad
            if not isinstance(target_pad, int) or target_pad < 1 or target_pad in targets:
                raise ValueError(f"{name}: matrix maps pad {pad} to invalid or duplicate output pad {target_pad}")
            targets.add(target_pad)
            if pad in instruments:
                from processors.instrument_render import export_instrument
                sample = instruments[pad]
                target = folder / f'{target_pad:02d}_{safe_name(sample.get("name") or "Instrument")}.wav'
                if self._executor is None:
                    self._record_result(export_instrument(self, renderer, sample, target))
                else:
                    self._pending.append(self._executor.submit(export_instrument, self, renderer, sample, target))
                    if len(self._pending) >= self._workers * 2:
                        self._record_result(self._pending.popleft().result())
                continue
            refs = by_pad.get(pad, [])
            if pad not in occupied_pads and self.fill_blanks:
                self._fill_blank(pad, target_pad, folder)
                continue
            for zone, (reference, namespace) in enumerate(refs, 1):
                if worker_instance and worker_instance.cancel_requested():
                    return False
                source = resolve_sample_path(reference, root, maschine_library=namespace)
                if source is None:
                    self.summary["missing"] += 1
                    self.logger.error("[%s] pad %s zone %s: unresolved exact path %r (root: %s)", name, pad, zone, reference, root)
                    continue
                prefix = f"{target_pad:02d}"
                if len(refs) > 1:
                    prefix += f"_{zone:02d}"
                prefix += "_" + safe_name(source.stem)
                self._copy(source, folder / (prefix + ".wav"))

        if worker_instance and worker_instance.cancel_requested():
            return False
        if self.include_preview and record.get("preview"):
            preview = resolve_sample_path(record["preview"], root)
            if preview is None:
                self.summary["missing"] += 1
                self.logger.error("[%s] unresolved preview path: %r", name, record["preview"])
            else:
                self._copy(preview, folder / ("00_PREVIEW - " + safe_name(name) + ".wav"))
        self.summary["collections"] += 1
        return True

    def run(self, worker_instance=None):
        self._start_export(worker_instance)
        self._output_folders = set()
        try:
            self._instrument_renderer = None
            render_options = getattr(self, 'render_options', None)
            if render_options is not None and (render_options.enabled or render_options.native_enabled):
                from processors.instrument_render import InstrumentRenderer
                self._instrument_renderer = InstrumentRenderer(render_options)
                self.logger.info('Instrument rendering enabled: external MIDI %s, velocity %s, %.2fs held + %.2fs release. Prepared Maschine kits use each pad’s saved pitch and routing.',
                                 render_options.note, render_options.velocity, render_options.hold, render_options.tail)
            with open(self.json_path, encoding="utf-8") as source:
                records = json.load(source)
            if not isinstance(records, list) or not records:
                raise ValueError("The sample index contains no kits/groups; rebuild it from the original files")
            if any(not isinstance(record, dict) or record.get("parser") != "structured-v1" for record in records):
                raise ValueError("This index uses an older or unknown parser. Rebuild it from the original kit/group files in Step 1 before exporting.")
            self._total = len(records)
            # libsndfile/NumPy/soxr release the GIL. Parallelize conversion,
            # while planning paths, counters, and collection order stay serial.
            with ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="audio-export") as executor:
                self._executor = executor if self.trim_silence or self.normalize or self.sample_rate or self.bit_depth or self._instrument_renderer else None
                for number, record in enumerate(records, 1):
                    if worker_instance and worker_instance.cancel_requested():
                        return self._cancelled()
                    self._current_name = str(record.get(self.kind) or "Unknown")
                    self.logger.info("[%s/%s] Exporting %s: %s", number, self._total, self.kind, self._current_name)
                    self._report_progress(force=True)
                    cancelled = False
                    try:
                        cancelled = self._export_record(record, worker_instance) is False
                    except Exception as exc:
                        self.summary["errors"] += 1
                        self.logger.error("Could not export %s %r: %s", self.kind, self._current_name, exc)
                    finally:
                        self._drain()
                        if self._instrument_renderer is not None:
                            self._instrument_renderer.close_record()
                    if cancelled or worker_instance and worker_instance.cancel_requested():
                        return self._cancelled()
                    self._completed = number
                    self._report_progress(force=True)
                    self.logger.info("[%s/%s] Finished %s — totals: %s exported, %s skipped, %s unresolved, %s errors.",
                                     number, self._total, self._current_name, self.summary["exported"],
                                     self.summary["skipped"], self.summary["missing"], self.summary["errors"])
        except Exception as exc:
            self.summary["errors"] += 1
            self.logger.error("Could not read sample index: %s", exc)
        finally:
            self._executor = None
            if self._instrument_renderer is not None:
                self._instrument_renderer.close_record()
        if worker_instance and worker_instance.cancel_requested():
            return self._cancelled()
        incomplete = self.summary["missing"] or self.summary["errors"]
        if not incomplete and not self.summary["exported"] and not self.summary["skipped"]:
            self.logger.warning("No sample files exported (filtered: %s; pads without sample references: %s).", self.summary["filtered"], self.summary["omitted"])
            return 1
        log = self.logger.error if incomplete else self.logger.info
        log(
            "Export %s: %s collections, %s files exported, %s existing files skipped, %s unresolved paths, %s errors, %s filtered, %s pads without sample references omitted.",
            "incomplete" if incomplete else "complete", self.summary["collections"],
            self.summary["exported"], self.summary["skipped"], self.summary["missing"],
            self.summary["errors"], self.summary["filtered"], self.summary["omitted"],
        )
        return 1 if incomplete else 0
