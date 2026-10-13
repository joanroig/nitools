"""Bounded NI Hsin object/class readers and FastLZ decompression.

All offsets and lengths are read from the stream. No string or magic scanning
is used to select objects. Unknown class payloads remain opaque.
"""

from dataclasses import dataclass
import struct


class FormatError(ValueError):
    """The file is malformed or uses an unsupported serialization variant."""


@dataclass
class ClassHeader:
    tag: bytes
    type_id: int
    version: int
    payload: bytes
    offset: int
    base: "ClassHeader | None" = None

    def find(self, tag, type_id):
        current = self
        while current is not None:
            if (current.tag, current.type_id) == (tag, type_id):
                return current
            current = current.base
        return None


@dataclass
class Object:
    header: ClassHeader
    children: list[tuple[int, "Object"]]
    offset: int
    size: int
    reference: tuple[bytes, int] | None = None

    def walk(self):
        yield self
        for _, child in self.children:
            yield from child.walk()


def _class(data, start, end, depth):
    if depth > 64 or end - start < 12:
        raise FormatError(f"Invalid class header at {start}")
    tag = data[start:start + 4]
    type_id, version = struct.unpack_from("<II", data, start + 4)
    if version != 1:
        raise FormatError(f"Unsupported class version {version} at {start}")
    if (tag, type_id) == (b"DSIN", 1):
        if end - start != 24:
            raise FormatError(f"Invalid base class size at {start}")
        return ClassHeader(tag, type_id, version, data[start + 12:end], start + 12)
    if end - start < 20:
        raise FormatError(f"Truncated class at {start}")
    base_size = struct.unpack_from("<Q", data, start + 12)[0]
    base_end = start + 20 + base_size
    if not base_size or base_end > end:
        raise FormatError(f"Invalid base class length at {start}")
    base = _class(data, start + 20, base_end, depth + 1)
    return ClassHeader(tag, type_id, version, data[base_end:end], base_end, base)


def read_container(data: bytes) -> Object:
    def read(start, bound, depth):
        if depth > 64 or bound - start < 48:
            raise FormatError(f"Truncated NI object at {start}")
        size, version, magic, header_version, reserved = struct.unpack_from("<QI4sII", data, start)
        end = start + size
        if size < 48 or end > bound:
            raise FormatError(f"Invalid NI object length at {start}")
        if (version, magic, header_version, reserved) != (1, b"hsin", 1, 0):
            raise FormatError(f"Unsupported NI object header at {start}")
        header_size = struct.unpack_from("<Q", data, start + 40)[0]
        cursor = start + 48 + header_size
        if cursor > end:
            raise FormatError(f"Invalid class length at {start}")
        header = _class(data, start + 48, cursor, 0)
        children = []
        while cursor < end:
            if end - cursor < 12:
                raise FormatError(f"Truncated object reference at {cursor}")
            field_id, tag, type_id = struct.unpack_from("<I4sI", data, cursor)
            child = read(cursor + 12, end, depth + 1)
            # The external object type may differ from its serialized base
            # header (Maschine's 2SAM/GRP object uses a DSIN/101 header).
            child.reference = (tag, type_id)
            children.append((field_id, child))
            cursor += 12 + child.size
        return Object(header, children, start, size)

    result = read(0, len(data), 0)
    if result.size != len(data):
        raise FormatError("Trailing bytes after NI object")
    return result


def decompress_fastlz(source: bytes, limit: int = 64 * 1024 * 1024) -> bytes:
    """Decode FastLZ levels 1/2, rejecting truncated or invalid references."""
    if not source:
        raise FormatError("Empty FastLZ stream")
    level = (source[0] >> 5) + 1
    if level not in (1, 2):
        raise FormatError(f"Unsupported FastLZ level: {level}")
    cursor = 1
    control = source[0] & 31
    output = bytearray()

    def read_byte():
        nonlocal cursor
        if cursor >= len(source):
            raise FormatError("Truncated FastLZ stream")
        value = source[cursor]
        cursor += 1
        return value

    while True:
        if control < 32:
            count = control + 1
            if cursor + count > len(source):
                raise FormatError("Truncated FastLZ literal")
            if len(output) + count > limit:
                raise FormatError("FastLZ output limit exceeded")
            output.extend(source[cursor:cursor + count])
            cursor += count
        else:
            count = (control >> 5) + 2
            high = (control & 31) << 8
            if count == 9:
                while True:
                    extra = read_byte()
                    count += extra
                    if level == 1 or extra != 255:
                        break
            low = read_byte()
            distance = high + low + 1
            if level == 2 and high == 7936 and low == 255:
                distance = (read_byte() << 8) + read_byte() + 8192
            if distance > len(output):
                raise FormatError("FastLZ back-reference precedes output")
            if len(output) + count > limit:
                raise FormatError("FastLZ output limit exceeded")
            if count <= distance:
                start = len(output) - distance
                output.extend(output[start:start + count])
            else:
                # Overlapping matches repeat the already decoded pattern.
                # Copy in C rather than dispatching a Python loop per byte.
                pattern = output[-distance:]
                repeats, remainder = divmod(count, distance)
                output.extend(pattern * repeats + pattern[:remainder])
        if cursor == len(source):
            return bytes(output)
        control = read_byte()
