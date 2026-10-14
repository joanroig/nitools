"""Decode kit names, sample locations and instrument states from archive objects."""

import struct

from formats.maschine_schema import MaschineArchive
from formats.ni_container import FormatError, read_container

SYNTHS = {"Kick", "Snare", "Hihat", "Tom", "Cymbal", "Perc", "BassSynth", "PolySynth"}


def unbox(node):
    """Unwrap typed parameter and shared-pointer records."""
    while isinstance(node, dict) and "type" in node:
        node = node["value"]
    return node


def instrument_info(module, include_state=False):
    name = module["type"]
    if name not in SYNTHS | {"PluginHost"}:
        return None
    result = dict(
        module=name,
        module_version=module["version"],
        render_support="requires_maschine",
    )
    if name != "PluginHost":
        return result
    identity, preset, chunk = module["value"]
    result.update(plugin_id=identity, name=preset)
    blob = chunk["value"]
    parts = identity.rsplit(":", 3)
    if len(blob) < 12 or struct.unpack_from("<III", blob) != (1, 1, len(blob) - 12):
        result.update(
            render_support="unsupported", reason="Unsupported instrument state encoding"
        )
    elif (
        len(parts) != 4
        or parts[1:3] != ["VST", "INSTR"]
        or not parts[3].isascii()
        or not parts[3].isdigit()
        or not 0 < int(parts[3]) < 2**32
    ):
        result.update(
            render_support="unsupported", reason="Instrument is not a VST2 chunk preset"
        )
    else:
        result.update(
            render_support="vst2", vst_id=int(parts[3]), state_size=len(blob) - 12
        )
        if include_state:
            result["state"] = blob[12:]
    return result


def sample_references(module, base):
    locations = module["value"]
    if locations["type"] == "FileLocation":
        entries = [(module, locations)]  # Older Audio modules have one location.
    else:
        entries = [
            (shared["value"], shared["value"]["value"]) for shared in locations["value"]
        ]
    references = []
    for zone, location in entries:
        kind, path, alias = location["value"]
        library_root, library = alias["value"] if alias else ("", "")
        references.append(
            dict(
                path=path,
                path_kind=kind,
                library_root=library_root,
                library=library,
                object_id=zone["id"],
                source_offset=base + zone["offset"],
            )
        )
    return references


def project(archive, base=0, include_state=False):
    reader = MaschineArchive(archive)
    root = reader.obj("Group")
    data = root["value"]
    content = unbox(data["content"])
    samples = []
    for pad, shared in enumerate(data["sounds"]["value"], 1):
        mixing = unbox(shared["value"])
        slots = unbox(mixing["chain"])
        # Slot -> SharedModule -> concrete module; effects later in the chain
        # are consumed by the schema but do not own the pad's sample map.
        module = slots[0]["value"]["value"]["value"] if slots else None
        references = []
        instrument = None
        audio = False
        if module:
            if module["type"] in ("Sampler", "AudioModule"):
                audio = module["type"] == "AudioModule"
                references = sample_references(module, base)
            else:
                instrument = instrument_info(module, include_state)
        paths = [ref["path"] for ref in references if ref["path"]]
        samples.append(
            dict(
                pad=pad,
                name=unbox(mixing["name"]),
                type="sample"
                if len(paths) == 1
                else "multisample"
                if paths
                else "no_sample",
                paths=paths,
                sample_references=references,
                empty_zones=sum(not ref["path"] for ref in references),
                source_offset=base + mixing["name"]["offset"],
                status="samples" if paths else "no_sample_reference",
                **({"instrument": instrument} if instrument else {}),
                **({"sample_module": "Audio"} if audio else {}),
            )
        )
    return dict(
        group=unbox(unbox(data["group"])["name"]),
        expansion=content[0] if content else "",
        samples=samples,
        parser="structured-v1",
        source="Maschine",
        format_details=dict(
            format="maschine-portable-archive",
            archive_version=reader.version,
            group_version=root["version"],
            library_identifier=content[1] if content else "",
            sample_mode="raw",
            sound_slots=16,
            zone_parameters="not_decoded",
            decoder="sequential-boost-v2",
        ),
    )


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
    if (
        version != 1
        or stored_size + 28 != len(payload)
        or archive_size + 4 != stored_size
    ):
        raise FormatError("Unsupported Maschine archive compression or length")
    return project(
        payload[16 : 16 + archive_size], header.offset + 16, include_plugin_state
    )
