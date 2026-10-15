"""Settings persistence checks use temporary files, never user configuration."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from models.config import Config
from utils import config_utils


class ConfigPersistenceTests(unittest.TestCase):
    def test_unicode_roundtrip_and_legacy_windows_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config.json'
            config = Config()
            config.kits_exporter.input_folder = 'D:/Bibliothèque/🥁'
            with patch.object(config_utils, 'CONFIG_FILE', str(target)):
                config_utils.save_config(config)
                self.assertEqual(config_utils.load_config(), config)
                self.assertIn('🥁', target.read_text(encoding='utf-8'))
                config.kits_exporter.input_folder = 'D:/Bibliothèque/Café'
                target.write_bytes(config.model_dump_json(indent=2).encode('cp1252'))
                with patch.object(config_utils.locale, 'getencoding', return_value='cp1252'):
                    self.assertEqual(config_utils.load_config(), config)
                config_utils.save_config(config)
                self.assertIn('Café', target.read_text(encoding='utf-8'))

    def test_failed_replace_preserves_saved_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config.json'
            with patch.object(config_utils, 'CONFIG_FILE', str(target)):
                original = config_utils.load_config()
                previous = target.read_bytes()
                changed = original.model_copy(deep=True)
                changed.max_log_lines = 500
                with patch.object(Path, 'replace', side_effect=PermissionError('locked')):
                    with self.assertRaises(PermissionError):
                        config_utils.save_config(changed)
                self.assertEqual(target.read_bytes(), previous)
                self.assertEqual(config_utils.load_config(), original)
                self.assertFalse(list(target.parent.glob('.nitools-*')))


if __name__ == '__main__':
    unittest.main()
