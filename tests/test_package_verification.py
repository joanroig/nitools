"""Exercise finished-package checks with synthetic archives, no vendor files."""
from pathlib import Path
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
from verify_package import validate_inventory, verify_zip


class PackageVerificationTests(unittest.TestCase):
    def test_zip_rejects_changed_missing_extra_and_duplicate_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'NITools'
            folder.mkdir()
            (folder / 'app.exe').write_bytes(b'synthetic executable')
            archive = root / 'package.zip'
            for variant in ('good', 'changed', 'missing', 'extra', 'duplicate'):
                with self.subTest(variant=variant):
                    with zipfile.ZipFile(archive, 'w') as output:
                        if variant != 'missing':
                            output.writestr('NITools/app.exe', b'changed' if variant == 'changed' else b'synthetic executable')
                        if variant == 'extra':
                            output.writestr('NITools/kit.nbkt', b'not real content')
                        if variant == 'duplicate':
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore', UserWarning)
                                output.writestr('NITools/app.exe', b'synthetic executable')
                    if variant == 'good':
                        self.assertEqual(verify_zip(folder, archive), 1)
                    else:
                        with self.assertRaises(ValueError):
                            verify_zip(folder, archive)

    def test_inventory_requires_payload_and_nonempty_contained_notices(self):
        inventory = {'payload': [{'path': 'library.dll'}],
                     'dependencies': [{'name': 'Library', 'notices': ['licenses/Library.txt']}]}
        validate_inventory(inventory, {'library.dll'}, lambda name: b'License')
        with self.assertRaisesRegex(ValueError, 'missing from package'):
            validate_inventory(inventory, set(), lambda name: b'License')
        with self.assertRaisesRegex(ValueError, 'empty dependency notice'):
            validate_inventory(inventory, {'library.dll'}, lambda name: b'')
        inventory['dependencies'][0]['notices'] = ['../outside.txt']
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            validate_inventory(inventory, {'library.dll'}, lambda name: b'License')


if __name__ == '__main__':
    unittest.main()
