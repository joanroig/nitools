"""Bounded readers for Audio takes and external instrument state in a Sound.

The synth's state stays opaque; its length-delimited VST chunk is passed to the
original installed plug-in. No audio DSP or preset parameters are emulated.
"""

import re
import struct

from formats.ni_container import FormatError


class Modules:
    def __init__(self, data, start, legacy=False):
        from formats.maschine import _uint, _text
        self.data = data
        self.legacy = legacy
        self.classes = {}
        self.take_class = None
        self.take_registered = False
        for match in re.finditer(rb'NI::MASCHINE::DATA::[A-Za-z0-9_:]+', data[start:]):
            at = start + match.start() - 2
            try:
                name, end = _text(data, at)
                cls, before = _uint(data, at - 2)
                tracking, end = _uint(data, end)
                version, end = _uint(data, end)
                ident, end = _uint(data, end)
                if before != at or tracking != 1 or cls in self.classes:
                    continue
                self.classes[cls] = (name.rsplit('::', 1)[-1], version, ident, at - 2, end)
            except FormatError:
                continue

    def first(self, sound, following):
        from formats.maschine import _encoded
        ident = sound.object_id + (18 if self.legacy else 23)
        for cls, (name, version, first_id, declaration, end) in self.classes.items():
            if first_id == ident and sound.end <= declaration < following.offset:
                return name, version, ident, end, True
            marker = _encoded(cls) + _encoded(ident)
            at = self.data.find(marker, sound.end, min(following.offset, sound.end + 512))
            if at >= 0:
                return name, version, ident, at + len(marker), False
        return None

    def audio(self, module, following, absolute_offset):
        from formats.maschine import _uint, _text, _ids, _encoded
        _, version, ident, at, first = module
        data = self.data[:following.offset]
        if self.legacy or version not in (3, 5, 6, 7, 8):
            raise FormatError(f'Unsupported Audio module version {version}')
        if first and data[at:at + 6] == bytes(6):
            at += 6  # All three Module base classes first registered here.
        elif first and data[at:at + 4] == bytes(4):
            at += 4
        if version == 3:
            if data[at:at + 3] == b'\x01\x01\0':
                at += 3
            at = _ids(data, at, ident + 1, 5)
            # Take v3 stored its timing properties before the FileLocation.
            override, at = _uint(data, at + 13)
            if override not in (0, 1):
                raise FormatError('Unsupported Audio timing property')
            at += 4
            if data[at:at + 2] == b'\0\0':
                at += 2
            kind, at = _uint(data, at)
            path, at = _text(data, at)
            root = library = ''
            if kind == 2:
                if data[at:at + 2] == b'\0\0':
                    at += 2
                root, at = _text(data, at)
                library, at = _text(data, at)
            if kind not in (0, 2) or not path:
                raise FormatError('Unsupported Audio v3 FileLocation')
            _ids(data, at, ident + 6, 5)
            return [dict(path=path, path_kind=kind, library_root=root, library=library,
                         object_id=ident, source_offset=absolute_offset + module[3])]
        count, at = _uint(data, at)
        item_version, at = _uint(data, at)
        if count > 1024 or item_version != 1:
            raise FormatError('Unsupported Audio take vector')
        if count == 0:
            return []
        if data[at:at + 3] == b'\0\x01\x01':
            at += 3
        cls, _ = _uint(data, at)
        if self.take_class is not None and cls != self.take_class:
            raise FormatError('Inconsistent Audio take class')
        self.take_class = cls
        references = []
        # A Take has a FileLocation followed by five consecutive tracked
        # properties. Ignore later pointers to the same Take (active take).
        cursor = at
        while cursor < following.offset:
            marker = data.find(_encoded(self.take_class), cursor, following.offset)
            if marker < 0:
                break
            cursor = marker + len(_encoded(self.take_class))
            try:
                obj, tail = _uint(data, cursor)
                registration = obj == 1
                if registration:
                    take_version, tail = _uint(data, tail)
                    obj, tail = _uint(data, tail)
                    if take_version not in (0, 1, 2) or self.take_registered:
                        continue
                    if data[tail:tail + 2] == b'\0\0':
                        tail += 2
                if not ident < obj < following.object_id:
                    continue
                kind, tail = _uint(data, tail)
                if kind not in (0, 2):
                    continue
                path, tail = _text(data, tail)
                root = library = ''
                if kind == 2:
                    if data[tail:tail + 2] == b'\0\0':
                        tail += 2
                    root, tail = _text(data, tail)
                    library, tail = _text(data, tail)
                    if not path:
                        raise FormatError('Empty Audio take path')
                if registration and data[tail:tail + 3] == b'\x01\x01\0':
                    tail += 3
                tail = _ids(data, tail, obj + 1, 5)
            except FormatError:
                continue
            if obj in {ref['object_id'] for ref in references}:
                continue
            references.append(dict(path=path, path_kind=kind, library_root=root,
                                   library=library, object_id=obj,
                                   source_offset=absolute_offset + marker))
            self.take_registered = True
            cursor = tail
        if len(references) != count:
            raise FormatError(f'Audio take vector declares {count} references, decoded {len(references)}')
        return references

    def instrument(self, module, following, include_state=False):
        from formats.maschine import _uint, _text, _ids
        name, version, ident, at, first = module
        data = self.data[:following.offset]
        result = {'module': name, 'module_version': version}
        if name != 'PluginHost':
            if name not in {'Kick', 'Snare', 'Hihat', 'Tom', 'Cymbal', 'Perc', 'BassSynth', 'PolySynth'}:
                return None  # An effect or audio-input slot is not a synth.
            result['render_support'] = 'requires_maschine'
            return result
        try:
            if version != 1:
                raise FormatError('Unsupported PluginHost layout')
            properties = 3 if self.legacy else 4
            for prop in range(4):
                at = _ids(data, at, ident + 1 + prop * properties, properties)
                for _ in range(5 if self.legacy else 6):
                    _, at = _uint(data, at)
            plugin_id, at = _text(data, at)
            plugin_name, at = _text(data, at)
            result.update(plugin_id=plugin_id, name=plugin_name)
            # First serialized binary-data vector registers its base class.
            if data[at:at + 2] == b'\0\0':
                at += 2
            size, at = _uint(data, at)
            end = at + size
            if size < 12 or end > following.offset:
                raise FormatError('Invalid instrument state length')
            state_version, is_chunk, chunk_size = struct.unpack_from('<III', data, at)
            if state_version != 1 or is_chunk != 1 or chunk_size != size - 12:
                raise FormatError('Unsupported instrument state encoding')
            match = re.fullmatch(r'.+:VST:INSTR:(\d+)', plugin_id)
            if not match or not 0 < int(match[1]) < 2**32:
                raise FormatError('Instrument is not a VST2 chunk preset')
            result.update(render_support='vst2', vst_id=int(match[1]), state_size=chunk_size)
            if include_state:
                result['state'] = data[at + 12:end]
        except FormatError as exc:
            result.update(render_support='unsupported', reason=str(exc))
        return result
