"""Battery 4 kit reader: NI objects -> FastLZ -> cells, zones and path table.

This is a version-bounded reader, not a search for filenames. Every record is
reached by its parent length/count. Effects, scripts and audio-engine settings
are skipped as opaque, length-delimited payloads.
"""

import struct

from formats.ni_container import FormatError, decompress_fastlz, read_container


class Reader:
    def __init__(self, data: bytes, offset=0):
        self.data = data
        self.offset = offset
        self.position = 0

    def take(self, count):
        if count < 0 or self.position + count > len(self.data):
            raise FormatError(f"Truncated Battery record at {self.offset + self.position}")
        result = self.data[self.position:self.position + count]
        self.position += count
        return result

    def number(self, kind="I"):
        return struct.unpack("<" + kind, self.take(struct.calcsize("<" + kind)))[0]

    def sub(self, count):
        offset = self.offset + self.position
        return Reader(self.take(count), offset)

    def text(self):
        try:
            result = self.take(self.number() * 2).decode("utf-16le")
        except UnicodeError as exc:
            raise FormatError("Invalid Battery UTF-16 text") from exc
        if "\0" in result:
            raise FormatError("Embedded NUL in Battery text")
        return result

    def finish(self):
        if self.position != len(self.data):
            raise FormatError(f"Unexpected Battery data at {self.offset + self.position}")

    def chunk(self):
        tag = self.number("H")
        return tag, self.sub(self.number())


def _chunks(reader):
    result = {}
    while reader.position < len(reader.data):
        tag, payload = reader.chunk()
        result.setdefault(tag, []).append(payload)
    return result


def _only(chunks, tag):
    matches = chunks.get(tag, [])
    if len(matches) != 1:
        raise FormatError(f"Expected one Battery chunk {tag}, found {len(matches)}")
    return matches[0]


def _object(reader, common_tag):
    if reader.number("B") != 1:
        raise FormatError("Unsupported Battery object version")
    tag, common = reader.chunk()
    if tag != common_tag:
        raise FormatError(f"Expected Battery common record {common_tag}, found {tag}")
    header = reader.sub(reader.number())
    body = reader.sub(reader.number())
    return common, header, body


def _path(reader):
    count = reader.number()
    if count > 256:
        raise FormatError("Battery path has too many components")
    parts = []
    for index in range(count):
        token = reader.number("B")
        if token == 3:
            parts.append("..")
        elif token in (2, 4):
            value = reader.text()
            if not value or "/" in value or "\\" in value:
                raise FormatError("Invalid Battery path component")
            if token == 4 and index != count - 1:
                raise FormatError("Battery filename is not the last path component")
            parts.append(value)
        else:
            raise FormatError(f"Unsupported Battery path token {token}")
    return "/".join(parts)


def _paths(reader):
    if (reader.number("H"), reader.number(), reader.number()) != (2, 1, 0):
        raise FormatError("Unsupported Battery path table version")
    count = reader.number()
    if count > 100000:
        raise FormatError("Battery sample table is too large")
    paths = []
    for _ in range(count):
        offset = reader.offset + reader.position
        paths.append({"path": _path(reader), "document_offset": offset})
    # Per-sample timestamps (u64) and flags (u32), followed by the saved kit path.
    reader.take(count * 12)
    if reader.number() != 1:
        raise FormatError("Unsupported Battery source-path record")
    _path(reader)
    if reader.number("H") != 1:
        raise FormatError("Unsupported Battery path-table footer")
    reader.finish()
    return paths


def _find_header(root, type_id):
    matches = [header for item in root.walk()
               if (header := item.header.find(b"DSIN", type_id)) is not None]
    if len(matches) != 1:
        raise FormatError(f"Expected one DSIN/{type_id} record, found {len(matches)}")
    return matches[0]


def decode_document(raw: bytes):
    outer = read_container(raw)
    if not any(item.reference == (b"4KIN", 3) for item in outer.walk()):
        raise FormatError("Not a supported Battery 4 kit container")
    compressed = _find_header(outer, 115)
    stream = Reader(compressed.payload, compressed.offset)
    if stream.number("B") != 0:
        raise FormatError("Unsupported Battery compression header")
    data = decompress_fastlz(stream.take(stream.number()))
    # Eight trailing bytes belong to compression bookkeeping, not FastLZ.
    stream.take(8)
    stream.finish()
    document = read_container(data)
    header = _find_header(document, 109)
    payload = Reader(header.payload, header.offset)
    if payload.number() != 1:
        raise FormatError("Unsupported Battery document version")
    legacy = payload.sub(payload.number("Q"))
    payload.take(16)
    payload.finish()
    return legacy


def parse_battery(raw: bytes) -> dict:
    top = _chunks(decode_document(raw))
    paths = _paths(_only(top, 75))
    kit = _only(top, 40)
    common, header, body = _object(kit, 171)
    kit.finish()
    if len(common.data) != 99:
        raise FormatError("Unsupported Battery grid-settings version")
    rows, columns = struct.unpack_from("<II", common.data, 48)
    if not (1 <= rows <= 8 and 1 <= columns <= 16):
        raise FormatError(f"Invalid Battery grid {rows} x {columns}")
    name = header.text()
    children = _chunks(body)

    cell_reader = _only(children, 51)
    count = cell_reader.number()
    if count != 128:
        raise FormatError(f"Unsupported Battery cell capacity {count}")
    cells = []
    for cell_id in range(count):
        cell_offset = cell_reader.offset + cell_reader.position
        _, properties, _ = _object(cell_reader, 149)
        cells.append({"name": properties.text(), "cell_id": cell_id,
                      "document_offset": cell_offset, "zones": []})
    cell_reader.finish()

    zone_reader = _only(children, 52)
    zone_count = zone_reader.number()
    if zone_count > 100000:
        raise FormatError("Battery zone table is too large")
    for zone_id in range(zone_count):
        zone_offset = zone_reader.offset + zone_reader.position
        cell_id = zone_reader.number()
        _, properties, _ = _object(zone_reader, 152)
        if len(properties.data) != 76:
            raise FormatError("Unsupported Battery zone-settings version")
        sample_index = struct.unpack_from("<I", properties.data, 42)[0]
        if cell_id >= count or sample_index >= len(paths):
            raise FormatError("Battery zone references an absent cell or sample")
        row, column = divmod(cell_id, 16)
        if row >= rows or column >= columns:
            raise FormatError("Battery zone is outside the stored grid")
        cells[cell_id]["zones"].append({
            "zone": zone_id, "sample_index": sample_index,
            "path": paths[sample_index]["path"],
            "document_offset": zone_offset,
            "path_document_offset": paths[sample_index]["document_offset"],
        })
    zone_reader.finish()

    samples = []
    for row in range(rows):
        for column in range(columns):
            cell = cells[row * 16 + column]
            refs = [zone["path"] for zone in cell["zones"]]
            samples.append({
                **cell, "pad": row * columns + column + 1,
                "row": row + 1, "column": column + 1,
                "type": "empty" if not refs else "sample" if len(refs) == 1 else "multisample",
                "path": refs[0] if refs else "", "paths": refs,
            })
    return {"kit": name, "rows": rows, "columns": columns, "samples": samples,
            "sample_table": paths, "zone_count": zone_count,
            "parser": "structured-v1", "format": "Battery 4 / path table 2"}
