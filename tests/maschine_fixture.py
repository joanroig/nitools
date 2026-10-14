"""Original synthetic Boost graph writer; contains no NI preset or sample data."""

import struct


def portable(value):
    size = (abs(value).bit_length() + 7) // 8
    return bytes([size if value >= 0 else 256 - size]) + abs(value).to_bytes(
        size, "little"
    )


def text(value):
    raw = value.encode("utf-8")
    return portable(len(raw)) + raw


class Writer:
    def __init__(self, legacy=False, empty_zone=False, override=False):
        self.data = bytearray(
            text("serialization::archive") + portable(10 if legacy else 17) + b"\0"
        )
        self.classes = {}
        self.registered = set()
        self.ident = 0
        self.slot = -1
        self.zone = 0
        self.group_name = False
        self.empty_zone = empty_zone
        self.override = override
        self.legacy = legacy
        self.zone_counts = []
        self.versions = {}

    def integer(self, n=0):
        self.data.extend(portable(n))

    def string(self, s=""):
        self.data.extend(text(s))

    def fields(self, names):
        for name in names.split():
            self.obj(name)

    def pointer(self, name, null=False, dynamic=False):
        if dynamic and name not in self.classes:
            self.integer(len(self.classes))
            self.string("NI::MASCHINE::DATA::" + name)
        else:
            self.classes.setdefault(name, len(self.classes))
            self.integer(-1 if null else self.classes[name])
        if not null:
            self.obj(name)

    def obj(self, name):
        self.classes.setdefault(name, len(self.classes))
        version = {
            "Group": 9 if self.legacy else 22,
            "Sound": 6,
            "EventInput": 1,
            "AudioInput": 1,
            "AudioOutput": 1,
            "EventOutput": 1,
            "Zone": 2,
            "Sampler": 2,
            "Parameter": 0 if self.legacy else 1,
        }.get(name, 0)
        version = self.versions.get(name, version)
        if name not in self.registered:
            self.registered.add(name)
            self.integer(1)
            self.integer(version)
        self.integer(self.ident)
        self.ident += 1
        self.body(name)

    def body(self, n):
        if n == "Group":
            self.fields("ScopedContent EventInput")
            if self.legacy:
                self.obj("Bool")
            self.fields("Enum UInt Bool")
            if self.legacy:
                self.fields(
                    "AudioOutput Bool Float Float Bool AudioOutput Float Enum AudioOutput Float Enum Color"
                )
            self.fields("Bool Bool Bool UInt")
            if self.legacy:
                self.obj("UInt")
            self.fields("UInt Enum Sounds")
            self.group_name = True
            self.obj("MixingLayer" if self.legacy else "Track")
        elif n == "Content":
            self.integer(1)
            self.string("Test Library")
            self.string("Test Library")
            self.string()
            self.integer()
        elif n == "ScopedContent":
            self.pointer("Content")
        elif n in ("EventInput", "AudioInput", "AudioOutput", "EventOutput"):
            self.obj("MaschineParameter")
        elif n == "Parameter":
            if not self.legacy:
                self.string()
        elif n in ("MaschineParameter", "Module"):
            pass
        elif n == "Enum":
            self.obj("UInt")
        elif n in ("Float", "Double", "UInt", "Int", "Bool", "String"):
            self.obj(("Value" if n == "String" else "Numeric") + n)
            self.obj("MaschineParameter")
            if n in ("Float", "Double"):
                width = 4 if n == "Float" else 8
                self.data.extend(bytes(width * 2))
                self.integer(int(self.override))
                self.data.extend(bytes(width))
            elif n != "String":
                for _ in range(4):
                    self.integer()
        elif n.startswith("Numeric"):
            self.obj("Value" + n[7:])
        elif n.startswith("Value"):
            self.obj("Parameter")
            kind = n[5:]
            if kind in ("Float", "Double"):
                self.data.extend(bytes(4 if kind == "Float" else 8))
            elif kind == "String":
                self.string(
                    "Fixture"
                    if self.group_name
                    else ""
                    if self.slot == 1
                    else f"Sound {self.slot + 1}"
                )
            else:
                self.integer()
        elif n in ("Sounds", "Sequences") or n.startswith("Objects"):
            item = {"Sounds": "Sound", "Sequences": "Sequence"}.get(n, n[7:])
            self.obj("Vector" + item)
            self.pointer(item, null=True)
            self.obj("Set" + item)
        elif n.startswith("Vector"):
            item = n[6:]
            count = (
                16
                if item == "Sound"
                else int(self.slot in (0, 2))
                if item == "Slot"
                else (1 if self.slot == 0 else 2)
                if item == "Zone"
                else int(item == "Take" and "AudioModule" in self.versions)
            )
            if item == "Zone":
                self.zone_counts.append(len(self.data))
            self.integer(count)
            self.integer()
            for index in range(count):
                if item == "Sound":
                    self.slot = index
                if item == "Zone":
                    self.zone = index
                self.obj("Shared" + item)
        elif n.startswith("Set"):
            self.integer()
            self.integer()
        elif n.startswith("Shared"):
            self.pointer(
                "Sampler" if n == "SharedModule" else n[6:], dynamic=n == "SharedModule"
            )
        elif n == "Sound":
            self.fields(
                "ScopedContent EventInput EventInput Enum Bool AudioInput Float AudioOutput Bool Float Float Bool Bool AudioOutput Float Enum AudioOutput Float Enum EventOutput Enum Int UInt Enum Enum Enum Enum Color UInt UInt Double Bool MixingLayer Sequences ScopedSoundInfo2"
            )
        elif n == "Color":
            self.integer()
            self.integer()
        elif n == "Track":
            self.fields(
                "AudioOutput Bool Float Float Bool AudioOutput Float Enum AudioOutput Float Enum Color MixingLayer"
            )
        elif n == "MixingLayer":
            self.fields("UInt UInt String")
            if not self.group_name:
                self.fields(
                    "Float Enum Bool Bool Chain ObjectsModulator ObjectsMacroPage ObjectsMidiAutomator"
                )
        elif n == "Chain":
            self.obj("ObjectsSlot")
            if self.slot in (0, 2):
                self.obj("QuickBrowse")
        elif n == "Slot":
            self.fields("Bool SharedModule ScopedSoundInfo2")
        elif n == "ScopedSoundInfo2":
            self.pointer("SoundInfo2", null=True)
        elif n == "QuickBrowse":
            self.integer()
        elif n == "AudioModule":
            version = self.versions.get(n, 0)
            self.obj("Module")
            if version >= 4:
                self.obj("ObjectsTake")
            else:
                self.fields(
                    ("Float" if version < 2 else "QuantizedFloat") + " FileLocation"
                )
            if version:
                self.fields("Enum Float")
            if version > 2:
                self.fields("Float Float")
            if version >= 5:
                self.obj("Enum")
        elif n == "Take":
            self.fields("FileLocation QuantizedFloat")
            if self.versions.get(n, 0):
                self.fields("Range Range UInt UInt Double")
            if self.versions.get(n, 0) > 1:
                self.obj("QuickBrowse")
        elif n == "QuantizedFloat":
            self.obj("Float")
        elif n == "Sampler":
            self.fields(
                "Module ObjectsZone Enum ObjectsTake Enum Float Float Enum Enum Bool"
            )
            self.fields(
                " ".join(
                    ["Float"] * 6
                    + ["Enum"]
                    + ["Float"] * 13
                    + ["AHDSR", "AHDSR", "LFO"]
                )
            )
        elif n == "AHDSR":
            self.fields(" ".join(["Float"] * 9))
        elif n == "LFO":
            self.fields("Enum Float Float Enum Float Float Float Float")
        elif n == "Zone":
            self.fields(
                "FileLocation Range Range Bool UInt UInt UInt UInt Range Range Float Float Float UInt Double Range UInt QuickBrowse"
            )
        elif n == "FileLocation":
            empty = self.empty_zone and self.zone == 1
            self.integer(0 if empty else 2)
            self.string("" if empty else "Samples/Kick\u00a0é🥁.wav")
            if not empty:
                self.obj("AliasPath")
        elif n == "AliasPath":
            self.string("Q:/Original Library/")
            self.string("Test Library")
        elif n == "Range":
            self.fields("MaschineParameter RangeHelper RangeHelper")
        elif n == "RangeHelper":
            self.fields("NumericUInt MaschineParameter")
            for _ in range(4):
                self.integer()
        else:
            raise AssertionError(n)

    def build(self):
        self.obj("Group")
        archive = bytes(self.data)
        payload = (
            struct.pack("<IQI", 1, len(archive) + 4, len(archive)) + archive + bytes(16)
        )
        base = b"DSIN" + struct.pack("<IIIII", 1, 1, 1, 1, 1)
        header = b"DSIN" + struct.pack("<IIQ", 109, 1, len(base)) + base + payload
        return (
            struct.pack("<QI4sII", 48 + len(header), 1, b"hsin", 1, 0)
            + bytes(16)
            + struct.pack("<Q", len(header))
            + header
        )


def synthetic_archive(legacy=False, empty_zone=False, override=False):
    return Writer(legacy, empty_zone, override).build()
