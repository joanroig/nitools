"""Sequential Maschine kit schemas recovered from native archive loaders.

Readers follow field order and class versions; unknown layouts fail closed.
Effects are consumed as parameter records, without implementing their DSP.
The kit projection ends after the Group name: later Group patterns/effects
are outside the sample-export projection and are not scanned or interpreted.
"""

import struct
from formats.portable_archive import PortableArchive

SIMPLE_FIELDS = {
    "AudioInputModule": ["Module", "Float"],
    "EQ": ["Module"] + ["Float"] * 11,
    "Chorus": ["Module"] + ["Float"] * 3,
    "TransientDesigner": ["Module"] + ["Float"] * 3 + ["Bool"],
    "Metaverb": ["Module"] + ["Float"] * 5,
    "Maximizer": ["Module", "Float", "Float", "Bool", "SideChainFilter"],
    "Saturator": ["Module", "Enum"] + ["Float"] * 11 + ["Bool", "Bool"],
    "Filter": ["Module", "Enum"]
    + ["Float"] * 3
    + ["Enum"]
    + ["Float"] * 6
    + ["SideChainFilter"],
    "GrainDelay": ["Module"] + ["Float"] * 3 + ["Bool"] + ["Float"] * 5,
    "Reverb": ["Module", "Enum"] + ["Float"] * 6 + ["Bool"],
    "SideChainFilter": ["SideChainInput"] + ["Float"] * 3 + ["Bool"],
}
SIMPLE_FIELDS.update(
    {
        "Iceverb": ["Module"] + ["Float"] * 4,
        "Reflex": ["Module"] + ["Float"] * 4,
        "FM": ["Module"] + ["Float"] * 4,
        "LoFi": ["Module"] + ["Float"] * 5,
        "FreqShifter": ["Module"] + ["Float"] * 4 + ["Bool", "Float"],
        "CabinetEmulation": ["Module", "Enum", "Enum", "Float", "Float"],
        "Gate": ["Module"] + ["Float"] * 5 + ["SideChainFilter"],
        "Phaser": ["Module", "Float", "Float", "Enum"]
        + ["Float"] * 4
        + ["Bool", "Float"],
    }
)
SIMPLE_FIELDS.update(
    {
        "PolySynth": [
            "Module",
            "Float",
            "Float",
            "Bool",
            "Bool",
            "Bool",
            "Int",
            "Bool",
            "Bool",
            "Float",
            "Bool",
            "Int",
            "Float",
            "Bool",
            "Bool",
            "Bool",
            "Float",
            "Bool",
            "Bool",
            "Float",
            "Float",
            "Float",
            "Float",
            "Float",
            "Float",
            "Float",
            "Float",
            "Bool",
            "Float",
            "Float",
            "Float",
            "Float",
            "Enum",
            "Float",
            "Bool",
            "Bool",
            "Bool",
            "Float",
            "Float",
            "Bool",
            "Bool",
            "Bool",
            "Bool",
            "Bool",
            "Float",
            "Float",
            "Float",
            "Float",
            "Float",
            "Bool",
            "Bool",
            "Bool",
            "Bool",
            "Enum",
            "Float",
            "Float",
            "Float",
            "Int",
            "Enum",
            "Enum",
        ],
        "Cymbal": ["Module", "Enum"] + ["Float"] * 7 + ["Enum"] + ["Float"] * 4,
        "GrainStretch": [
            "Module",
            "Bool",
            "Float",
            "Enum",
            "Float",
            "Bool",
            "Float",
            "Float",
        ],
        "Resochord": ["Module", "Enum", "Enum", "Enum", "Float", "Int"] + ["Float"] * 4,
    }
)

VERSIONS = {
    "Group": (1, 2, 4, 9, 13, 14, 15, 16, 18, 19, 20, 22, 23),
    "Sound": tuple(range(10)),
    "Parameter": (0, 1),
    "MixingLayer": (0, 1),
    "Track": (0, 1),
    "Sampler": (0, 1, 2),
    "Zone": (0, 1, 2),
    "Take": (0, 1, 2),
    "AudioModule": tuple(range(8)),
    "EventInput": (0, 1, 2),
    "AudioInput": (0, 1, 2),
    "AudioOutput": (0, 1, 2),
    "EventOutput": (0, 1, 2),
    "SideChainInput": (0, 1, 2),
    "AudioInputValue": (0, 1, 2, 3),
    "AudioOutputValue": (0, 1, 2, 3),
    "EventOutputValue": (0, 1, 2, 3),
    "SideChainInputValue": (0, 1, 2),
    "TimedEvents": (0, 1, 2, 3),
    "AudioEvent": (0, 1),
    "PluginHost": (0, 1),
    "PluginParameter": (0, 1),
    "BassSynth": (0, 1),
    "Kick": (0, 1, 2),
    "Hihat": (0, 1, 2),
    "Snare": (0, 1),
    "Tom": (0, 1),
    "Perc": (0, 1),
    "Flanger": (0, 1),
    "MullhollandDrive": (0, 1),
    "Compressor": (0, 1),
    "Limiter": (0, 1),
    "PlateReverb": (0, 1),
}


class MaschineArchive(PortableArchive):
    def validate_version(self, name, version):
        allowed = (0, 1) if name.startswith("Shared") else VERSIONS.get(name, (0,))
        if version not in allowed:
            self.fail(f"Unsupported {name} schema version {version}")

    def body(self, name, v):
        method = READERS.get(name)
        if method is not None:
            return method(self, name, v)
        return self._read_family(name, v)

    def _read_basssynth(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Float", "Int"]
            + ["Float"] * 5
            + ["Bool" if v == 0 else "Int", "Float"]
        ]

    def _read_kick(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Enum"]
            + ["Float"] * 6
            + ["Enum"]
            + ["Float"] * 11
            + [
                "Enum",
                "Float",
                "Float",
                "Enum",
                "Float",
                "Float",
                "Enum",
                "Float",
                "Float",
            ]
            + (["Bool", "Float", "Float"] if v > 1 else [])
        ]

    def _read_hihat(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Enum"]
            + ["Float"] * 3
            + ["Bool"]
            + ["Float"] * 6
            + ["Enum", "Float"]
            + (["Float"] * 5 if v > 1 else [])
        ]

    def _read_snare(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Enum"]
            + ["Float"] * 5
            + ["Enum"]
            + ["Float"] * 4
            + ["Enum"]
            + ["Float"] * 5
            + ["Bool"]
            + ["Float"] * 4
        ]

    def _read_tom(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Enum"] + ["Float"] * 9 + ["Enum"] + ["Float"] * 12
        ]

    def _read_perc(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Enum"]
            + ["Float"] * 4
            + ["Enum"]
            + ["Float"] * 8
            + ["Bool", "Enum", "Float"]
            + (
                ["Float", "Enum", "Enum", "Float", "Float", "Enum", "Float", "Enum"]
                if v
                else []
            )
            + ["Float"] * 4
        ]

    def _read_flanger(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Float"]
            + (["Enum"] if v else [])
            + ["Float"] * 5
            + ["Bool", "Float"]
        ]

    def _read_mullhollanddrive(self, name, v):
        return [
            self.obj(f)
            for f in ["Module"]
            + (["Enum"] + ["Float"] * 3 + ["Bool", "Float", "Float"] if v else [])
            + ["Float"] * 5
            + ["Bool", "Float", "Float"]
        ]

    def _read_pluginhost(self, name, v):
        for f in ("Module", "Bool", "Bool", "Bool", "Bool"):
            self.obj(f)
        identity = self.text()
        preset = self.text()
        chunk = self.obj("PluginChunk")
        if v:
            self.integer(4)
        self.obj("PluginParameters")
        self.obj("PluginWindowHandler")
        return (identity, preset, chunk)

    def _read_pluginparameters(self, name, v):
        return [self.obj(f) for f in ("ObjectsPluginPage", "SideChainFilter")]

    def _read_pluginpage(self, name, v):
        self.obj("ParameterPage")
        return self.obj("PluginArray")

    def _read_pluginarray(self, name, v):
        count = self.integer()
        if not 0 <= count <= 8:
            self.fail("Invalid collection or object schema")
        return [self.obj("SharedPluginParameter") for _ in range(count)]

    def _read_pluginparameter(self, name, v):
        self.obj("Float")
        index = self.integer(4)
        label = self.text()
        if v:
            self.integer(1)
        return (index, label, self.text())

    def _read_track(self, name, v):
        for f in (
            "AudioOutput",
            "Bool",
            "Float",
            "Float",
            "Bool",
            "AudioOutput",
            "Float",
            "Enum",
            "AudioOutput",
            "Float",
            "Enum",
            "Color",
        ):
            self.obj(f)
        return self.obj("MixingLayer")

    def _read_legacyrouting(self, name, v):
        for f in (
            "AudioOutput",
            "Bool",
            "Float",
            "Float",
            "Bool",
            "AudioOutput",
            "Float",
        ):
            self.obj(f)
        self.obj("Enum" if v else "Bool")
        self.obj("AudioOutput")
        self.obj("Float")
        self.obj("Enum" if v else "Bool")
        self.obj("Color")
        return None

    def _read_compressor(self, name, v):
        return [
            self.obj(f)
            for f in ["Module"]
            + (["Enum"] if v else [])
            + ["Float"] * 6
            + ["SideChainFilter"]
        ]

    def _read_limiter(self, name, v):
        return [
            self.obj(f)
            for f in ["Module", "Float", "SideChainFilter"]
            + (["Enum", "Float", "Float"] if v else [])
        ]

    def _read_modulator(self, name, v):
        return self.dynamic()

    def _read_audiooutputvalue(self, name, v):
        kind = self.integer(4)
        index = self.integer()
        if v < 2:
            self.pointer("Group")
            self.pointer("Sound")
            self.pointer("Slot")
            self.integer()
        elif v == 2:
            for f in ("WeakGroup", "WeakSound", "WeakSlot"):
                self.obj(f)
        else:
            self.pointer("Sound")
            self.pointer("Slot")
        return (kind, index)

    def _read_valueaudiooutput(self, name, v):
        self.obj("Parameter")
        return self.obj(name[5:] + "Value")

    def _read_sidechaininputvalue(self, name, v):
        kind = self.integer(4)
        if v == 1:
            self.obj("WeakGroup")
            self.obj("WeakSound")
        else:
            self.pointer("Group")
            self.pointer("Sound")
        return kind

    def _read_eventoutputvalue(self, name, v):
        kind = self.integer(4)
        label = self.text()
        if v < 2:
            self.pointer("Group")
        if v == 2:
            self.obj("WeakSound")
            self.obj("WeakSlot")
        else:
            self.pointer("Sound")
            self.pointer("Slot")
        return (kind, label)

    def _read_parameterevent(self, name, v):
        return self.obj("Event")

    def _read_midievent(self, name, v):
        self.obj("Event")
        return (self.integer(4), self.integer(), self.integer())

    def _read_audioevent(self, name, v):
        self.obj("LengthEvent")
        return self.pointer("Take") if v else None

    def _read_timedevent(self, name, v):
        return (self.integer(), self.pointer("Event"))

    def _read_event(self, name, v):
        return self.integer(1)

    def _read_lengthevent(self, name, v):
        self.obj("Event")
        return self.integer()

    def _read_noteevent(self, name, v):
        self.obj("LengthEvent")
        return (self.integer(), self.integer())

    def _read_sequence(self, name, v):
        events = self.obj("TimedEvents")
        self.pointer("Event")
        return events

    def _read_eventversion(self, name, v):
        return None

    def _read_timedevents(self, name, v):
        count = self.count()
        if v >= 2:
            self.obj("EventVersion")
        for _ in range(count):
            self.obj("TimedEvent")
            self.obj("EventNode")
        self.obj("EventNode")
        if not self.pointer("EventNode") is None:
            self.fail("Unsupported nonempty event ordering tree")
        return None

    def _read_snapshotsmanager(self, name, v):
        return [
            self.obj(f)
            for f in (
                "ObjectMapSnapshot",
                "Bool",
                "Enum",
                "Enum",
                "Enum",
                "UInt",
                "UInt",
            )
        ]

    def _read_objectmapsnapshot(self, name, v):
        value = self.obj("MapSnapshot")
        self.pointer("Snapshot")
        return value

    def _read_mapsnapshot(self, name, v):
        count = self.integer()
        _item_version = self.integer()
        if count != 0:
            self.fail("Unsupported nonempty snapshot map")
        return []

    def _read_midiautomator(self, name, v):
        return [self.obj(f) for f in ("Enum", "UInt")]

    def _read_sequences(self, name, v):
        return self.body("ObjectsSequence", v)

    def _read_macropage(self, name, v):
        self.obj("ParameterPage")
        return self.obj("ForwardArray")

    def _read_parameterpage(self, name, v):
        return self.obj("String")

    def _read_forwardarray(self, name, v):
        count = self.integer()
        if not 0 <= count <= 8:
            self.fail("Invalid collection or object schema")
        return [self.obj("SharedForwardParameter") for _ in range(count)]

    def _read_forwardparameter(self, name, v):
        self.obj("MaschineParameter")
        ref = self.dynamic()
        return (ref, self.text(), self.text())

    def _read_chain(self, name, v):
        slots = self.obj("ObjectsSlot")
        for slot in slots["value"]:
            self.obj("QuickBrowse")
        return slots

    def _read_quickbrowse(self, name, v):
        return self.take(self.integer(4))

    def _read_slot(self, name, v):
        self.obj("Bool")
        module = self.obj("SharedModule")
        self.obj("ScopedSoundInfo2")
        return module

    def _read_sharedmodule(self, name, v):
        return self.dynamic()

    def _read_module(self, name, v):
        return None

    def _read_beatdelay(self, name, v):
        return [
            self.obj(f) for f in ["Module", "Enum", "Enum"] + ["Float"] * 6 + ["Enum"]
        ]

    def _read_platereverb(self, name, v):
        self.obj("Module")
        for _ in range(5):
            self.obj("Float")
        if v:
            self.obj("Enum")
            for _ in range(17):
                self.obj("Float")
        return None

    def _read_quantizedfloat(self, name, v):
        return self.obj("Float")

    def _read_take(self, name, v):
        location = self.obj("FileLocation")
        self.obj("QuantizedFloat")
        if v:
            for f in ("Range", "Range", "UInt", "UInt", "Double"):
                self.obj(f)
        if v > 1:
            self.obj("QuickBrowse")
        return location

    def _read_audiomodule(self, name, v):
        self.obj("Module")
        if v >= 4:
            locations = self.obj("ObjectsTake")
        else:
            self.obj("Float" if v < 2 else "QuantizedFloat")
            locations = self.obj("FileLocation")
        if v:
            self.obj("Enum")
            self.obj("Float")
        if v > 2:
            self.obj("Float")
            self.obj("Float")
        if v >= 5:
            self.obj("Enum")
        return locations

    def _read_sampler(self, name, v):
        self.obj("Module")
        zones = self.obj("ObjectsZone")
        if v:
            self.obj("Enum")
        if v > 1:
            self.obj("ObjectsTake")
        for f in (
            ["Enum", "Float", "Float", "Enum", "Enum", "Bool"]
            + ["Float"] * 6
            + ["Enum"]
            + ["Float"] * 13
            + ["AHDSR", "AHDSR", "LFO"]
        ):
            self.obj(f)
        return zones

    def _read_ahdsr(self, name, v):
        return [self.obj("Float") for _ in range(9)]

    def _read_lfo(self, name, v):
        return [
            self.obj(f)
            for f in (
                "Enum",
                "Float",
                "Float",
                "Enum",
                "Float",
                "Float",
                "Float",
                "Float",
            )
        ]

    def _read_zone(self, name, v):
        location = self.obj("FileLocation")
        for f in (
            "Range",
            "Range",
            "Bool",
            "UInt",
            "UInt",
            "UInt",
            "UInt",
            "Range",
            "Range",
            "Float",
            "Float",
            "Float",
            "UInt",
            "Double",
            "Range",
        ):
            self.obj(f)
        if v:
            self.obj("UInt")
        self.obj("QuickBrowse" if v > 1 else "ScopedQuickBrowse")
        return location

    def _read_filelocation(self, name, v):
        kind = self.integer(4)
        path = self.text()
        return (kind, path, self.obj("AliasPath") if kind else None)

    def _read_aliaspath(self, name, v):
        return (self.text(), self.text())

    def _read_range(self, name, v):
        return [
            self.obj(f) for f in ("MaschineParameter", "RangeHelper", "RangeHelper")
        ]

    def _read_rangehelper(self, name, v):
        self.obj("NumericUInt")
        self.obj("MaschineParameter")
        return [self.integer() for _ in range(4)]

    def _read_group(self, name, v):
        content = self.obj("ScopedContent")
        self.obj("EventInput")
        if v < 19:
            self.obj("Bool")
        self.obj("Enum")
        self.obj("UInt")
        if v > 4:
            self.obj("Bool")
        if v < 13:
            self.body("LegacyRouting", v)
        self.obj("Bool")
        self.obj("Bool")
        self.obj("Bool")
        if v in (10, 11):
            self.obj("Bool")
        self.obj("UInt")
        if v < 13:
            self.obj("UInt")
        self.obj("UInt")
        if v >= 4:
            self.obj("Enum")
        elif v == 3:
            self.obj("UInt")
        sounds = self.obj("Sounds")
        self.group_projection = True
        group = self.obj("MixingLayer" if v < 13 else "Track")
        return dict(content=content, sounds=sounds, group=group)

    def _read_sound(self, name, v):
        self.obj("ScopedContent")
        self.obj("EventInput")
        self.obj("EventInput" if v >= 6 else "Bool")
        self.obj("Enum")
        if v > 3:
            self.obj("Bool")
        for field in (
            "AudioInput",
            "Float",
            "AudioOutput",
            "Bool",
            "Float",
            "Float",
            "Bool",
            "Bool",
            "AudioOutput",
            "Float",
        ):
            self.obj(field)
        self.obj("Enum" if v else "Bool")
        self.obj("AudioOutput")
        self.obj("Float")
        self.obj("Enum" if v else "Bool")
        for field in (
            "EventOutput",
            "Enum",
            "Int",
            "UInt",
            "Enum",
            "Enum",
            "Enum",
            "Enum",
            "Color",
            "UInt",
            "UInt",
            "Double",
        ):
            self.obj(field)
        if v > 6:
            self.obj("UInt")
        self.obj("Bool")
        if v > 7:
            self.obj("MidiMacro")
        mixing = self.obj("MixingLayer")
        self.obj("Sequences")
        self.obj("ScopedSoundInfo2")
        return mixing

    def _read_midimacro(self, name, v):
        return [self.obj("Int") for _ in range(130)]

    def _read_mixinglayer(self, name, v):
        self.obj("UInt")
        self.obj("UInt")
        name_value = self.obj("String")
        if getattr(self, "group_projection", False):
            return dict(name=name_value, chain=None)
        for field in ("Float", "Enum", "Bool", "Bool"):
            self.obj(field)
        chain = self.obj("Chain")
        for f in ("ObjectsModulator", "ObjectsMacroPage", "ObjectsMidiAutomator"):
            self.obj(f)
        if v:
            self.obj("SnapshotsManager")
        return dict(name=name_value, chain=chain)

    def _read_color(self, name, v):
        return (self.integer(), self.integer(1))

    def _read_sounds(self, name, v):
        return self.body("ObjectsSound", v)

    def _read_vectorsound(self, name, v):
        count = self.integer()
        _item_version = self.integer()
        if count != 16:
            self.fail(f"Expected 16 Sounds, found {count}")
        return [self.obj("SharedSound") for _ in range(count)]

    def _read_sharedsound(self, name, v):
        return self.pointer("Sound")

    def _read_scopedcontent(self, name, v):
        return self.pointer("Content")

    def _read_content(self, name, v):
        return (
            [self.text(), self.text(), self.text(), self.integer(4)]
            if self.integer(1)
            else None
        )

    def _read_eventinput(self, name, v):
        omit = self.integer(1) if v >= 2 else v >= 1
        if not omit:
            self.obj("ValueString" if name == "EventInput" else "Value" + name)
        return self.obj("MaschineParameter")

    def _read_parameter(self, name, v):
        return self.text() if v else None

    def _read_maschineparameter(self, name, v):
        return None

    def _read_enum(self, name, v):
        return self.obj("UInt")

    def _read_family(self, name, v):
        parameter = PARAMETER_TYPES.get(name)
        if parameter is not None:
            return self._read_typed_parameter(*parameter)
        if name in SIMPLE_FIELDS:
            return [self.obj(f) for f in SIMPLE_FIELDS[name]]
        if name.startswith("Weak"):
            return self.obj("Shared" + name[4:])
        if name.endswith("ModulationEvent"):
            kind = name[:-15]
            self.obj("ParameterEvent")
            self.pointer(kind)
            return (
                self.take(4 if kind == "Float" else 8)
                if kind in ("Float", "Double")
                else self.integer()
            )
        if name.startswith("Scoped") and name != "ScopedContent":
            return self.pointer(name[6:])
        if name.startswith("Objects"):
            item = name[7:]
            values = self.obj("Vector" + item)
            self.pointer(item)
            self.obj("Set" + item)
            return values["value"]
        if name.startswith("Vector"):
            item = name[6:]
            count = self.integer()
            _item_version = self.integer()
            if not 0 <= count < 100000:
                self.fail("Invalid collection or object schema")
            return [self.obj("Shared" + item) for _ in range(count)]
        if name.startswith("Set"):
            item = name[3:]
            count = self.integer()
            _item_version = self.integer()
            if not 0 <= count < 100000:
                self.fail("Invalid collection or object schema")
            return [self.pointer(item) for _ in range(count)]
        if name.startswith("Shared"):
            return self.pointer(name[6:])
        self.fail(f"Unsupported object schema {name} version {v}")

    def _read_typed_parameter(self, suffix, kind, layer):
        if layer == "Value":
            self.obj("Parameter")
            if kind in ("M", "N"):
                return struct.unpack(
                    "<f" if kind == "M" else "<d", self.take(4 if kind == "M" else 8)
                )[0]
            return (
                self.text() if kind == "S" else self.integer(1 if kind == "_N" else 8)
            )
        if layer == "Numeric":
            return self.obj("Value" + suffix)
        value = self.obj(("Value" if kind == "S" else "Numeric") + suffix)
        self.obj("MaschineParameter")
        if kind in ("M", "N"):
            self.take(8 if kind == "M" else 16)
            self.integer(1)
            self.take(4 if kind == "M" else 8)
        elif kind != "S":
            for _ in range(4):
                self.integer(1 if kind == "_N" else 8)
        return value


PARAMETER_TYPES = {
    layer + suffix: (suffix, kind, layer)
    for suffix, kind in (
        ("UInt", "_K"),
        ("Bool", "_N"),
        ("Float", "M"),
        ("String", "S"),
        ("Int", "H"),
        ("Double", "N"),
    )
    for layer in ("", "Value", "Numeric")
}


READERS = {
    "BassSynth": MaschineArchive._read_basssynth,
    "Kick": MaschineArchive._read_kick,
    "Hihat": MaschineArchive._read_hihat,
    "Snare": MaschineArchive._read_snare,
    "Tom": MaschineArchive._read_tom,
    "Perc": MaschineArchive._read_perc,
    "Flanger": MaschineArchive._read_flanger,
    "MullhollandDrive": MaschineArchive._read_mullhollanddrive,
    "PluginHost": MaschineArchive._read_pluginhost,
    "PluginParameters": MaschineArchive._read_pluginparameters,
    "PluginPage": MaschineArchive._read_pluginpage,
    "PluginArray": MaschineArchive._read_pluginarray,
    "PluginParameter": MaschineArchive._read_pluginparameter,
    "Track": MaschineArchive._read_track,
    "LegacyRouting": MaschineArchive._read_legacyrouting,
    "Compressor": MaschineArchive._read_compressor,
    "Limiter": MaschineArchive._read_limiter,
    "Modulator": MaschineArchive._read_modulator,
    "AudioOutputValue": MaschineArchive._read_audiooutputvalue,
    "AudioInputValue": MaschineArchive._read_audiooutputvalue,
    "ValueAudioOutput": MaschineArchive._read_valueaudiooutput,
    "ValueAudioInput": MaschineArchive._read_valueaudiooutput,
    "ValueEventOutput": MaschineArchive._read_valueaudiooutput,
    "ValueSideChainInput": MaschineArchive._read_valueaudiooutput,
    "SideChainInputValue": MaschineArchive._read_sidechaininputvalue,
    "EventOutputValue": MaschineArchive._read_eventoutputvalue,
    "ParameterEvent": MaschineArchive._read_parameterevent,
    "MidiEvent": MaschineArchive._read_midievent,
    "AudioEvent": MaschineArchive._read_audioevent,
    "TimedEvent": MaschineArchive._read_timedevent,
    "Event": MaschineArchive._read_event,
    "LengthEvent": MaschineArchive._read_lengthevent,
    "NoteEvent": MaschineArchive._read_noteevent,
    "Sequence": MaschineArchive._read_sequence,
    "EventVersion": MaschineArchive._read_eventversion,
    "EventNode": MaschineArchive._read_eventversion,
    "TimedEvents": MaschineArchive._read_timedevents,
    "SnapshotsManager": MaschineArchive._read_snapshotsmanager,
    "ObjectMapSnapshot": MaschineArchive._read_objectmapsnapshot,
    "MapSnapshot": MaschineArchive._read_mapsnapshot,
    "MidiAutomator": MaschineArchive._read_midiautomator,
    "Sequences": MaschineArchive._read_sequences,
    "MacroPage": MaschineArchive._read_macropage,
    "ParameterPage": MaschineArchive._read_parameterpage,
    "ForwardArray": MaschineArchive._read_forwardarray,
    "ForwardParameter": MaschineArchive._read_forwardparameter,
    "Chain": MaschineArchive._read_chain,
    "QuickBrowse": MaschineArchive._read_quickbrowse,
    "SoundInfo2": MaschineArchive._read_quickbrowse,
    "PluginChunk": MaschineArchive._read_quickbrowse,
    "PluginWindowHandler": MaschineArchive._read_quickbrowse,
    "Slot": MaschineArchive._read_slot,
    "SharedModule": MaschineArchive._read_sharedmodule,
    "Module": MaschineArchive._read_module,
    "BeatDelay": MaschineArchive._read_beatdelay,
    "PlateReverb": MaschineArchive._read_platereverb,
    "QuantizedFloat": MaschineArchive._read_quantizedfloat,
    "Take": MaschineArchive._read_take,
    "AudioModule": MaschineArchive._read_audiomodule,
    "Sampler": MaschineArchive._read_sampler,
    "AHDSR": MaschineArchive._read_ahdsr,
    "LFO": MaschineArchive._read_lfo,
    "Zone": MaschineArchive._read_zone,
    "FileLocation": MaschineArchive._read_filelocation,
    "AliasPath": MaschineArchive._read_aliaspath,
    "Range": MaschineArchive._read_range,
    "RangeHelper": MaschineArchive._read_rangehelper,
    "Group": MaschineArchive._read_group,
    "Sound": MaschineArchive._read_sound,
    "MidiMacro": MaschineArchive._read_midimacro,
    "MixingLayer": MaschineArchive._read_mixinglayer,
    "Color": MaschineArchive._read_color,
    "Sounds": MaschineArchive._read_sounds,
    "VectorSound": MaschineArchive._read_vectorsound,
    "SharedSound": MaschineArchive._read_sharedsound,
    "ScopedContent": MaschineArchive._read_scopedcontent,
    "Content": MaschineArchive._read_content,
    "EventInput": MaschineArchive._read_eventinput,
    "AudioInput": MaschineArchive._read_eventinput,
    "AudioOutput": MaschineArchive._read_eventinput,
    "EventOutput": MaschineArchive._read_eventinput,
    "SideChainInput": MaschineArchive._read_eventinput,
    "Parameter": MaschineArchive._read_parameter,
    "MaschineParameter": MaschineArchive._read_maschineparameter,
    "Enum": MaschineArchive._read_enum,
}
