"""Minimal offline VST2 instrument host. Run ONLY inside a disposable process.

Uses the public VST2.4 ABI (cdecl, 8-byte struct packing), no NI private APIs.
Only the primary stereo output is captured; effects and Maschine routing are
not reproduced. DLLs and licensed content are supplied by the user.
"""

import ctypes as C
from pathlib import Path

import numpy as np
import soundfile as sf

I, P, L, F = C.c_int32, C.c_void_p, C.c_ssize_t, C.c_float


class Effect(C.Structure):
    pass


EP = C.POINTER(Effect)
Dispatch = C.CFUNCTYPE(L, EP, I, I, L, P, F)
Process = C.CFUNCTYPE(None, EP, C.POINTER(C.POINTER(F)), C.POINTER(C.POINTER(F)), I)
Effect._fields_ = [
    ('magic', I), ('dispatcher', Dispatch), ('process', P), ('setParameter', P),
    ('getParameter', P), ('numPrograms', I), ('numParams', I), ('numInputs', I),
    ('numOutputs', I), ('flags', I), ('reserved1', L), ('reserved2', L),
    ('initialDelay', I), ('realQualities', I), ('offQualities', I), ('ioRatio', F),
    ('object', P), ('user', P), ('uniqueID', I), ('version', I),
    ('processReplacing', Process), ('processDoubleReplacing', P), ('future', C.c_char * 56),
]


class Midi(C.Structure):
    _fields_ = [(name, I) for name in ('type', 'byteSize', 'deltaFrames', 'flags', 'noteLength', 'noteOffset')] + [
        ('midiData', C.c_ubyte * 4), ('detune', C.c_byte), ('noteOffVelocity', C.c_ubyte),
        ('reserved1', C.c_ubyte), ('reserved2', C.c_ubyte),
    ]


class Events(C.Structure):
    _fields_ = [('numEvents', I), ('reserved', L), ('events', P * 2)]


class TimeInfo(C.Structure):
    _fields_ = [(name, C.c_double) for name in (
        'samplePos', 'sampleRate', 'nanoSeconds', 'ppqPos', 'tempo', 'barStartPos', 'cycleStartPos', 'cycleEndPos',
    )] + [(name, I) for name in (
        'timeSigNumerator', 'timeSigDenominator', 'smpteOffset', 'smpteFrameRate', 'samplesToNextClock', 'flags',
    )]


def render(dll_path, state, expected_id, output, *, note=60, velocity=100,
           hold=1.0, tail=2.0, sample_rate=48000):
    from utils.plugin_host import prepare_plugin_host
    prepare_plugin_host()
    block = 512
    timing = TimeInfo(sampleRate=sample_rate, tempo=120, timeSigNumerator=4,
                      timeSigDenominator=4, flags=(1 << 10) | (1 << 9) | (1 << 13))
    directory = C.create_string_buffer(str(Path(dll_path).parent).encode('mbcs'))

    @Dispatch
    def host(effect, opcode, index, value, pointer, option):
        if opcode == 1:  # audioMasterVersion
            return 2400
        if opcode == 7:
            return C.addressof(timing)
        if opcode == 16:
            return sample_rate
        if opcode == 17:
            return block
        if opcode == 22:
            return 1  # replacing, not accumulating
        if opcode == 23:
            return 4  # offline processing
        if opcode in (32, 33) and pointer:
            C.memmove(pointer, b'NITools\0', 8)
            return 1
        if opcode == 34:
            return 1000
        if opcode == 37 and pointer:
            return int(C.string_at(pointer) in (
                b'sendVstEvents', b'sendVstMidiEvent', b'sendVstMidiEvents', b'startStopProcess',
            ))
        if opcode == 41:
            return C.addressof(directory)
        if opcode == 42:
            return 1
        return 0

    # Keep DLL, callback and all pointed-to arrays alive until effClose.
    dll = C.CDLL(str(dll_path))
    entry = getattr(dll, 'VSTPluginMain', None) or getattr(dll, 'main', None)
    if entry is None:
        raise ValueError('DLL has no VST2 entry point')
    entry.restype, entry.argtypes = EP, [Dispatch]
    pointer = entry(host)
    if not pointer or pointer.contents.magic != 0x56737450:
        raise ValueError('DLL is not a VST2 plug-in')
    effect = pointer.contents

    def call(opcode, index=0, value=0, ptr=None, opt=0):
        return effect.dispatcher(pointer, opcode, index, value, ptr, opt)

    call(0)
    active = False
    try:
        if effect.uniqueID & 0xffffffff != expected_id:
            raise ValueError(f'Installed plug-in ID does not match saved instrument ({expected_id})')
        if not effect.flags & (1 << 8) or not effect.flags & (1 << 5):
            raise ValueError('Plug-in is not a chunk-based VST2 instrument')
        if not effect.processReplacing:
            raise ValueError('Plug-in does not support float audio processing')
        call(10, opt=sample_rate)
        call(11, value=block)
        def current_state():
            chunk = P()
            size = call(23, index=1, ptr=C.byref(chunk))
            if not chunk or not 0 < size <= 128 * 1024 * 1024:
                return b''
            return C.string_at(chunk, size)

        previous = current_state()
        state_buffer = C.create_string_buffer(state)
        call(24, index=1, value=len(state), ptr=C.cast(state_buffer, P))
        # effSetChunk may return zero even on success (VST specification).
        # Require a readable state plus finite, non-silent output below.
        restored = current_state()
        if not restored:
            raise ValueError('Plug-in did not expose a restored state')
        if restored == previous and state != previous:
            raise ValueError('Plug-in state did not change; the saved preset may have been rejected')
        call(12, value=1)
        active = True
        call(71)
        if not 0 <= effect.numInputs <= 64 or not 1 <= effect.numOutputs <= 64:
            raise ValueError('Unsupported plug-in channel count')
        latency = effect.initialDelay
        if not 0 <= latency <= sample_rate * 10:
            raise ValueError('Unsupported plug-in latency')
        inputs = np.zeros((effect.numInputs, block), np.float32)
        outputs = np.zeros((effect.numOutputs, block), np.float32)
        inp = (C.POINTER(F) * len(inputs))(*[v.ctypes.data_as(C.POINTER(F)) for v in inputs])
        out = (C.POINTER(F) * len(outputs))(*[v.ctypes.data_as(C.POINTER(F)) for v in outputs])

        midi_buffers = []

        def midi(status, offset):
            event = Midi(type=1, byteSize=C.sizeof(Midi), deltaFrames=offset,
                         midiData=(C.c_ubyte * 4)(status, note, velocity if status == 0x90 else 0, 0))
            events = Events(numEvents=1, events=(P * 2)(C.addressof(event), 0))
            midi_buffers.append((event, events))  # Valid until this audio block finishes.
            call(25, ptr=C.byref(events))

        warmup = block * 2
        duration = round((hold + tail) * sample_rate)
        note_off = warmup + round(hold * sample_rate)
        total = warmup + latency + duration
        audio = []
        for start in range(0, total, block):
            if start <= warmup < start + block:
                midi(0x90, warmup - start)
            if start <= note_off < start + block:
                midi(0x80, note_off - start)
            outputs.fill(0)
            effect.processReplacing(pointer, inp, out, block)
            midi_buffers.clear()
            audio.append(outputs[:2].T.copy())
            timing.samplePos += block
            timing.ppqPos = timing.samplePos / sample_rate * 2
        result = np.concatenate(audio)[warmup + latency:warmup + latency + duration]
        if not np.isfinite(result).all():
            raise ValueError('Instrument produced invalid audio')
        if float(np.max(np.abs(result))) < 1e-7:
            raise ValueError('Instrument produced silence; check its content, activation and MIDI note')
        sf.write(output, result, sample_rate, subtype='FLOAT')
    finally:
        if active:
            call(72)
            call(12, value=0)
        call(1)


def render_job(connection, dll_path, state, expected_id, output, options):
    """Top-level spawn target; native crashes cannot terminate the exporter."""
    try:
        render(dll_path, state, expected_id, output, **options)
        connection.send(None)
    except Exception as exc:
        connection.send(f'{type(exc).__name__}: {exc}')
    finally:
        connection.close()
