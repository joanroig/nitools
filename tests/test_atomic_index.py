"""Failure injection: old indexes must survive partial writes and replace errors."""
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from utils.file_utils import atomic_write
from processors.index_utils import build_sample_index
from processors.previews.build_previews_json import PreviewsJsonBuilder


class AtomicIndexTests(unittest.TestCase):
    def test_partial_write_keeps_existing_index_and_cleans_temporary(self):
        for preview in (False, True):
            with self.subTest(preview=preview), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / ('all_previews.json' if preview else 'index.json')
                target.write_bytes(b'previous index')
                report = target.with_suffix('.report.json')
                report.write_bytes(b'previous report')
                real_temp = tempfile.NamedTemporaryFile
                @contextmanager
                def failing_temp(*args, **kwargs):
                    with real_temp(*args, **kwargs) as handle:
                        class FailedWrite:
                            name = handle.name
                            def write(self, data):
                                handle.write(data[:5])
                                raise OSError('disk full')
                        yield FailedWrite()
                with patch('utils.file_utils.tempfile.NamedTemporaryFile', failing_temp):
                    if preview:
                        with patch('processors.previews.build_previews_json.get_ni_content_paths', return_value=[]):
                            self.assertEqual(PreviewsJsonBuilder(directory).run(), 1)
                    else:
                        with self.assertRaisesRegex(OSError, 'disk full'):
                            build_sample_index(['source'], target, None, lambda *a, **k: {'name': 'é'},
                                               generate_txt=False, worker=None, logger=logging.getLogger(), label='kits')
                self.assertEqual(target.read_bytes(), b'previous index')
                self.assertEqual(report.read_bytes(), b'previous report')
                self.assertFalse(list(root.glob('.nitools-*')))

    def test_replace_failure_preserves_original_and_success_keeps_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'index.json'
            target.write_bytes(b'previous')
            with patch.object(Path, 'replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    atomic_write(target, b'new')
            self.assertEqual(target.read_bytes(), b'previous')
            self.assertFalse(list(target.parent.glob('.nitools-*')))
            atomic_write(target, json.dumps({'name': 'é🥁'}, ensure_ascii=False).encode('utf-8'))
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'name': 'é🥁'})


if __name__ == '__main__':
    unittest.main()
