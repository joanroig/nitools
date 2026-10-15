"""Synthetic format fixtures; no NI kits, samples or native code are bundled."""

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formats.battery import Reader, _path, parse_battery
from formats.ni_container import FormatError, decompress_fastlz, read_container
from processors.kits.build_kits_json import KitsJsonBuilder


def pack(kind, *values):
    return struct.pack("<" + kind, *values)


def text(value):
    encoded = value.encode("utf-16le")
    return pack("I", len(encoded) // 2) + encoded


def path_record(value):
    parts = value.split("/")
    result = pack("I", len(parts))
    for index, part in enumerate(parts):
        result += b"\x03" if part == ".." else bytes([4 if index == len(parts) - 1 else 2]) + text(part)
    return result


def chunk(tag, payload):
    return pack("HI", tag, len(payload)) + payload


def legacy_object(common_tag, common, header, body=b""):
    return b"\x01" + chunk(common_tag, common) + pack("I", len(header)) + header + pack("I", len(body)) + body


BASE = b"DSIN" + pack("IIIII", 1, 1, 1, 1, 1)


def class_header(tag, kind, payload=b"", base=BASE):
    return tag + pack("IIQ", kind, 1, len(base)) + base + payload


def ni_object(header, children=b""):
    size = 48 + len(header) + len(children)
    return pack("QI4sII", size, 1, b"hsin", 1, 0) + bytes(16) + pack("Q", len(header)) + header + children


def child(field, tag, kind, obj):
    return pack("I4sI", field, tag, kind) + obj


def fixture(paths=None, assignments=None, rows=4, columns=4, *,
            kit_tag=171, zone_tag=152, path_version=2, auxiliary_paths=None, base_path=None):
    paths = paths if paths is not None else ["../../Samples/Kick\u00a0é.wav", "../../Samples/Lick G#.wav"]
    # Serialized zone order is intentionally different from cell/display order.
    assignments = assignments if assignments is not None else [(16, 1), (0, 0), (16, 0)]
    common = bytearray({163: 93, 164: 89, 168: 99, 171: 99, 174: 113, 175: 113, 178: 113}[kit_tag])
    struct.pack_into("<II", common, 48, rows, columns)
    cells = pack("I", 128) + b"".join(
        legacy_object(149, b"", text(f"Cell {index}") + bytes(36)) for index in range(128)
    )
    zones = pack("I", len(assignments))
    for cell, sample in assignments:
        properties = bytearray(76 if zone_tag == 152 else 82)
        struct.pack_into("<I", properties, 42 if zone_tag == 152 else 48, sample)
        zones += pack("I", cell) + legacy_object(zone_tag, b"", properties)
    kit = legacy_object(kit_tag, common, text("Fixture"), chunk(51, cells) + chunk(52, zones))
    if path_version == 2:
        table = pack("HI", 2, 1) + (pack("I", 0) if base_path is None else base_path)
        table += pack("I", len(paths)) + b"".join(map(path_record, paths))
        auxiliary_paths = [(path_record("Fixture.nbkt"), 1)] if auxiliary_paths is None else auxiliary_paths
        table += bytes(12 * len(paths)) + pack("I", len(auxiliary_paths))
        table += b"".join(path for path, flag in auxiliary_paths)
        table += b"".join(pack("H", flag) for path, flag in auxiliary_paths)
    else:
        table = pack("HI", path_version, len(paths))
        table += b"".join(bytes(8) + path_record(path) + bytes(20) for path in paths)
    legacy = chunk(40, kit) + chunk(75, table)
    inner_header = class_header(b"DSIN", 109, pack("IQ", 1, len(legacy)) + legacy + bytes(16))
    inner = ni_object(BASE, child(0, b"DSIN", 109, ni_object(inner_header)))
    # Independent literal-only FastLZ2 encoder, exercising the real container path.
    compressed = bytearray()
    for start in range(0, len(inner), 32):
        run = inner[start:start + 32]
        compressed += bytes([len(run) - 1]) + run
    compressed[0] |= 32
    compression = class_header(b"DSIN", 115, b"\0" + pack("I", len(compressed)) + compressed + bytes(8))
    payload = ni_object(class_header(b"DSIN", 116, bytes(5), compression))
    kit_object = ni_object(class_header(b"4KIN", 3), child(1, b"DSIN", 116, payload))
    return ni_object(class_header(b"DSIN", 118), child(0, b"4KIN", 3, kit_object))


class BatteryFormatTests(unittest.TestCase):
    def test_paths_cells_holes_and_layer_assignments(self):
        kit = parse_battery(fixture())
        self.assertEqual(kit["kit"], "Fixture")
        self.assertEqual((kit["rows"], kit["columns"]), (4, 4))
        self.assertEqual(len(kit["samples"]), 16)
        self.assertEqual(kit["samples"][0]["paths"], ["../../Samples/Kick\u00a0é.wav"])
        self.assertEqual(kit["samples"][1]["type"], "empty")
        self.assertEqual(kit["samples"][4]["cell_id"], 16)
        self.assertEqual(kit["samples"][4]["paths"], ["../../Samples/Lick G#.wav", "../../Samples/Kick\u00a0é.wav"])
        self.assertEqual(kit["samples"][4]["type"], "multisample")
        self.assertEqual(kit["zone_count"], 3)

    def test_grid_is_read_not_inferred_from_sample_count(self):
        kit = parse_battery(fixture(assignments=[(17, 0)], rows=6, columns=12))
        self.assertEqual(len(kit["samples"]), 72)
        self.assertEqual(kit["samples"][13]["cell_id"], 17)
        self.assertEqual(kit["samples"][13]["pad"], 14)
        self.assertEqual(kit["samples"][13]["paths"], ["../../Samples/Kick\u00a0é.wav"])

    def test_repeated_sample_reference_is_not_deduplicated(self):
        kit = parse_battery(fixture(assignments=[(0, 0), (0, 0), (1, 0)]))
        self.assertEqual(len(kit["samples"][0]["paths"]), 2)
        self.assertEqual(kit["samples"][1]["paths"], kit["samples"][0]["paths"][:1])

    def test_explicit_kit_and_zone_versions_preserve_assignments(self):
        expected = parse_battery(fixture())
        for tag in (163, 164, 168, 171, 174, 175, 178):
            for zone in (152, 154):
                with self.subTest(kit=tag, zone=zone):
                    actual = parse_battery(fixture(kit_tag=tag, zone_tag=zone))
                    self.assertEqual((actual['rows'], actual['columns']), (4, 4))
                    self.assertEqual([(s['cell_id'], s['paths']) for s in actual['samples']],
                                     [(s['cell_id'], s['paths']) for s in expected['samples']])

    def test_auxiliary_archive_paths_are_not_sample_references(self):
        archive = (pack('I', 4) + b'\x06\x02' + text('Impulse Responses')
                   + b'\x08' + text('IR.nkx') + b'\x04' + text('Room.wav'))
        for auxiliary in ([], [(archive, 0)], [(path_record('Fixture.nbkt'), 1), (archive, 0)]):
            result = parse_battery(fixture(auxiliary_paths=auxiliary))
            self.assertEqual(result['zone_count'], 3)
            self.assertFalse(any('Room.wav' in r['path'] for r in result['sample_table']))
        with self.assertRaises(FormatError):
            parse_battery(fixture(auxiliary_paths=[(archive[:-1], 0)]))
        with self.assertRaises(FormatError):
            parse_battery(fixture(auxiliary_paths=[(archive, 9)]))
        with self.assertRaises(FormatError):
            _path(Reader(archive))  # Archive members are not filesystem samples.

    def test_posix_root_and_saved_base_directory(self):
        root = pack('I', 2) + b'\x01' + text('') + b'\x02' + text('Library')
        absolute = pack('I', 3) + b'\x01' + text('') + b'\x02' + text('Samples') + b'\x04' + text('é.wav')
        self.assertEqual(_path(Reader(absolute)), '/Samples/é.wav')
        # Stored base paths must not change already serialized sample references.
        self.assertEqual(parse_battery(fixture(base_path=root))['samples'][0]['paths'],
                         parse_battery(fixture())['samples'][0]['paths'])

    def test_v3_resource_order_is_kept_for_zone_indices(self):
        result = parse_battery(fixture(paths=['Kit.nbkt', 'Samples/One.wav', 'Samples/Two.wav'],
                                      assignments=[(0, 2), (1, 1)], kit_tag=178, zone_tag=154, path_version=3))
        self.assertEqual(result['samples'][0]['paths'], ['Samples/Two.wav'])
        self.assertEqual(result['samples'][1]['paths'], ['Samples/One.wav'])
        self.assertEqual(result['format'], 'Battery 4 / path table 3')
        with self.assertRaises(FormatError):
            parse_battery(fixture(path_version=4))

    def test_hidden_cells_are_retained_without_changing_visible_grid(self):
        result = parse_battery(fixture(assignments=[(0, 0), (75, 1)], columns=12))
        self.assertEqual((result['rows'], result['columns']), (4, 12))
        self.assertEqual(len(result['samples']), 48)
        self.assertEqual(result['hidden_cells'][0]['cell_id'], 75)
        self.assertNotIn('pad', result['hidden_cells'][0])
        self.assertEqual(result['hidden_cells'][0]['zones'][0]['sample_index'], 1)
        self.assertEqual(result['zone_count'], 2)

    def test_invalid_zone_references_fail_instead_of_guessing(self):
        for assignments in ([(0, 2)], [(128, 0)]):
            with self.subTest(assignments=assignments), self.assertRaises(FormatError):
                parse_battery(fixture(assignments=assignments))

    def test_truncated_or_trailing_container_is_rejected(self):
        raw = fixture()
        for damaged in (raw[:40], raw[:-1], raw + b"extra"):
            with self.assertRaises(FormatError):
                parse_battery(damaged)

    def test_unknown_path_tokens_are_not_reconstructed(self):
        with self.assertRaises(FormatError):
            _path(Reader(pack("I", 1) + b"\x7f"))

    def test_unicode_path_uses_utf16_code_units(self):
        value = "../../Samples/\U0001f941 G#.wav"
        self.assertEqual(_path(Reader(path_record(value))), value)

    def test_fastlz_level2_long_match_extension(self):
        # Literal A; level2 extended match 9+255+10 copies at distance1.
        self.assertEqual(decompress_fastlz(b"\x20A\xe0\xff\x0a\x00"), b"A" * 275)

    def test_fastlz_level2_far_backreference(self):
        literal = bytes(range(256)) * 32
        stream = bytearray()
        for start in range(0, len(literal), 32):
            stream += b"\x1f" + literal[start:start + 32]
        stream[0] |= 32
        stream += b"\x3f\xff\x00\x00"  # three bytes from distance8192
        self.assertEqual(decompress_fastlz(stream), literal + literal[:3])

    def test_fastlz_invalid_input_never_pads_with_zero(self):
        for source in (b"", b"\x02A", b"\x20A\x20\x05", b"\x60A", b"\x20A\xe0"):
            with self.subTest(source=source), self.assertRaises(FormatError):
                decompress_fastlz(source)
        with self.assertRaises(FormatError):
            decompress_fastlz(b"\x20A\xe0\xff\x0a\x00", limit=100)

    def test_bad_class_length_cannot_escape_parent(self):
        raw = bytearray(fixture())
        struct.pack_into("<Q", raw, 40, len(raw) + 1)
        with self.assertRaises(FormatError):
            read_container(raw)

    def test_builder_reports_partial_failure_and_keeps_exact_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "valid.nbkt").write_bytes(fixture())
            (source / "bad.nbkt").write_bytes(b"damaged")
            builder = KitsJsonBuilder(str(source), str(output), generate_txt=False)
            self.assertEqual(builder.run(), 1)
            index = json.loads((output / "all_kits.json").read_text(encoding="utf-8"))
            report = json.loads((output / "all_kits.report.json").read_text(encoding="utf-8"))
            self.assertEqual(index[0]["parser"], "structured-v1")
            self.assertEqual(index[0]["sample_root"], source.as_posix())
            self.assertEqual(report["decoded"], 1)
            self.assertEqual(len(report["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
