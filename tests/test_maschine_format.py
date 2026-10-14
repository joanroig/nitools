"""Regression checks using installed kits; proprietary kits are not copied."""

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formats.maschine import parse_maschine
from formats.maschine_project_frames import _channel_names
from maschine_fixture import synthetic_archive, Writer
from formats.ni_container import FormatError
from processors.groups.build_groups_json import GroupsJsonBuilder, process_mxgrp_file


CORPUS = Path(__file__).resolve().parents[1] / "in"


def portable(value):
    width = max(0, (value.bit_length() + 7) // 8)
    return bytes([width]) + value.to_bytes(width, "little")


def archive_text(value):
    encoded = value.encode("utf-8")
    return portable(len(encoded)) + encoded


def ids(first, count):
    return b"".join(portable(value) for value in range(first, first + count))



def kit(name):
    source = next(CORPUS.rglob(name), None)
    if source is None:
        raise unittest.SkipTest(f"Local licensed fixture unavailable: {name}")
    return source


class MaschineFormatTests(unittest.TestCase):
    def test_channel_frames_keep_empty_long_unicode_names_and_wide_ids(self):
        for legacy in (False, True):
            archive = bytearray(b'opaque' + bytes(100))
            names = ['', 'é🥁' * 80] + ['Channel'] * 15
            # Exercise canonical ID widths and crossings, plus both legacy
            # first-use metadata forms, without relying on installed presets.
            identifiers = [254, 65534, 16777214] + [17000000 + i * 100 for i in range(14)]
            for index, (name, ident) in enumerate(zip(names, identifiers)):
                metadata = (b'\0\0' if index % 2 else b'') if legacy else b'\0'
                archive += portable(ident) + metadata + archive_text(name)
                numeric = bytes(12 if legacy else 13) + portable(1) + bytes(4)
                if legacy:
                    archive += ids(ident + 1, 3) + numeric + ids(ident + 4, 4) + bytes(5) + ids(ident + 8, 3)
                else:
                    archive += ids(ident + 1, 4) + numeric + ids(ident + 5, 5)
                archive += bytes(100)
            decoded = _channel_names(bytes(archive), 0, legacy)
            self.assertEqual([row.text for row in decoded], names)
            self.assertEqual([row.object_id for row in decoded], identifiers)

    def test_legacy_parameter_layout_and_optional_volume_override(self):
        for legacy in (False, True):
            result = parse_maschine(synthetic_archive(legacy=legacy, override=True))
            self.assertEqual(result['group'], 'Fixture')
            self.assertEqual(len(result['samples'][2]['paths']), 2)
            self.assertEqual(result['format_details']['archive_version'], 10 if legacy else 17)

    def test_empty_zone_counts_without_becoming_a_missing_sample(self):
        for legacy in (False, True):
            sample = parse_maschine(synthetic_archive(legacy=legacy, empty_zone=True))['samples'][2]
            self.assertEqual(len(sample['sample_references']), 2)
            self.assertEqual(len(sample['paths']), 1)
            self.assertEqual(sample['empty_zones'], 1)

    def test_declared_zone_count_cannot_hide_extra_zones(self):
        writer = Writer()
        data = bytearray(writer.build())
        # Change the second sequential vector count without changing its body.
        offset = 108 + writer.zone_counts[1]
        data[offset + 1] = 1
        with self.assertRaises(FormatError):
            parse_maschine(bytes(data))

    def test_installed_archive_version_profiles(self):
        library = Path(r'D:\Libraries\Native Instruments')
        if not library.is_dir():
            self.skipTest('Optional installed library corpus is unavailable')
        cases = [
            ('Amplified Funk Library/Groups/Kits/3onIt Kit.mxgrp', 10, 27),
            ('Molten Veil Library/Kits/About The Low Kit.mxgrp', 12, 49),
            ('Hexagon Highway Library/Groups/Kits/Arena Kit.mxgrp', 13, 14),
            ('Crystal Daggers Library/Groups/Kits/Magenta Kit.mxgrp', 14, 15),
            ('Arcane Attic Library/Groups/Kits/Aeon Kit.mxgrp', 15, 16),
            ('District Xeo Library/Groups/Kits/Argon Kit.mxgrp', 16, 14),
            ('Amplified Funk Library/Groups/Kits/DaOne Kit.mxgrp', 17, 14),
            ('Burnt Hues Library/Groups/Kits/Alderson Kit.mxgrp', 18, 16),
            ('AMIRI Sounds Library/Groups/Kits/Apio Kit.mxgrp', 19, 18),
        ]
        for name, version, zones in cases:
            with self.subTest(name=name):
                path = library / name
                if not path.is_file():
                    continue
                result = parse_maschine(path.read_bytes())
                self.assertEqual(result['format_details']['archive_version'], version)
                self.assertEqual([s['pad'] for s in result['samples']], list(range(1, 17)))
                self.assertEqual(sum(len(s['paths']) for s in result['samples']), zones)

    def test_synthetic_unicode_empty_name_and_repeated_zones(self):
        result = parse_maschine(synthetic_archive())
        self.assertEqual(result["group"], "Fixture")
        self.assertEqual(result["samples"][1]["name"], "")
        self.assertEqual(result["samples"][1]["pad"], 2)
        self.assertEqual(result["samples"][0]["paths"], ["Samples/Kick\u00a0é\U0001f941.wav"])
        self.assertEqual(result["samples"][2]["paths"], ["Samples/Kick\u00a0é\U0001f941.wav"] * 2)

    def test_synthetic_bad_zone_count_fails(self):
        writer = Writer()
        data = bytearray(writer.build())
        data[108 + writer.zone_counts[1] + 1] = 3
        with self.assertRaises(FormatError):
            parse_maschine(bytes(data))

    def test_samples_and_non_sample_slots_keep_source_order(self):
        result = parse_maschine(kit("Manhattan Kit.mxgrp").read_bytes())
        self.assertEqual(result["parser"], "structured-v1")
        self.assertEqual([sample["pad"] for sample in result["samples"]], list(range(1, 17)))
        block, tom, ride = result["samples"][10:13]
        self.assertEqual(block["name"], "Block\u00a0Manhattan")
        self.assertEqual(block["paths"], ["Samples/Drums/Percussion/Block\u00a0Manhattan.wav"])
        self.assertEqual(tom["name"], "Tom Manhatten")
        self.assertEqual(tom["status"], "no_sample_reference")
        self.assertEqual(tom["type"], "no_sample")
        self.assertEqual(tom["paths"], [])
        self.assertEqual(ride["pad"], 13)
        self.assertEqual(ride["paths"], ["Samples/Drums/Cymbal/Ride\u00a0Manhattan.wav"])

    def test_multisample_records_stay_on_the_same_sound(self):
        result = parse_maschine(kit("Cosmic Kit.mxgrp").read_bytes())
        bass = result["samples"][14]
        self.assertEqual((bass["pad"], bass["name"], bass["type"]), (15, "Bass Cosmic", "multisample"))
        self.assertEqual(len(bass["paths"]), 8)
        self.assertEqual(bass["paths"][0], "Samples/Instruments/Bass/Bass Eight On/EightOn C1.wav")
        self.assertEqual(bass["paths"][-1], "Samples/Instruments/Bass/Bass Eight On/EightOn Gb4.wav")
        self.assertEqual(len({ref["object_id"] for ref in bass["sample_references"]}), 8)
        self.assertEqual(result["samples"][15]["paths"], [])

    def test_old_library_namespace_is_preserved_exactly(self):
        result = parse_maschine(kit("7 Mile Kit.mxgrp").read_bytes())
        reference = result["samples"][0]["sample_references"][0]
        self.assertEqual(result["format_details"]["archive_version"], 15)
        self.assertEqual(reference["path"], "//Samples/Drums/Kick/Kick 7Mile 1.wav")
        self.assertEqual(reference["library"], "Conant Gardens")
        self.assertTrue(reference["library_root"].endswith("Conant Gardens Library/"))

    def test_corrupt_path_length_is_not_reconstructed_or_silently_empty(self):
        data = bytearray(kit("Baby Mayka Kit.mxgrp").read_bytes())
        offset = data.index(b"Samples/Drums/Kick/Kick BabyMayka 1.wav")
        data[offset - 1] += 1
        with self.assertRaises(FormatError):
            parse_maschine(bytes(data))

    def test_missing_zone_marker_does_not_turn_sampler_into_empty_pad(self):
        data = bytearray(kit("Baby Mayka Kit.mxgrp").read_bytes())
        result = parse_maschine(bytes(data))
        offset = result["samples"][1]["sample_references"][0]["source_offset"]
        data[offset + 1] = 46
        with self.assertRaises(FormatError):
            parse_maschine(bytes(data))

    def test_unknown_archive_version_is_explicitly_unsupported(self):
        data = bytearray(kit("Baby Mayka Kit.mxgrp").read_bytes())
        offset = data.index(b"serialization::archive") + len(b"serialization::archive")
        data[offset + 1] = 99
        with self.assertRaisesRegex(FormatError, "version 99"):
            parse_maschine(bytes(data))

    def test_truncated_container_is_rejected(self):
        data = kit("Baby Mayka Kit.mxgrp").read_bytes()
        with self.assertRaises(FormatError):
            parse_maschine(data[:-1])

    def test_builder_uses_decoded_metadata_and_preserves_other_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diagnostic = root / "parsed" / "keep.txt"
            diagnostic.parent.mkdir()
            diagnostic.write_text("another build", encoding="utf-8")
            result = process_mxgrp_file(str(kit("Baby Mayka Kit.mxgrp")), temporary, False)
            self.assertEqual(result["group"], "Baby Mayka Kit")
            self.assertEqual(result["expansion"], "Aquarius Earth")
            self.assertEqual(result["parser"], "structured-v1")
            self.assertIsNone(result["txt_file"])
            invalid = root / "input"
            invalid.mkdir()
            (invalid / "Broken.mxgrp").write_bytes(b"Samples/Fake.wav")
            self.assertEqual(GroupsJsonBuilder(str(invalid), temporary, generate_txt=False).run(), 1)
            report = json.loads((root / "all_groups.report.json").read_text(encoding="utf-8"))
            self.assertEqual(len(report["errors"]), 1)
            self.assertEqual(diagnostic.read_text(encoding="utf-8"), "another build")


if __name__ == "__main__":
    unittest.main()
