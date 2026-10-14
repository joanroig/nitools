"""Legacy bounded frame locator for prepared project routing only.

Kit decoding uses the sequential archive reader; this project patcher remains
separate until the complete Project schema is implemented.
"""
from dataclasses import dataclass
import re
from formats.ni_container import FormatError

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
