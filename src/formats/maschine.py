"""Read sample references from Maschine 2's portable Boost archive.

This is a deliberately limited binary reader for the Group/Sound and sample
reference records in validated Maschine 2 archive layouts. It validates the NI object
container, length-prefixed UTF-8 strings, tracked property IDs and the fixed
16-element Sound vector. Instruments/effects are opaque. Unknown record
layouts are errors, rather than a reason to extract printable byte fragments.
"""

from dataclasses import dataclass
import re
import struct

from formats.ni_container import FormatError, read_container
from formats.maschine_modules import Modules


@dataclass(frozen=True)
class _Name:
    offset: int
    end: int
    object_id: int
    text: str


def _uint(data, offset):
    """Boost portable integer: byte count, followed by little-endian bytes."""
    if offset >= len(data):
        raise FormatError("Truncated portable archive integer")
    width = data[offset]
    end = offset + 1 + width
    if width > 4 or end > len(data):
        raise FormatError(f"Invalid portable archive integer at {offset}")
    if width and data[end - 1] == 0:
        raise FormatError(f"Noncanonical portable archive integer at {offset}")
    return int.from_bytes(data[offset + 1:end], "little"), end


def _encoded(value):
    width = (value.bit_length() + 7) // 8
    return bytes([width]) + value.to_bytes(width, "little")


def _text(data, offset):
    size, start = _uint(data, offset)
    end = start + size
    if size > 1024 * 1024 or end > len(data):
        raise FormatError(f"Invalid archive string length at {offset}")
    try:
        value = data[start:end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"Invalid archive UTF-8 at {offset}") from error
    if any(ord(character) < 32 for character in value):
        raise FormatError(f"Control character in archive string at {offset}")
    return value, end


def _ids(data, offset, first, count):
    for expected in range(first, first + count):
        value, offset = _uint(data, offset)
        if value != expected:
            raise FormatError("Unsupported tracked property layout")
    return offset


_TRACKED_ID = rb"(?:\x01[\x01-\xff]|\x02.[\x01-\xff]|\x03..[\x01-\xff]|\x04...[\x01-\xff])"
_NAME_PAYLOAD = rb"((?:\x00|\x01[\x01-\xff]|\x02.[\x01-\xff]))[\x20-\xff]*" + _TRACKED_ID * 3
_NAME_FRAMES = {
    False: (re.compile(rb"(?=" + _TRACKED_ID + rb"\x00" + _NAME_PAYLOAD + rb")", re.DOTALL),),
    True: tuple(re.compile(rb"(?=" + _TRACKED_ID + metadata + _NAME_PAYLOAD + rb")", re.DOTALL)
                for metadata in (b"", rb"\x00\x00")),
}


def _channel_names(data, start, legacy=False, expected_count=17):
    """Locate bounded Channel name-property frames, including empty names.

    A Channel name property is followed by tracked parameter objects, a
    numeric value/override record, and further tracked parameter objects.
    Group and Sound use this same frame; Pattern and Macro names do not.
    This uses the serialized object graph, never sample filename ordering.
    """
    result = []
    # Require the canonical tracked ID preceding a name before entering Python.
    # The old scan visited almost every zero byte in opaque plugin payloads.
    # Both legacy metadata forms and overlapping frames remain candidates;
    # the complete property/parameter validation below is unchanged.
    offsets = sorted({match.start(1)
                      for pattern in _NAME_FRAMES[legacy]
                      for match in pattern.finditer(data, max(0, start - 7), len(data) - 30)
                      if match.start(1) >= start})
    for offset in offsets:
        try:
            size, text_start = _uint(data, offset)
            end = text_start + size
            if size > 1024 * 1024 or end > len(data):
                continue
            first, cursor = _uint(data, end)
            if first < 2:
                continue
            previous = _encoded(first - 1) + (b"" if legacy else b"\x00")
            if (data[offset - len(previous):offset] != previous
                    and not (legacy and data[offset - len(previous) - 2:offset] == previous + b"\0\0")):
                continue
            cursor = _ids(data, cursor, first + 1, 2 if legacy else 3)
            # Three floats, an optional-value flag (portable bool), then one
            # float. A stored override changes the flag's encoded width.
            override, cursor = _uint(data, cursor + (12 if legacy else 13))
            if override not in (0, 1):
                continue
            cursor = _ids(data, cursor + 4, first + (3 if legacy else 4), 4 if legacy else 5)
            if legacy:
                for _ in range(5):
                    _, cursor = _uint(data, cursor)
                cursor = _ids(data, cursor, first + 7, 3)
            # Decode UTF-8 only after the binary frame is valid, avoiding
            # speculative text decoding of unrelated instrument payloads.
            value, _ = _text(data, offset)
        except FormatError:
            continue
        result.append(_Name(offset, end, first - 1, value))
    if len(result) != expected_count:
        raise FormatError(
            f"Unsupported Maschine Channel layout: expected {expected_count} channels, found {len(result)}"
        )
    if any(a.object_id >= b.object_id for a, b in zip(result, result[1:])):
        raise FormatError("Unordered Maschine Channel object IDs")
    return result


def _sample_references(data, sound, following, absolute_offset, registered, legacy=False, sampler_class=40, zone_class=45):
    references = []
    cursor = sound.end
    first_marker = None
    first_registered = False
    # The Channel's first plugin owns tracked object name_id + 18 (legacy)
    # or +23. Its class ID comes from the actual Sampler registration.
    # Check the plugin independently of its sample map so corrupt/missing
    # zone records cannot turn a sample-bearing slot into a silent blank.
    sampler_pointer = _encoded(sampler_class) + _encoded(sound.object_id + (18 if legacy else 23))
    sampler_declaration = _encoded(sampler_class) + b"\x01\x1bNI::MASCHINE::DATA::Sampler"
    has_sampler = (
        data.find(sampler_pointer, sound.end, following.offset) >= 0
        or data.find(sampler_declaration, sound.end, following.offset) >= 0
    )
    if not has_sampler:
        return [], registered
    declared_count = None
    while True:
        marker = data.find(_encoded(zone_class), cursor, following.offset)
        if marker < 0:
            break
        cursor = marker + 2
        framed = False
        try:
            object_id, at = _uint(data, cursor)
            is_registration = object_id == 1
            if is_registration:
                class_version, at = _uint(data, at)
                object_id, at = _uint(data, at)
                if class_version != 2 or registered:
                    continue
                if data[at:at + 2] == b"\0\0":
                    at += 2  # First FileLocation class use; another plugin may own it.
            if not sound.object_id < object_id < following.object_id:
                continue
            framed = is_registration or data[marker - 2:marker] == b"\x01\x01"
            path_kind, at = _uint(data, at)
            if path_kind not in (0, 2):
                if framed:
                    raise FormatError(f"Unsupported sample path kind {path_kind}")
                continue
            framed = framed or path_kind == 2
            if not is_registration and not registered:
                raise FormatError("Missing sample-reference class registration")
            path, at = _text(data, at)
            root = library = ""
            if path_kind:
                if data[at:at + 2] == b"\0\0":
                    at += 2
                root, at = _text(data, at)
                library, at = _text(data, at)
            if not path and path_kind:
                raise FormatError("Empty Maschine sample reference")
            if is_registration and data[at:at + 3] == b"\x01\x01\x00":
                at = _ids(data, at + 3, object_id + 1, 1)
                if data[at:at + 2] != b"\0\0":
                    raise FormatError("Unsupported sample parameter base metadata")
                at = _ids(data, at + 2, object_id + 2, 2 if legacy else 3)
            else:
                at = _ids(data, at, object_id + 1, 3 if legacy else 4)
            if legacy:
                # Legacy integer parameters store five portable values, not
                # five fixed bytes (nonzero sample offsets need wider values).
                for _ in range(5):
                    _, at = _uint(data, at)
                at = _ids(data, at, object_id + 4, 2)
        except FormatError:
            if framed and (declared_count is None or len(references) < declared_count):
                raise
            continue
        if first_marker is None:
            first_marker = marker
            first_registered = is_registration
            declared_count, _ = _uint(data, marker - (7 if is_registration else 4))
        references.append({
            "path": path,
            "path_kind": path_kind,
            "library_root": root,
            "library": library,
            "object_id": object_id,
            "source_offset": absolute_offset + marker,
        })
        registered = True
        cursor = at

    if has_sampler and not references:
        raise FormatError(f"Missing or unsupported sample map for {sound.text!r}")
    if references:
        # First use adds the vector's class metadata; later instances contain
        # count and item version immediately before their first element.
        count_offset = first_marker - (7 if first_registered else 4)
        count, _ = _uint(data, count_offset)
        if count != len(references):
            raise FormatError(
                f"Unsupported or damaged sample map for {sound.text!r}: "
                f"declares {count} references, decoded {len(references)}"
            )
    return references, registered


def parse_maschine(data: bytes, *, include_plugin_state=False) -> dict:
    container = read_container(data)
    headers = [obj.header.find(b"DSIN", 109) for obj in container.walk()]
    headers = [header for header in headers if header is not None]
    if len(headers) != 1:
        raise FormatError("Expected one Maschine archive object")
    header = headers[0]
    payload = header.payload
    if len(payload) < 32:
        raise FormatError("Truncated Maschine archive object")
    version, stored_size, archive_size = struct.unpack_from("<IQI", payload)
    if version != 1 or stored_size + 28 != len(payload) or archive_size + 4 != stored_size:
        raise FormatError("Unsupported Maschine archive compression or length")
    archive = payload[16:16 + archive_size]
    signature, cursor = _text(archive, 0)
    if signature != "serialization::archive":
        raise FormatError("Missing portable archive signature")
    archive_version, cursor = _uint(archive, cursor)
    supported = {10: (1, 2, 4, 9), 12: (9,), 13: (13,),
                 14: (14, 15, 16), 15: (16, 18, 19, 20, 22),
                 16: (22,), 17: (22,), 18: (22, 23), 19: (23,)}
    if archive_version not in supported:
        raise FormatError(f"Unsupported Maschine archive version {archive_version}")
    for expected in (0, 1):
        actual, cursor = _uint(archive, cursor)
        if actual != expected:
            raise FormatError("Unsupported Maschine Group archive header")
    group_version, cursor = _uint(archive, cursor)
    if group_version not in supported[archive_version]:
        raise FormatError(f"Unsupported Maschine Group schema {group_version} in archive {archive_version}")
    for expected in (0, 0, 0, 2, 1, 0, 1):
        actual, cursor = _uint(archive, cursor)
        if actual != expected:
            raise FormatError("Unsupported Maschine Group archive header")
    library_version, cursor = _uint(archive, cursor)
    if library_version not in (0, 1):
        raise FormatError("Unsupported Maschine library metadata")
    expansion = ""
    expansion_id = ""
    if library_version:
        expansion, cursor = _text(archive, cursor)
        expansion_id, cursor = _text(archive, cursor)
        # Factory libraries can store different display and product names.

    # Boost archive versions and NI class versions are independent. Keep the
    # observed class registrations explicit, including older parameter layouts.
    legacy = group_version <= 9
    vector_profiles = {
        1: ((17, 1, 61), (17, 2, 61), (17, 3, 61)), 2: ((21, 3, 61),), 4: ((21, 3, 65),),
        9: ((21, 4, 68), (21, 5, 68), (21, 6, 68)), 13: ((16, 6, 45),),
        14: ((16, 6, 45),), 15: ((16, 8, 45),), 16: ((16, 8, 45),),
        18: ((16, 8, 45),), 19: ((16, 8, 41),), 20: ((16, 8, 41),),
        22: ((16, 8, 41), (16, 9, 41)), 23: ((16, 9, 41),),
    }
    vectors = []
    for sound_class, sound_version, first_id in vector_profiles[group_version]:
        vector_header = b"".join(_encoded(value) for value in (16, 1, 0, 1, sound_class, 1, sound_version, first_id))
        vector_start = archive.find(vector_header, cursor)
        if vector_start >= 0:
            if archive.find(vector_header, vector_start + 1) >= 0:
                raise FormatError("Ambiguous Maschine 16-Sound vector")
            vectors.append(vector_start + len(vector_header))
    if len(vectors) != 1:
        raise FormatError("Unsupported Maschine 16-Sound vector")
    names = _channel_names(archive, vectors[0], legacy)
    # Class IDs are assigned in serialization order: an earlier effect or
    # instrument can change the Sampler ID. Read its actual class registration.
    declaration = b"\x01\x1bNI::MASCHINE::DATA::Sampler\x01\x01"
    declaration_at = archive.find(declaration, vectors[0])
    sampler_class = None
    zone_class = None
    if declaration_at >= 0:
        sampler_class, end = _uint(archive, declaration_at - 2)
        if end != declaration_at or archive.find(declaration, declaration_at + 1) >= 0:
            raise FormatError("Unsupported Sampler class registration")
        at = declaration_at + len(declaration)
        _, at = _uint(archive, at)  # Sampler class version
        sampler_id, at = _uint(archive, at)
        # The first Zone registers its own class. The Sampler's base class may
        # already have been registered by a different plugin, changing this ID.
        for match in re.finditer(rb"\x01[\x01-\xff]\x01\x01\x01\x02", archive[at:at + 40]):
            marker = at + match.start()
            ident, end = _uint(archive, marker + 6)
            if ident == sampler_id + 1:
                zone_class, _ = _uint(archive, marker)
                break
        if zone_class is None:
            raise FormatError("Unsupported Sampler zone-vector registration")
    samples = []
    registered = False
    modules = Modules(archive, vectors[0], legacy)
    for pad, (sound, following) in enumerate(zip(names, names[1:]), 1):
        references, registered = _sample_references(
            archive, sound, following, header.offset + 16, registered,
            legacy, sampler_class, zone_class,
        ) if sampler_class is not None else ([], registered)
        module = modules.first(sound, following)
        instrument = None
        if module and module[0] == 'AudioModule':
            references = modules.audio(module, following, header.offset + 16)
        elif module and module[0] != 'Sampler' and not references:
            instrument = modules.instrument(module, following, include_plugin_state)
        paths = [reference["path"] for reference in references if reference['path']]
        samples.append({
            "pad": pad,
            "name": sound.text,
            "type": "sample" if len(paths) == 1 else "multisample" if paths else "no_sample",
            "paths": paths,
            "sample_references": references,
            "empty_zones": sum(not reference['path'] for reference in references),
            "source_offset": header.offset + 16 + sound.offset,
            "status": "samples" if paths else "no_sample_reference",
            **({'instrument': instrument} if instrument else {}),
            **({'sample_module': 'Audio'} if module and module[0] == 'AudioModule' else {}),
        })
    return {
        "group": names[-1].text,
        "expansion": expansion,
        "samples": samples,
        "parser": "structured-v1",
        "source": "Maschine",
        "format_details": {
            "format": "maschine-portable-archive",
            "archive_version": archive_version,
            "group_version": group_version,
            "library_identifier": expansion_id,
            "sample_mode": "raw",
            "sound_slots": 16,
            "zone_parameters": "not_decoded",
        },
    }
