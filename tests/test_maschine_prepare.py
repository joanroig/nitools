"""Batch checkpoint, cancellation and child recovery without licensed content."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from models.render_options import RenderOptions
from processors.maschine_prepare import PreparationSession, prepare_index
from processors.maschine_render import NativeSession


def fake_prepare_job(connection, plugin, options):
    try:
        while True:
            source = Path(connection.recv())
            if source.stem == 'crash':
                os._exit(7)
            if source.stem == 'slow':
                time.sleep(20)
            if source.stem == 'wrong':
                connection.send(('error', 'Loaded kit does not match'))
                return
            target = Path(options.cache_folder) / source.name
            target.write_text('prepared')
            connection.send(('done', str(target)))
    except EOFError:
        pass
    finally:
        connection.close()


@unittest.skipUnless(sys.platform in {'win32', 'darwin'}, 'Supported preparation host')
class PreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.plugin = self.root / 'test.vst3'
        if sys.platform == 'darwin':
            import plistlib
            binary = self.plugin / 'Contents/MacOS/Maschine'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'test')
            (self.plugin / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Maschine'}))
        else:
            self.plugin.write_bytes(b'test')
        self.options = RenderOptions(maschine_plugin=str(self.plugin), cache_folder=str(self.cache))
        self.session = PreparationSession(self.options)
        self.addCleanup(self.session.close)
        self.addCleanup(patch.stopall)
        patch('processors.maschine_prepare._prepare_job', fake_prepare_job).start()
        patch('processors.maschine_prepare.load_prepared', side_effect=self.cached).start()

    def cached(self, source, options):
        path = self.cache / Path(source).name
        if not path.is_file():
            raise ValueError('not prepared')
        return path.read_bytes()

    def test_reuses_host_and_resume_does_not_start_host(self):
        self.assertEqual(self.session.prepare(self.root / 'first.mxgrp'), 'prepared')
        pid = self.session.process.pid
        self.assertEqual(self.session.prepare(self.root / 'second.mxgrp'), 'prepared')
        self.assertEqual(self.session.process.pid, pid)
        self.session.close()
        self.assertEqual(self.session.prepare(self.root / 'first.mxgrp'), 'cached')
        self.assertIsNone(self.session.process)

    def test_wrong_kit_and_crash_restart_for_next_kit(self):
        for name in ('wrong', 'crash'):
            with self.assertRaises((RuntimeError, EOFError)):
                self.session.prepare(self.root / f'{name}.mxgrp')
            self.assertIsNone(self.session.process)
            self.assertFalse((self.cache / f'{name}.mxgrp').exists())
            self.assertEqual(self.session.prepare(self.root / f'after-{name}.mxgrp'), 'prepared')

    def test_cancellation_and_timeout_kill_owned_child(self):
        worker = Mock()
        worker.cancel_requested.side_effect = [False, True]
        self.assertEqual(self.session.prepare(self.root / 'slow.mxgrp', worker), 'cancelled')
        self.assertIsNone(self.session.process)
        self.assertEqual(self.session.prepare(self.root / 'warm.mxgrp'), 'prepared')
        self.options.prepare_timeout = 0.2  # Short warm-host deadline for the synthetic test.
        with self.assertRaises(TimeoutError):
            self.session.prepare(self.root / 'slow.mxgrp')
        self.assertIsNone(self.session.process)

    def test_export_can_defer_preparation_until_a_pad_actually_renders(self):
        with patch('processors.maschine_render.load_prepared', side_effect=ValueError('not prepared')):
            native = NativeSession(self.root / 'one.mxgrp', self.options)
            self.assertIsNone(native.state)
            self.assertIsNone(native.process)
            native.close()
            self.options.auto_prepare = False
            with self.assertRaisesRegex(ValueError, 'not prepared'):
                NativeSession(self.root / 'one.mxgrp', self.options)

    def test_batch_selects_native_kits_deduplicates_and_reports_failures(self):
        paths = [self.root / f'{name}.mxgrp' for name in ('native', 'vst', 'raw', 'bad')]
        for path in paths:
            path.write_bytes(path.stem.encode())
        index = self.root / 'index.json'
        index.write_text(json.dumps([{'source_file': str(p)} for p in [*paths, paths[0]]] + [{}]))
        def decode(data):
            if data == b'bad':
                raise ValueError('invalid archive')
            if data == b'raw':
                return {'samples': [{}]}
            return {'samples': [{'instrument': {'render_support': 'vst2' if data == b'vst' else 'requires_maschine'}}]}
        self.options.enabled = sys.platform == 'win32'
        with patch('processors.maschine_prepare.parse_maschine', side_effect=decode):
            self.assertEqual(prepare_index(index, self.options), 1)
        report = json.loads((self.cache / 'preparation-report.json').read_text())
        expected = (1, 2, 2) if sys.platform == 'win32' else (2, 1, 2)
        self.assertEqual((report['prepared'], report['unnecessary'], report['errors']), expected)
        self.assertEqual(len(report['results']), 3 if sys.platform == 'win32' else 4)
        self.assertEqual(paths[0].read_bytes(), b'native')

    def test_batch_cancel_keeps_report_and_cache(self):
        source = self.root / 'native.mxgrp'
        source.write_bytes(b'kit')
        index = self.root / 'index.json'
        index.write_text(json.dumps([{'source_file': str(source)}]))
        worker = Mock()
        worker.cancel_requested.return_value = True
        self.assertEqual(prepare_index(index, self.options, worker), -1)
        self.assertTrue(json.loads((self.cache / 'preparation-report.json').read_text())['cancelled'])
        self.assertFalse(list(self.cache.glob('*.mxgrp')))

    def test_keyboard_interrupt_checkpoints_cancelled_report(self):
        source = self.root / 'native.mxgrp'
        source.write_bytes(b'kit')
        index = self.root / 'index.json'
        index.write_text(json.dumps([{'source_file': str(source)}]))
        with patch('processors.maschine_prepare.parse_maschine', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                prepare_index(index, self.options)
        self.assertTrue(json.loads((self.cache / 'preparation-report.json').read_text())['cancelled'])
