from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from processors.previews.product_names import load_product_names


class ProductNamesTests(unittest.TestCase):
    def test_reads_local_names_and_ignores_unrelated_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Example.xml").write_text(
                '<ProductHints><Product><UPID>TEST-ID</UPID><Name>Example &amp; Synth</Name>'
                '<SerialNumber>must-not-be-used</SerialNumber></Product>'
                '<Product><Name>Incomplete</Name></Product></ProductHints>', encoding="utf-8")
            self.assertEqual(load_product_names([folder]), {"test-id": "Example & Synth"})

    def test_missing_invalid_and_entity_xml_do_not_break_export(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Bad.xml").write_text("<broken", encoding="utf-8")
            Path(folder, "Entity.xml").write_text(
                '<!DOCTYPE x [<!ENTITY x "hidden">]><Product><UPID>test</UPID>'
                '<Name>&x;</Name></Product>', encoding="utf-8")
            self.assertEqual(load_product_names([folder, Path(folder, "missing")]), {})
