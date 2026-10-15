import importlib.util
from pathlib import Path
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bundle_policy', ROOT / 'packaging/bundle_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class ReleaseContentTests(unittest.TestCase):
    def test_current_resources_match_reviewed_inventory_and_silence(self):
        self.assertEqual(len(policy.checked_resources(ROOT / 'resources')), len(policy.RESOURCES))

    def test_runtime_aliases_and_proprietary_inputs_are_rejected(self):
        for name in ('VCRUNTIME140.dll', 'PySide6/Qt6/bin/MSVCP140_2.dll',
                     'numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll',
                     'Kit.mxgrp', 'Kit.nbkt', 'saved.vstpreset', 'preview.ogg',
                     'tmp/cache/project.bin', 'resources/upids.json', 'Other.wav'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.check_payload_name(name)

    def test_nested_plugin_bundles_and_unsafe_paths_are_rejected(self):
        for name in ('Maschine.vst3/Contents/MacOS/Maschine', '../secret',
                     '/outside/file', 'C:/outside/file', 'resources/../secret'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.check_payload_name(name)

    def test_unreviewed_resource_fails_even_when_extension_looks_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'readme.txt').write_text('extra', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'inventory changed'):
                policy.checked_resources(folder)

    def test_nonzero_audio_is_not_accepted_as_silence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in policy.RESOURCES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'')
            with wave.open(str(root / 'audio/.wav'), 'wb') as output:
                output.setparams((2, 3, 48000, 2000, 'NONE', 'not compressed'))
                output.writeframes(b'\x01' + bytes(11999))
            with self.assertRaisesRegex(ValueError, 'nonzero audio'):
                policy.checked_resources(root)
