"""Archive framing and schema boundary tests with original synthetic records."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from maschine_fixture import Writer, portable, text
from formats.maschine import sample_references
from formats.maschine_schema import MaschineArchive
from formats.ni_container import FormatError


class ArchiveTests(unittest.TestCase):
    def test_audio_locations_follow_each_supported_module_and_take_layout(self):
        for version in range(8):
            for take_version in range(3):
                with self.subTest(module=version, take=take_version):
                    writer = Writer()
                    writer.versions = {"AudioModule": version, "Take": take_version}
                    writer.obj("AudioModule")
                    reader = MaschineArchive(bytes(writer.data))
                    module = reader.obj("AudioModule")
                    self.assertEqual(reader.pos, len(writer.data))
                    refs = sample_references(module, 0)
                    self.assertEqual(
                        [r["path"] for r in refs], ["Samples/Kick\u00a0é🥁.wav"]
                    )
                    self.assertEqual(refs[0]["library_root"], "Q:/Original Library/")
                    with self.assertRaises(FormatError):
                        MaschineArchive(bytes(writer.data[:-1])).obj("AudioModule")

    def test_opaque_chunk_does_not_register_fake_classes_or_paths(self):
        writer = Writer()
        # A complete length-bounded binary vector may contain arbitrary markers.
        blob = (
            text("NI::MASCHINE::DATA::Sampler") + text("Samples/Fake.wav") + bytes(50)
        )
        writer.data += portable(0) + portable(0) + portable(len(blob)) + blob
        reader = MaschineArchive(bytes(writer.data))
        node = reader.obj("PluginChunk")
        self.assertEqual(node["value"], blob)
        self.assertEqual(reader.class_names, ["PluginChunk"])
        self.assertEqual(reader.pos, len(writer.data))
        with self.assertRaises(FormatError):
            MaschineArchive(bytes(writer.data[:-1])).obj("PluginChunk")

    def test_tracked_reference_has_no_second_body_and_checks_type(self):
        writer = Writer()
        writer.obj("String")
        first_end = len(writer.data)
        writer.integer(0)
        reader = MaschineArchive(bytes(writer.data))
        first = reader.obj("String")
        self.assertEqual(reader.pos, first_end)
        self.assertIs(reader.obj("String"), first)
        self.assertEqual(reader.pos, len(writer.data))
        reader.data += portable(1) + portable(0) + portable(0)
        with self.assertRaisesRegex(FormatError, "references a String"):
            reader.obj("Module")

    def test_invalid_width_version_count_and_unknown_type_fail_closed(self):
        header = text("serialization::archive") + portable(17) + portable(0)
        for payload, kind in [
            (portable(1) + portable(99), "Group"),
            (portable(0) + portable(0) + portable(-1), "VectorSound"),
            (portable(0) + portable(0) + portable(-1), "ForwardArray"),
            (portable(0) + portable(0) + portable(100001), "TimedEvents"),
            (portable(0) + portable(0), "UnimplementedModule"),
        ]:
            with self.subTest(kind=kind), self.assertRaises(FormatError):
                MaschineArchive(header + payload).obj(kind)
        for value in (0, 1, -1, 255, -255, 256, -256, 2**32, -(2**32)):
            encoded = portable(value)
            reader = MaschineArchive(header + encoded)
            self.assertEqual(reader.integer(), value)
            self.assertEqual(reader.pos, len(header) + len(encoded))
            with self.assertRaises(FormatError):
                MaschineArchive(header + encoded[:-1]).integer()
        reader = MaschineArchive(header + portable(256))
        with self.assertRaises(FormatError):
            reader.integer(1)
        reader = MaschineArchive(header + bytes([9]))
        with self.assertRaises(FormatError):
            reader.integer()

    def test_unknown_exported_type_cannot_be_skipped(self):
        writer = Writer()
        writer.integer(0)
        writer.string("Foreign::Unknown")
        with self.assertRaisesRegex(FormatError, "Unsupported exported type"):
            MaschineArchive(bytes(writer.data)).dynamic()


if __name__ == "__main__":
    unittest.main()
