import json
from pathlib import Path
import sys
import tempfile
import unittest
import shutil
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formats.sample_paths import resolve_sample_path
from models.groups_exporter_config import GroupsExporterConfig
from models.kits_exporter_config import KitsExporterConfig
from processors.groups.process_groups_json import GroupsProcessor
from processors.kits.process_kits_json import KitsProcessor


class SampleExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / "Library"
        self.source = self.library / "Sounds" / "Battery Kits" / "Kit.nbkt"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"source fixture")
        self.output = self.root / "output"

    def sample(self, relative, payload=b"first sample"):
        path = self.library / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def process(self, samples, *, kind="kit", **options):
        record = {
            kind: "Test", "expansion": "Expansion", "parser": "structured-v1",
            "path": str(self.source if kind == "kit" else self.library),
            "sample_root": str(self.source.parent if kind == "kit" else self.library),
            "samples": samples,
        }
        record.update(options.pop("record_fields", {}))
        index = self.root / "index.json"
        index.write_text(json.dumps([record]), encoding="utf-8")
        cls = KitsProcessor if kind == "kit" else GroupsProcessor
        options.setdefault("enable_matrix", False)
        processor = cls(str(index), str(self.output), **options)
        return processor, processor.run()

    def test_paths_keep_parent_tokens_unicode_and_duplicate_basenames(self):
        self.sample("Samples/A/Kick\u00a0One.wav", b"correct")
        self.sample("Samples/B/Kick\u00a0One.wav", b"wrong")
        processor, result = self.process([
            {"pad": 1, "type": "sample", "path": "../../Samples/A/Kick\u00a0One.wav"},
            {"pad": 3, "type": "sample", "path": "..\\..\\Samples\\B\\Kick\u00a0One.wav"},
            {"pad": 4, "type": "sample", "path": "../../Samples/A/Kick\u00a0One.wav"},
            {"pad": 17, "type": "sample", "path": "../../Samples/A/Kick\u00a0One.wav"},
        ])
        self.assertEqual(result, 0)
        folder = self.output / "Expansion" / "Test"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["01_Kick\u00a0One.wav", "03_Kick\u00a0One.wav", "04_Kick\u00a0One.wav", "17_Kick\u00a0One.wav"])
        self.assertEqual((folder / "01_Kick\u00a0One.wav").read_bytes(), b"correct")
        self.assertEqual((folder / "03_Kick\u00a0One.wav").read_bytes(), b"wrong")
        self.assertEqual(processor.summary["exported"], 4)

    def test_all_zones_and_duplicate_references_are_preserved(self):
        self.sample("Samples/A.wav")
        processor, result = self.process([
            {"pad": 3, "type": "multisample", "paths": ["../../Samples/A.wav", "../../Samples/A.wav"]}
        ])
        self.assertEqual(result, 0)
        self.assertEqual(processor.summary["exported"], 2)
        self.assertEqual(sorted(p.name for p in (self.output / "Expansion" / "Test").iterdir()), ["03_01_A.wav", "03_02_A.wav"])

    def test_missing_path_never_uses_a_similar_or_same_basename_elsewhere(self):
        self.sample("Samples/Other/Kick.wav")
        self.sample("Samples/Wanted/Kick Similar.wav")
        processor, result = self.process([
            {"pad": 1, "type": "sample", "path": "../../Samples/Wanted/Kick.wav"}
        ])
        self.assertEqual(result, 1)
        self.assertEqual(processor.summary["missing"], 1)
        self.assertEqual(list(self.output.rglob("*.wav")), [])

    def test_hidden_battery_cells_warn_without_inventing_export_pads(self):
        from formats.battery import parse_battery
        from test_battery_format import fixture

        self.sample("Samples/Visible.wav")
        self.sample("Samples/Hidden.wav")
        decoded = parse_battery(fixture(
            paths=["../../Samples/Visible.wav", "../../Samples/Hidden.wav"],
            assignments=[(0, 0), (75, 1)], columns=12,
        ))
        with self.assertLogs("KitsProcessor", level="WARNING") as messages:
            processor, result = self.process(decoded["samples"], record_fields={
                "hidden_cells": decoded["hidden_cells"],
            })
        self.assertEqual(result, 0)
        self.assertEqual(processor.summary["exported"], 1)
        self.assertEqual([p.name for p in self.output.rglob("*.wav")], ["01_Visible.wav"])
        self.assertIn("outside the saved grid", "\n".join(messages.output))
        saved = json.loads((self.root / "index.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(saved["hidden_cells"][0]["cell_id"], 75)
        self.assertNotIn("pad", saved["hidden_cells"][0])

    def test_absolute_path_is_used_without_rebasing(self):
        source = self.sample("Samples/Elsewhere.wav")
        self.assertEqual(resolve_sample_path(str(source), self.root / "wrong"), source)
        self.assertIsNone(resolve_sample_path(str(self.root / "absent" / source.name), self.library))

    def test_matrix_defaults_apply_to_real_pad_numbers_and_leave_high_cells(self):
        self.sample("Samples/A.wav")
        _, result = self.process([
            {"pad": pad, "type": "sample", "path": "../../Samples/A.wav"}
            for pad in (1, 3, 17)
        ], enable_matrix=True)
        self.assertEqual(result, 0)
        self.assertEqual(sorted(p.name for p in self.output.rglob("*.wav")), ["13_A.wav", "15_A.wav", "17_A.wav"])

    def test_dict_matrix_and_pad_filter_are_supported(self):
        self.sample("Samples/A.wav")
        _, result = self.process([
            {"pad": 3, "name": "Snare", "path": "../../Samples/A.wav"}
        ], enable_matrix=True, matrix={3: 2}, filter_pads=True, pad_filter={3: ["SNARE"]})
        self.assertEqual(result, 0)
        self.assertEqual([p.name for p in self.output.rglob("*.wav")], ["02_A.wav"])

    def test_conversion_failure_is_not_silently_replaced_by_original_audio(self):
        self.sample("Samples/A.wav")
        with patch("processors.audio_export.trim_and_normalize_wav", side_effect=ValueError("invalid audio")):
            processor, result = self.process([
                {"pad": 1, "path": "../../Samples/A.wav"}
            ], normalize=True)
        self.assertEqual(result, 1)
        self.assertEqual(processor.summary["errors"], 1)
        self.assertEqual(processor.summary["exported"], 0)

    def test_preview_is_converted_to_wav(self):
        import numpy as np
        import soundfile as sf

        preview = self.source.parent / ".previews" / "Kit.nbkt.ogg"
        preview.parent.mkdir()
        sf.write(str(preview), np.sin(np.arange(400) * 0.1) * 0.2, 44100)
        processor, result = self.process([], include_preview=True, record_fields={"preview": str(preview)})
        self.assertEqual(result, 0)
        exported = self.output / "Expansion" / "Test" / "00_PREVIEW - Test.wav"
        self.assertEqual(sf.info(str(exported)).format, "WAV")
        self.assertEqual(processor.summary["exported"], 1)

    def test_groups_keep_all_zones_and_holes(self):
        self.sample("Samples/A/Kick.wav", b"a")
        self.sample("Samples/B/Kick.wav", b"b")
        processor, result = self.process([
            {"pad": 3, "type": "multisample", "paths": ["Samples/A/Kick.wav", "Samples/B/Kick.wav"]},
            {"pad": 5, "type": "sample", "paths": "Samples/A/Kick.wav"},
            {"pad": 17, "type": "sample", "paths": "Samples/B/Kick.wav"},
        ], kind="group")
        self.assertEqual(result, 0)
        folder = self.output / "Expansion" / "Test"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["03_01_Kick.wav", "03_02_Kick.wav", "05_Kick.wav", "17_Kick.wav"])
        self.assertEqual((folder / "03_02_Kick.wav").read_bytes(), b"b")
        self.assertEqual(processor.summary["exported"], 4)

    def test_fill_blanks_does_not_replace_instruments_or_unresolved_samples(self):
        fill = self.sample("Samples/Silence.wav")
        processor, result = self.process([
            {"pad": 1, "type": "instrument", "paths": []},
            {"pad": 2, "type": "sample", "paths": "Samples/Missing.wav"},
            {"pad": 3, "type": "empty", "paths": []},
        ], kind="group", fill_blanks=str(fill))
        self.assertEqual(result, 1)
        names = sorted(p.name for p in self.output.rglob("*.wav"))
        self.assertNotIn("01_Silence.wav", names)
        self.assertNotIn("02_Silence.wav", names)
        self.assertIn("03_Silence.wav", names)
        self.assertEqual(processor.summary["missing"], 1)
        self.assertEqual(processor.summary["omitted"], 1)

    def test_unknown_non_sample_slot_is_never_filled(self):
        fill = self.sample("Samples/Silence.wav")
        processor, result = self.process([
            {"pad": 1, "type": "no_sample", "paths": [], "status": "no_sample_reference"}
        ], kind="group", fill_blanks=str(fill))
        self.assertEqual(result, 0)
        self.assertEqual(processor.summary["omitted"], 1)
        self.assertFalse((self.output / "Expansion" / "Test" / "01_Silence.wav").exists())

    def test_legacy_index_is_rejected_before_export(self):
        source = self.sample("Samples/A.wav")
        processor, result = self.process([
            {"pad": 1, "path": str(source)}
        ], record_fields={"parser": None})
        self.assertEqual(result, 1)
        self.assertEqual(processor.summary["errors"], 1)
        self.assertFalse(self.output.exists())

    def test_maschine_library_namespace_resolves_without_changing_unc(self):
        source = self.sample("Samples/Drums/Kick.wav")
        processor, result = self.process([
            {"pad": 1, "paths": ["//Samples/Drums/Kick.wav"]}
        ], kind="group", record_fields={"source": "Maschine"})
        self.assertEqual(result, 0)
        self.assertEqual(processor.summary["exported"], 1)
        self.assertEqual(resolve_sample_path("//Samples/Drums/Kick.wav", self.library, maschine_library=True), source)
        self.assertEqual(resolve_sample_path("/Samples/Drums/Kick.wav", self.library, maschine_library=True), source)
        with patch("formats.sample_paths.Path.is_file", return_value=True):
            unc = resolve_sample_path("//OtherServer/Share/Kick.wav", self.library, maschine_library=True)
        if sys.platform == "win32":
            self.assertEqual(unc.as_posix(), "//OtherServer/Share/Kick.wav")
        else:
            self.assertIsNone(unc)

    def test_same_kit_name_in_different_expansions_stays_separate(self):
        source = self.sample("Samples/A.wav", b"a")
        other = self.sample("Samples/B.wav", b"b")
        records = [
            {"kit": "Same", "expansion": expansion, "parser": "structured-v1", "samples": [{"pad": 1, "path": str(path)}]}
            for expansion, path in (("First", source), ("Second", other))
        ]
        index = self.root / "index.json"
        index.write_text(json.dumps(records), encoding="utf-8")
        processor = KitsProcessor(str(index), str(self.output), enable_matrix=False)
        self.assertEqual(processor.run(), 0)
        self.assertEqual((self.output / "First" / "Same" / "01_A.wav").read_bytes(), b"a")
        self.assertEqual((self.output / "Second" / "Same" / "01_B.wav").read_bytes(), b"b")

    def test_colliding_names_are_reported_without_overwriting_first(self):
        source = self.sample("Samples/A.wav", b"a")
        other = self.sample("Samples/B.wav", b"b")
        records = [
            {"kit": name, "expansion": "Expansion", "parser": "structured-v1", "samples": [{"pad": 1, "path": str(path)}]}
            for name, path in (("Kit?", source), ("Kit*", other))
        ]
        index = self.root / "index.json"
        index.write_text(json.dumps(records), encoding="utf-8")
        processor = KitsProcessor(str(index), str(self.output), enable_matrix=False)
        self.assertEqual(processor.run(), 1)
        self.assertEqual(processor.summary["errors"], 1)
        self.assertEqual((self.output / "Expansion" / "Kit_" / "01_A.wav").read_bytes(), b"a")

    def test_output_names_cannot_traverse_out_of_destination(self):
        source = self.sample("Samples/A.wav")
        _, result = self.process([
            {"pad": 1, "path": str(source)}
        ], record_fields={"kit": "../../Outside", "expansion": "../Library"})
        self.assertEqual(result, 0)
        exported = list(self.output.rglob("*.wav"))
        self.assertEqual(len(exported), 1)
        self.assertTrue(exported[0].resolve().is_relative_to(self.output.resolve()))

    def test_failed_conversion_preserves_existing_output_and_cleans_partial_file(self):
        source = self.sample("Samples/A.wav")
        target = self.output / "Expansion" / "Test" / "01_A.wav"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"previous export")

        def failed_conversion(source, temporary, *args):
            Path(temporary).write_bytes(b"partial invalid output")
            raise ValueError("conversion failed")

        with patch("processors.audio_export.trim_and_normalize_wav", side_effect=failed_conversion):
            _, result = self.process([{"pad": 1, "path": str(source)}], normalize=True)
        self.assertEqual(result, 1)
        self.assertEqual(target.read_bytes(), b"previous export")
        self.assertEqual([path.name for path in target.parent.iterdir()], ["01_A.wav"])

    def test_copy_to_source_is_rejected_even_when_skip_existing(self):
        source = self.sample("Expansion/Test/00_PREVIEW - Test.wav", b"original")
        self.output = self.library
        processor, result = self.process([], normalize=True, skip_existing=True,
                                         include_preview=True, record_fields={"preview": str(source)})
        self.assertEqual(result, 1)
        self.assertEqual(source.read_bytes(), b"original")
        self.assertEqual(processor.summary["skipped"], 0)

    def test_cancellation_after_one_copy_stops_before_other_zones_and_preview(self):
        source = self.sample("Samples/A.wav")
        record = {"kit": "Test", "parser": "structured-v1", "preview": str(source), "samples": [
            {"pad": 1, "paths": [str(source), str(source)]}
        ]}
        index = self.root / "index.json"
        index.write_text(json.dumps([record]), encoding="utf-8")

        class Worker:
            cancelled = False

            def cancel_requested(self):
                return self.cancelled

        worker = Worker()
        original_copy = shutil.copy2

        def copy_then_cancel(source, target):
            original_copy(source, target)
            worker.cancelled = True

        processor = KitsProcessor(str(index), str(self.output), enable_matrix=False, include_preview=True)
        with patch("processors.audio_export.shutil.copy2", side_effect=copy_then_cancel):
            self.assertEqual(processor.run(worker_instance=worker), 1)
        self.assertTrue(processor.summary["cancelled"])
        self.assertEqual(processor.summary["exported"], 0)
        self.assertEqual(list(self.output.rglob("*.wav")), [])

    def test_missing_preview_marks_export_incomplete(self):
        self.sample("Samples/A.wav")
        processor, result = self.process([
            {"pad": 1, "path": "../../Samples/A.wav"}
        ], include_preview=True, record_fields={"preview": "missing.ogg"})
        self.assertEqual(result, 1)
        self.assertEqual(processor.summary["missing"], 1)

    def test_audio_conversions_overlap_with_bounded_workers_and_exact_counts(self):
        source = self.sample("Samples/A.wav", b"converted sample")
        lock = threading.Lock()
        active = peak = 0

        def conversion(input_path, temporary, *args):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            Path(temporary).write_bytes(Path(input_path).read_bytes())
            with lock:
                active -= 1

        with patch("processors.audio_export.trim_and_normalize_wav", side_effect=conversion):
            processor, result = self.process([
                {"pad": pad, "paths": [str(source)]} for pad in range(1, 21)
            ], normalize=True)
        self.assertEqual(result, 0)
        self.assertEqual(processor.summary["exported"], 20)
        self.assertLessEqual(peak, 4)
        if processor._workers > 1:
            self.assertGreater(peak, 1)
        files = list(self.output.rglob("*.wav"))
        self.assertEqual(len(files), 20)
        self.assertTrue(all(path.read_bytes() == b"converted sample" for path in files))

    def test_new_config_preserves_empty_slots_and_has_no_fuzzy_setting(self):
        self.assertFalse(GroupsExporterConfig().fill_blanks)
        self.assertFalse(GroupsExporterConfig().filter_pads)
        config = KitsExporterConfig.model_validate({"replace_missing": True})
        self.assertNotIn("replace_missing", config.model_dump())

    def test_cancel_parallel_conversion_discards_pending_files_and_joins_workers(self):
        source = self.sample("Samples/A.wav")
        index = self.root / "index.json"
        index.write_text(json.dumps([{"kit": "Test", "parser": "structured-v1", "samples": [
            {"pad": pad, "paths": [str(source)]} for pad in range(1, 21)
        ]}]), encoding="utf-8")
        entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()

        class Worker:
            def cancel_requested(self):
                return cancelled.is_set()

        def conversion(input_path, temporary, *args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release conversion")
            Path(temporary).write_bytes(b"converted")

        processor = KitsProcessor(str(index), str(self.output), enable_matrix=False, normalize=True)
        result = []
        with patch("processors.audio_export.trim_and_normalize_wav", side_effect=conversion):
            thread = threading.Thread(target=lambda: result.append(processor.run(Worker())))
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                cancelled.set()
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [1])
        self.assertTrue(processor.summary["cancelled"])
        self.assertEqual(processor.summary["exported"], 0)
        self.assertFalse(any(path.is_file() for path in self.output.rglob("*")))


if __name__ == "__main__":
    unittest.main()
