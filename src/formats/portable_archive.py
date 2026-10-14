"""Bounded sequential reader for NI's portable Boost archive framing.

Class IDs are assigned in registration order. Object IDs identify tracked
instances, including references to instances whose bodies are still loading.
Schema readers consume fields; this layer never searches for byte patterns.
"""

from formats.ni_container import FormatError


class PortableArchive:
    MAX_OBJECTS = 2_000_000
    MAX_COLLECTION = 100_000
    MAX_DEPTH = 128

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.classes = {}
        self.class_names = []
        self.objects = []
        self.depth = 0
        self.group_projection = False
        if self.text() != "serialization::archive":
            self.fail("Missing portable archive signature")
        self.version = self.integer(2)
        if self.version not in (10, 12, 13, 14, 15, 16, 17, 18, 19):
            self.fail(f"Unsupported Maschine archive version {self.version}")
        if self.integer(1) != 0:
            self.fail("Unsupported portable archive flags")

    def fail(self, message):
        raise FormatError(f"{message} at archive offset 0x{self.pos:x}")

    def take(self, size):
        if size < 0 or size > len(self.data) - self.pos:
            self.fail(f"Truncated archive field ({size} bytes)")
        start = self.pos
        self.pos += size
        return self.data[start : self.pos]

    def integer(self, width=8):
        # Most parameter values use zero or one byte. Decode them directly,
        # retaining the same width and truncation checks for every field.
        data, start = self.data, self.pos
        if start >= len(data):
            self.fail("Truncated portable integer")
        size = data[start]
        size = size if size < 128 else size - 256
        length = abs(size)
        if length > width:
            self.fail(f"Portable integer exceeds {width} bytes")
        end = start + 1 + length
        if end > len(data):
            self.fail("Truncated portable integer")
        self.pos = end
        if length == 0:
            return 0
        magnitude = (
            data[start + 1]
            if length == 1
            else int.from_bytes(data[start + 1 : end], "little")
        )
        return -magnitude if size < 0 else magnitude

    def text(self):
        size = self.integer()
        if not 0 <= size <= 1024 * 1024:
            self.fail("Invalid archive string length")
        try:
            return self.take(size).decode("utf-8")
        except UnicodeDecodeError as error:
            raise FormatError(f"Invalid archive UTF-8 at 0x{self.pos:x}") from error

    def count(self, limit=None):
        count = self.integer()
        if not 0 <= count <= (self.MAX_COLLECTION if limit is None else limit):
            self.fail(f"Invalid collection count {count}")
        return count

    def register(self, name):
        if name not in self.classes:
            if len(self.classes) >= 4096:
                self.fail("Too many archive classes")
            self.classes[name] = [len(self.class_names), None, None]
            self.class_names.append(name)
        return self.classes[name]

    def obj(self, name):
        start = self.pos
        cls = self.classes.get(name)
        if cls is None:
            cls = self.register(name)
        if cls[1] is None:
            cls[1], cls[2] = self.integer(1), self.integer(4)
            if cls[1] not in (0, 1):
                self.fail(f"Invalid tracking flag for {name}")
            self.validate_version(name, cls[2])
        tracking, version = cls[1], cls[2]
        ident = self.integer(4) if tracking else None
        if ident is not None:
            if not 0 <= ident <= len(self.objects):
                self.fail(f"Invalid {name} object reference {ident}")
            if ident < len(self.objects):
                result = self.objects[ident]
                if result["type"] != name:
                    self.fail(f"{name} references a {result['type']} object")
                return result
            if len(self.objects) >= self.MAX_OBJECTS:
                self.fail("Too many tracked objects")
        result = dict(
            type=name, offset=start, body_offset=self.pos, version=version, id=ident
        )
        if tracking:
            self.objects.append(result)
        if self.depth >= self.MAX_DEPTH:
            self.fail("Archive nesting limit exceeded")
        self.depth += 1
        try:
            result["value"] = self.body(name, version)
        finally:
            self.depth -= 1
        result["end"] = self.pos
        return result

    def pointer(self, name):
        self.register(name)
        return self._pointer()

    def dynamic(self):
        return self._pointer()

    def _pointer(self):
        cls = self.integer(2)
        if cls == -1:
            return None
        if not 0 <= cls <= len(self.class_names):
            self.fail(f"Invalid class reference {cls}")
        if cls == len(self.class_names):
            exported = self.text()
            prefix = "NI::MASCHINE::DATA::"
            if not exported.startswith(prefix):
                self.fail(f"Unsupported exported type {exported!r}")
            name = exported[len(prefix) :]
            if name in self.classes:
                self.fail(f"Duplicate exported class {name}")
        else:
            name = self.class_names[cls]
        return self.obj(name)

    def validate_version(self, name, version):
        raise NotImplementedError

    def body(self, name, version):
        raise NotImplementedError
