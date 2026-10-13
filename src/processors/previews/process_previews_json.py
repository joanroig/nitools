import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from processors.audio_export import AudioExporter, resolved_path, safe_name
from processors.previews.product_names import load_product_names
from utils.logger import Logger

logger = Logger.get_logger("PreviewsProcessor")

class PreviewsProcessor(AudioExporter):
    def __init__(
        self,
        json_path,
        output_folder,
        trim_silence=False,
        normalize=False,
        sample_rate=None,
        bit_depth=None,
        skip_existing=False,
        skip_native_browser_preview_library=False,
        find_real_instrument_folder=False,
        skip_maschine_folders=False,
        skip_battery_kits=False,
    ):
        self.json_path = json_path
        self.output_folder = output_folder
        self.trim_silence = trim_silence
        self.normalize = normalize
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.skip_existing = skip_existing
        self.skip_maschine_folders = skip_maschine_folders
        self.skip_battery_kits = skip_battery_kits
        self.skip_native_browser_preview_library = skip_native_browser_preview_library
        self.find_real_instrument_folder = find_real_instrument_folder
        self.upids = {}
        self.logger = logger
        self.kind = "preview"
        self.summary = {}

    def _record_result(self, result):
        if result != "cancelled":
            self._completed += 1
        super()._record_result(result)
        now = time.monotonic()
        if now - self._last_log >= 1 or self._completed == self._total:
            logger.info("[%s/%s] Previews: %s exported, %s skipped, %s filtered, %s unresolved, %s errors.",
                        self._completed, self._total, self.summary['exported'], self.summary['skipped'],
                        self.summary['filtered'], self.summary['missing'], self.summary['errors'])
            self._last_log = now

    def _instrument_name(self, sample, source):
        instrument = sample['instrument']
        if self.find_real_instrument_folder and instrument == "Native Browser Preview Library":
            parts = source.parts
            for i in range(len(parts) - 3, -1, -1):
                if parts[i].lower() == 'previews' and parts[i + 1].lower() == 'samples':
                    return self.upids.get(parts[i + 2].casefold(), instrument).strip() or instrument
        return instrument

    def _export_preview(self, sample, targets):
        if not isinstance(sample, dict) or any(not isinstance(sample.get(key), str) or not sample[key] for key in ('ogg_path', 'wav_name', 'instrument')):
            raise ValueError("Preview record needs ogg_path, wav_name and instrument strings; rebuild in Step 1")
        source = Path(sample['ogg_path'])
        if ((self.skip_maschine_folders and source.name.lower().endswith('.mxgrp.ogg'))
                or (self.skip_battery_kits and source.name.lower().endswith('.nbkt.ogg'))
                or (self.skip_native_browser_preview_library and sample['instrument'] == 'Native Browser Preview Library')):
            self._record_result('filtered')
            return
        self._current_name = f"{sample['instrument']} / {sample['wav_name']}"
        if not source.is_file():
            logger.error("Unresolved preview path: %s", source)
            self._record_result('missing')
            return
        filename = sample['wav_name']
        if '/' in filename or '\\' in filename or not filename.lower().endswith('.wav'):
            raise ValueError(f"Invalid preview output filename: {filename!r}")
        target = Path(self.output_folder) / safe_name(self._instrument_name(sample, source)) / safe_name(filename)
        if not resolved_path(target).is_relative_to(resolved_path(self.output_folder)):
            raise ValueError(f"Preview output resolves outside the selected folder: {target}")
        key = str(resolved_path(target)).casefold()
        source_key = str(resolved_path(source)).casefold()
        if key in targets:
            if targets[key] != source_key:
                raise ValueError(f"Different previews target the same output: {target}; separate or rename them in the index")
            self._record_result('filtered')
            return
        targets[key] = source_key
        self._report_progress(force=not self._pending and self._completed == 0)
        self._copy(source, target)

    def run(self, worker_instance=None):
        self._start_export(worker_instance)
        self._last_log = time.monotonic()
        try:
            if self.find_real_instrument_folder:
                self.upids = load_product_names()

            with open(self.json_path, "r", encoding="utf-8") as f:
                samples = json.load(f)
            if not isinstance(samples, list) or not samples:
                raise ValueError("The preview index is empty or invalid; rebuild it in Step 1")
            self._total = len(samples)
            logger.info("[1/%s] Exporting previews with up to %s audio workers.", self._total, self._workers)
            self._report_progress(force=True)
            targets = {}
            with ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="preview-export") as executor:
                self._executor = executor
                try:
                    for sample in samples:
                        if worker_instance and worker_instance.cancel_requested():
                            break
                        try:
                            self._export_preview(sample, targets)
                        except Exception as exc:
                            logger.error("Could not export preview %r: %s", sample, exc)
                            self._record_result('errors')
                finally:
                    self._drain()
        except Exception as e:
            self.summary['errors'] += 1
            logger.error(f"Error processing previews: {e}")
        finally:
            self._executor = None
        if worker_instance and worker_instance.cancel_requested():
            return self._cancelled()
        self._report_progress(force=True)
        incomplete = self.summary['missing'] or self.summary['errors']
        empty = not (self.summary['exported'] or self.summary['skipped'])
        log = logger.error if incomplete else logger.warning if empty else logger.info
        log("Export %s: %s previews exported, %s existing files skipped, %s unresolved paths, %s errors, %s filtered.",
            'incomplete' if incomplete else 'empty' if empty else 'complete', self.summary['exported'],
            self.summary['skipped'], self.summary['missing'], self.summary['errors'], self.summary['filtered'])
        return 1 if incomplete or empty else 0


def main(json_path: str, output_folder: str, trim_silence: bool, normalize: bool, sample_rate: int, bit_depth: int, skip_existing: bool, find_real_instrument_folder: bool, skip_native_browser_preview_library: bool, skip_maschine_folders: bool, skip_battery_kits: bool):
    processor = PreviewsProcessor(
        json_path=json_path,
        output_folder=output_folder,
        trim_silence=trim_silence,
        normalize=normalize,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        skip_existing=skip_existing,
        skip_maschine_folders=skip_maschine_folders,
        skip_battery_kits=skip_battery_kits,
        skip_native_browser_preview_library=skip_native_browser_preview_library,
        find_real_instrument_folder=find_real_instrument_folder,
    )
    sys.exit(processor.run())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="preview processor")
    parser.add_argument("json_path", help="Path to input JSON file")
    parser.add_argument("output_folder", help="Path to output base folder")
    parser.add_argument("--trim_silence", action="store_true", help="Trim silence from wav files")
    parser.add_argument("--normalize", action="store_true", help="Normalize wav files")
    parser.add_argument("--sample_rate", type=int, help="Convert all samples to this sample rate (e.g. 48000)")
    parser.add_argument("--bit_depth", type=int, help="Convert all samples to this bit depth (e.g. 16)")
    parser.add_argument("--skip_existing", action="store_true", help="Skip processing if output file already exists")
    parser.add_argument("--skip_maschine_folders", action="store_true", help="Skip .mxgrp.ogg previews (Maschine groups)")
    parser.add_argument("--skip_battery_kits", action="store_true", help="Skip files ending with .nbkt.ogg (Battery kits)")
    parser.add_argument("--skip_native_browser_preview_library", action="store_true", help="Skip 'Native Browser Preview Library' folder")
    parser.add_argument("--find_real_instrument_folder", action="store_true", help="Find real instrument folder for the Preview Library")

    args = parser.parse_args()

    # Parameter Validation
    if not Path(args.json_path).is_file():
        logger.error(f"Error: JSON path '{args.json_path}' does not exist or is not a file.")
        sys.exit(1)

    output_dir = Path(args.output_folder)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Error: Could not create output folder '{args.output_folder}': {e}")
        sys.exit(1)

    if args.sample_rate is not None and args.sample_rate <= 0:
        logger.error(f"Error: Sample rate must be a positive integer, got {args.sample_rate}.")
        sys.exit(1)

    if args.bit_depth is not None and args.bit_depth <= 0:
        logger.error(f"Error: Bit depth must be a positive integer, got {args.bit_depth}.")
        sys.exit(1)

    try:
        main(
            json_path=args.json_path,
            output_folder=args.output_folder,
            trim_silence=args.trim_silence,
            normalize=args.normalize,
            sample_rate=args.sample_rate,
            bit_depth=args.bit_depth,
            skip_existing=args.skip_existing,
            skip_maschine_folders=args.skip_maschine_folders,
            skip_battery_kits=args.skip_battery_kits,
            skip_native_browser_preview_library=args.skip_native_browser_preview_library,
            find_real_instrument_folder=args.find_real_instrument_folder,
        )
    except SystemExit as e:
        sys.exit(e.code)
