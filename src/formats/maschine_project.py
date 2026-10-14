"""Validate a single-kit Maschine 2/3 VST3 state and enable pad MIDI routing.

Only the Group's serialized routing property is changed. The original kit,
instruments, effects and other project state are preserved. Unknown layouts
are rejected. No proprietary preset or template is bundled.
"""

import struct

from formats.maschine import _channel_names, _encoded, _ids, _text, _uint
from formats.ni_container import FormatError, read_container


def vst3_chunks(data):
    if len(data) < 56 or data[:8] != b'VST3\x01\0\0\0':
        raise FormatError('Invalid VST3 preset header')
    at = struct.unpack_from('<Q', data, 40)[0]
    if at < 48 or at + 8 > len(data) or data[at:at + 4] != b'List':
        raise FormatError('Invalid VST3 chunk list')
    count = struct.unpack_from('<I', data, at + 4)[0]
    if count > 64 or at + 8 + count * 20 != len(data):
        raise FormatError('Invalid VST3 chunk count')
    chunks = []
    ranges = []
    for index in range(count):
        tag, offset, size = struct.unpack_from('<4sQQ', data, at + 8 + index * 20)
        if offset < 48 or offset + size > at or tag in {item[0] for item in chunks}:
            raise FormatError('Invalid VST3 chunk bounds')
        if any(offset < end and offset + size > start for start, end in ranges):
            raise FormatError('Overlapping VST3 chunks')
        ranges.append((offset, offset + size))
        chunks.append((tag, data[offset:offset + size]))
    return data[8:40], chunks


def build_vst3(class_id, chunks):
    if len(class_id) != 32:
        raise FormatError('Invalid VST3 class ID')
    body = b''.join(payload for _, payload in chunks)
    at = 48
    entries = []
    for tag, payload in chunks:
        entries.append(struct.pack('<4sQQ', tag, at, len(payload)))
        at += len(payload)
    return (b'VST3\x01\0\0\0' + class_id + struct.pack('<Q', at) + body
            + b'List' + struct.pack('<I', len(entries)) + b''.join(entries))


def _serialize(obj, source, changed_header, payload):
    def header(item):
        content = payload if item is changed_header else item.payload
        prefix = item.tag + struct.pack('<II', item.type_id, item.version)
        if item.base is None:
            return prefix + content
        base = header(item.base)
        return prefix + struct.pack('<Q', len(base)) + base + content

    head = header(obj.header)
    children = b''.join(struct.pack('<I4sI', field, *child.reference)
                        + _serialize(child, source, changed_header, payload)
                        for field, child in obj.children)
    size = 48 + len(head) + len(children)
    return (struct.pack('<Q', size) + source[obj.offset + 8:obj.offset + 40]
            + struct.pack('<Q', len(head)) + head + children)


def route_kit_preset(preset, expected_names, expected_group):
    class_id, chunks = vst3_chunks(preset)
    components = [data for tag, data in chunks if tag == b'Comp']
    if len(components) != 1:
        raise FormatError('Expected one VST3 component state')
    source = components[0]
    root = read_container(source)
    if not any(obj.reference == (b'2SAM', 1347571530) for obj in root.walk()):
        raise FormatError('State is not a Maschine project')
    headers = [h for obj in root.walk() if (h := obj.header.find(b'DSIN', 109))]
    if len(headers) != 1 or len(headers[0].payload) < 32:
        raise FormatError('Expected one uncompressed Maschine project archive')
    h = headers[0]
    version, stored, length = struct.unpack_from('<IQI', h.payload)
    if version != 1 or stored != length + 4 or stored + 28 != len(h.payload):
        raise FormatError('Unsupported project archive storage')
    archive = h.payload[16:16 + length]
    signature, at = _text(archive, 0)
    archive_version, _ = _uint(archive, at)
    if signature != 'serialization::archive' or archive_version not in (19, 20):
        raise FormatError('Unsupported Maschine project archive; validated versions are 19 (Maschine 2.18.4) and 20 (Maschine 3.7.1)')
    names = _channel_names(archive, 0, expected_count=18)
    if len(expected_names) != 16 or [n.text for n in names[:16]] != list(expected_names) or names[16].text != expected_group:
        raise FormatError('Loaded kit does not match the selected kit and its 16 sound names. Load it into the only Group, A1.')
    group, master = names[-2:]
    # In the validated v19/v20 layouts, the last three Group Boolean parameters
    # precede the Master Channel's object graph. The first is Drumkit mode.
    ident = master.object_id - 28
    marker = b''.join(_encoded(n) for n in range(ident, ident + 5))
    at = archive.find(marker, group.end, master.offset)
    if at < 0 or archive.find(marker, at + 1, master.offset) >= 0:
        raise FormatError('Unsupported Group MIDI routing layout')
    values_at = at + len(marker)
    values = []
    end = values_at
    for _ in range(6):
        value, end = _uint(archive, end)
        values.append(value)
    if tuple(values) not in ((0, 0, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0), (0, 1, 1, 0, 0, 0)):
        raise FormatError(f'Unsupported Group key-mode parameter: {tuple(values)}')
    tail = end
    for next_id in (ident + 5, ident + 10):
        tail = _ids(archive, tail, next_id, 5)
        for _ in range(6):
            value, tail = _uint(archive, tail)
            if value != 0:
                raise FormatError('Non-default Group routing: prepare this kit with a fresh Maschine instance')
    routed = archive[:values_at] + b''.join(_encoded(v) for v in (0, 1, 1, 0, 0, 0)) + archive[end:]
    payload = struct.pack('<IQI', 1, len(routed) + 4, len(routed)) + routed + h.payload[16 + length:]
    replacement = _serialize(root, source, h, payload)
    return build_vst3(class_id, [(tag, replacement if tag == b'Comp' else data) for tag, data in chunks])
