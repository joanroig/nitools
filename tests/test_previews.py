import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from processors.previews.build_previews_json import PreviewsJsonBuilder, collect_samples_from_path
from processors.previews.process_previews_json import PreviewsProcessor


class Worker:
    cancelled = False

    def __init__(self):
        self.progress = []

    def cancel_requested(self):
        return self.cancelled

    def report_progress(self, completed, total, message):
        self.progress.append((completed, total, message))


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'Library'
        self.input.mkdir()
        self.output = self.root / 'output'
        self.index = self.root / 'index.json'

    def record(self, name='Test', folder='Instrument'):
        source = self.input / (name + '.wav')
        source.write_bytes(b'raw audio fixture')
        return dict(instrument=folder, ogg_path=str(source), wav_name=name + '.wav')

    def process(self, records, worker=None, **options):
        self.index.write_text(json.dumps(records), encoding='utf-8')
        processor = PreviewsProcessor(self.index, self.output, **options)
        code = processor.run(worker)
        return code, processor.summary

    def test_success_skip_and_live_final_counts(self):
        record = self.record('Café')
        worker = Worker()
        code, summary = self.process([record], worker)
        self.assertEqual((code, summary['exported']), (0, 1))
        self.assertEqual(worker.progress[0][:2], (0, 1))
        self.assertEqual(worker.progress[-1][:2], (1, 1))
        self.assertEqual((self.output / 'Instrument/Café.wav').read_bytes(), b'raw audio fixture')
        self.assertEqual(self.process([record], skip_existing=True)[1]['skipped'], 1)

    def test_missing_and_conversion_error_are_incomplete_and_keep_old_output(self):
        record = self.record()
        self.process([record])
        with patch('processors.audio_export.trim_and_normalize_wav', side_effect=ValueError('bad audio')):
            code, summary = self.process([record], normalize=True)
        self.assertEqual((code, summary['errors']), (1, 1))
        self.assertEqual((self.output / 'Instrument/Test.wav').read_bytes(), b'raw audio fixture')
        self.assertFalse(list(self.output.rglob('.nitools-*')))
        record['ogg_path'] += '.missing'
        self.assertEqual(self.process([record])[1]['missing'], 1)

    def test_collision_and_duplicate_are_distinguished(self):
        first = self.record('First')
        second = self.record('Second')
        second['wav_name'] = first['wav_name']
        code, summary = self.process([first, second, first])
        self.assertEqual((code, summary['exported'], summary['errors'], summary['filtered']), (1, 1, 1, 1))

    def test_cancel_during_conversion_does_not_commit(self):
        worker = Worker()
        def convert(source, target, *args):
            Path(target).write_bytes(b'partial')
            worker.cancelled = True
        with patch('processors.audio_export.trim_and_normalize_wav', side_effect=convert):
            code, summary = self.process([self.record()], worker, normalize=True)
        self.assertEqual(code, 1)
        self.assertTrue(summary['cancelled'])
        self.assertFalse(list(self.output.rglob('*.wav')))

    def test_empty_invalid_and_filtered_indexes_do_not_succeed(self):
        for records in ([], {}, [{'instrument': 'Missing fields'}]):
            with self.subTest(records=records):
                self.assertEqual(self.process(records)[0], 1)
        record = self.record()
        record['ogg_path'] += '.MXGRP.OGG'
        code, summary = self.process([record], skip_maschine_folders=True)
        self.assertEqual((code, summary['filtered'], summary['missing']), (1, 1, 0))

    def test_native_browser_unmatched_path_does_not_reuse_previous_id(self):
        record = self.record(folder='Native Browser Preview Library')
        processor = PreviewsProcessor(self.index, self.output, find_real_instrument_folder=True)
        processor.upids = {'known': 'Mapped Instrument'}
        self.assertEqual(processor._instrument_name(record, Path('Previews/Samples/known/a.ogg')), 'Mapped Instrument')
        self.assertEqual(processor._instrument_name(record, Path('Unrelated/a.ogg')), 'Native Browser Preview Library')
        self.assertEqual(processor._instrument_name(record, Path('Previews/Samples')), 'Native Browser Preview Library')

    def test_paths_cannot_escape_and_source_cannot_be_overwritten(self):
        record = self.record()
        record['wav_name'] = '../escape.wav'
        self.assertEqual(self.process([record])[1]['errors'], 1)
        self.assertFalse((self.root / 'escape.wav').exists())
        record['wav_name'] = 'Test.wav'
        record['instrument'] = self.input.name
        self.output = self.root
        self.assertEqual(self.process([record], skip_existing=True)[1]['errors'], 1)
        self.assertEqual(Path(record['ogg_path']).read_bytes(), b'raw audio fixture')

    def test_scan_deduplicates_overlapping_libraries_and_handles_uppercase(self):
        previews = self.input / 'Sounds/.previews'
        previews.mkdir(parents=True)
        (previews / 'Café.NKSF.OGG').write_bytes(b'preview')
        paths = [('Library', self.input), ('Alias', self.input), ('Nested', self.input / 'Sounds')]
        worker = Worker()
        with patch('processors.previews.build_previews_json.get_ni_content_paths', return_value=paths):
            self.assertEqual(PreviewsJsonBuilder(self.output / 'nested').run(worker), 0)
        records = json.loads((self.output / 'nested/all_previews.json').read_text(encoding='utf-8'))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['wav_name'], 'Café.wav')
        self.assertEqual(worker.progress[-1][:2], (2, 2))

    def test_cancel_inside_library_preserves_index(self):
        previews = self.input / '.previews'
        previews.mkdir()
        (previews / 'Test.ogg').write_bytes(b'preview')
        self.output.mkdir()
        index = self.output / 'all_previews.json'
        index.write_text('previous index', encoding='utf-8')
        worker = Worker()
        def cancel(*args):
            worker.cancelled = True
        worker.report_progress = cancel
        with patch('processors.previews.build_previews_json.get_ni_content_paths', return_value=[('Library', self.input)]):
            self.assertEqual(PreviewsJsonBuilder(self.output).run(worker), 1)
        self.assertEqual(index.read_text(), 'previous index')
        worker.cancelled = False
        self.assertEqual(collect_samples_from_path('Library', self.input, worker, lambda *args: cancel()), [])

    def test_empty_and_unreadable_scan_report_failure(self):
        for paths in ([], [('Missing', self.root / 'missing')]):
            with patch('processors.previews.build_previews_json.get_ni_content_paths', return_value=paths):
                self.assertEqual(PreviewsJsonBuilder(self.output).run(), 1)
        report = json.loads((self.output / 'all_previews.report.json').read_text())
        self.assertEqual(len(report['errors']), 1)
