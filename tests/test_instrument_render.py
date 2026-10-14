"""Synthetic format and process tests; no licensed presets are bundled."""

import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from formats.maschine_modules import Modules
from formats.maschine_project import build_vst3, project_archive_version, route_kit_preset, vst3_chunks
from formats.ni_container import FormatError, read_container
from models.render_options import RenderOptions
from processors.instrument_render import export_instrument
from processors.maschine_render import NativeSession, cache_paths, load_prepared, save_prepared
from test_maschine_format import archive_text, ids, portable


def project_preset(mode=(0, 0, 0, 1, 0, 0), version=20, sounds=16):
    archive = archive_text('serialization::archive') + portable(version)
    for slot in range(sounds + 2):
        ident = (slot + 1) * 1000
        name = f'Sound {slot + 1}' if slot < sounds else 'Kit' if slot == sounds else 'Master'
        archive += portable(ident) + b'\0' + archive_text(name)
        archive += ids(ident + 1, 4) + bytes(18) + ids(ident + 5, 5)
        if slot == sounds:
            routing = ident + 1000 - 28
            archive += ids(routing, 5) + b''.join(portable(v) for v in mode)
            archive += ids(routing + 5, 5) + bytes(6) + ids(routing + 10, 5) + bytes(6)
        archive += bytes(50)
    payload = struct.pack('<IQI', 1, len(archive) + 4, len(archive)) + archive + bytes(16)
    base = b'DSIN' + struct.pack('<IIIII', 1, 1, 1, 1, 1)
    header = b'DSIN' + struct.pack('<IIQ', 109, 1, len(base)) + base + payload
    def obj(h, children=b''):
        return struct.pack('<QI4sII', 48 + len(h) + len(children), 1, b'hsin', 1, 0) + bytes(16) + struct.pack('<Q', len(h)) + h + children
    component = obj(base, struct.pack('<I4sI', 1, b'2SAM', 1347571530) + obj(header))
    return build_vst3(b'A' * 32, [(b'Comp', component), (b'Cont', b'unchanged controller')])


def fake_native_job(connection, plugin, state, source=None, options=None):
    last_output = None
    if state == b'crash':
        os._exit(7)
    if state == b'slow':
        time.sleep(20)
    try:
        while True:
            request = connection.recv()
            if request is None:
                return
            pad, path, options = request
            last_output = Path(path)
            if state == b'pad_error' and pad == 12:
                connection.send('silent pad')
                continue
            Path(path).write_text(str(pad))
            connection.send(None)
    except EOFError:
        pass
    finally:
        if last_output is not None:
            last_output.with_suffix('.closed').write_text('clean')
        connection.close()


class InstrumentFormatTests(unittest.TestCase):
    def test_host_profile_comes_from_validated_project_archive(self):
        for version in (19, 20):
            self.assertEqual(project_archive_version(project_preset(version=version)), version)
        for preset in (b'invalid', project_preset(version=18), project_preset(version=21)):
            with self.assertRaises(ValueError):
                project_archive_version(preset)

    def test_audio_take_versions_keep_exact_unicode_paths_and_vector_count(self):
        for version in (5, 6, 7, 8):
            for take_version in (0, 1, 2):
                prefix = portable(1) + portable(1)
                take = (portable(40) + portable(1) + portable(take_version) + portable(124)
                        + bytes(2) + portable(2) + archive_text('Samples/é loop.wav')
                        + bytes(2) + archive_text('Q:/Library/') + archive_text('Library')
                        + b'\x01\x01\0' + ids(125, 5))
                data = prefix + take
                following = SimpleNamespace(offset=len(data), object_id=1000)
                refs = Modules(data, 0).audio(('Audio', version, 123, 0, False), following, 50)
                self.assertEqual(refs[0]['path'], 'Samples/é loop.wav')
                self.assertEqual(refs[0]['library_root'], 'Q:/Library/')
                self.assertEqual(refs[0]['source_offset'], 50 + len(prefix))
                bad = portable(2) + portable(1) + take
                with self.assertRaisesRegex(FormatError, 'declares 2 references'):
                    Modules(bad, 0).audio(('Audio', version, 123, 0, False), following, 0)
                with self.assertRaises(FormatError):
                    Modules(data, 0).audio(('Audio', version, 123, 0, False),
                        SimpleNamespace(offset=len(data)-2, object_id=1000), 0)

    def test_audio_v3_file_location_is_bounded(self):
        data = (ids(124, 5) + bytes(18) + portable(2) + archive_text('Samples/Loop.wav')
                + archive_text('Q:/Library/') + archive_text('Library') + ids(129, 5))
        boundary = SimpleNamespace(offset=len(data), object_id=1000)
        refs = Modules(data, 0).audio(('Audio', 3, 123, 0, False), boundary, 0)
        self.assertEqual(refs[0]['path'], 'Samples/Loop.wav')
        boundary.offset -= 2
        with self.assertRaises(FormatError):
            Modules(data, 0).audio(('Audio', 3, 123, 0, False), boundary, 0)

    def test_plugin_chunk_is_opt_in_and_cannot_cross_sound_boundary(self):
        for legacy in (False, True):
            width = 3 if legacy else 4
            props = b''.join(ids(124 + prop * width, width) + bytes(5 if legacy else 6) for prop in range(4))
            chunk = b'opaque saved preset'
            payload = struct.pack('<III', 1, 1, len(chunk)) + chunk
            data = props + archive_text('NI:VST:INSTR:123456') + archive_text('Synth') + portable(len(payload)) + payload
            boundary = SimpleNamespace(offset=len(data), object_id=1000)
            module = ('PluginHost', 1, 123, 0, False)
            reader = Modules(data, 0, legacy)
            self.assertNotIn('state', reader.instrument(module, boundary))
            self.assertEqual(reader.instrument(module, boundary, True)['state'], chunk)
            boundary.offset -= 1
            self.assertEqual(reader.instrument(module, boundary, True)['render_support'], 'unsupported')

    def test_effects_are_not_classified_as_instruments(self):
        reader = Modules(b'', 0)
        boundary = SimpleNamespace(offset=0, object_id=1000)
        self.assertIsNone(reader.instrument(('Reverb', 1, 10, 0, False), boundary))
        self.assertEqual(reader.instrument(('Tom', 1, 10, 0, False), boundary)['render_support'], 'requires_maschine')

    def test_routing_updates_container_lengths_and_is_idempotent(self):
        original = project_preset()
        names = [f'Sound {i}' for i in range(1, 17)]
        routed = route_kit_preset(original, names, 'Kit')
        self.assertNotEqual(original, routed)
        self.assertEqual(route_kit_preset(routed, names, 'Kit'), routed)
        _, chunks = vst3_chunks(routed)
        self.assertEqual(dict(chunks)[b'Cont'], b'unchanged controller')
        self.assertEqual(read_container(dict(chunks)[b'Comp']).size, len(dict(chunks)[b'Comp']))
        default_state = project_preset(mode=(0, 0, 0, 0, 0, 0))
        self.assertEqual(route_kit_preset(default_state, names, 'Kit'), routed)

    def test_maschine2_routing_preserves_version_and_controller(self):
        names = [f'Sound {i}' for i in range(1, 17)]
        original = project_preset(version=19)
        routed = route_kit_preset(original, names, 'Kit')
        self.assertNotEqual(original, routed)
        self.assertEqual(route_kit_preset(routed, names, 'Kit'), routed)
        self.assertEqual(routed, project_preset(version=19, mode=(0, 1, 1, 0, 0, 0)))
        with self.assertRaises(FormatError):
            route_kit_preset(project_preset(version=18), names, 'Kit')

    def test_wrong_kit_extra_group_unknown_version_and_routing_fail(self):
        names = [f'Sound {i}' for i in range(1, 17)]
        for data, expected, group in (
            (project_preset(), names, 'Wrong'),
            (project_preset(), ['Wrong'] + names[1:], 'Kit'),
            (project_preset(sounds=32), names, 'Kit'),
            (project_preset(version=21), names, 'Kit'),
            (project_preset(mode=(0, 2, 1, 0, 0, 0)), names, 'Kit'),
        ):
            with self.assertRaises(FormatError):
                route_kit_preset(data, expected, group)

    def test_vst3_rejects_truncation_overlap_and_duplicate_chunks(self):
        data = build_vst3(b'A'*32, [(b'Comp', bytes(20)), (b'Cont', bytes(20))])
        for damaged in (data[:20], data[:-1], build_vst3(b'A'*32, [(b'Comp', b'a'), (b'Comp', b'b')])):
            with self.assertRaises(FormatError):
                vst3_chunks(damaged)
        overlapping = bytearray(data)
        table = struct.unpack_from('<Q', data, 40)[0]
        struct.pack_into('<Q', overlapping, table + 8 + 20 + 4, 50)
        with self.assertRaisesRegex(FormatError, 'Overlapping'):
            vst3_chunks(overlapping)


class RenderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plugin = self.root/'Maschine 3.vst3'
        self.plugin_binary = self.plugin
        if sys.platform == 'darwin':
            import plistlib
            self.plugin_binary = self.plugin / 'Contents/MacOS/Maschine'
            self.plugin_binary.parent.mkdir(parents=True)
            (self.plugin / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Maschine'}))
        self.plugin_binary.write_bytes(b'plugin')
        self.source = self.root/'Kit.mxgrp'
        self.source.write_bytes(b'original source')
        self.options = RenderOptions(native_enabled=True, maschine_plugin=str(self.plugin), cache_folder=str(self.root/'cache'))

    def session(self, state=b'normal'):
        with patch('processors.maschine_render.load_prepared', return_value=state):
            session = NativeSession(self.source, self.options)
        self.addCleanup(session.close)
        return session

    def test_cache_rejects_tampering_and_invalidates_changed_source_or_plugin(self):
        decoded = dict(group='Kit', samples=[{'name': f'Sound {i}'} for i in range(1, 17)])
        with patch('processors.maschine_render.parse_maschine', return_value=decoded):
            path = save_prepared(self.source, project_preset(), self.options)
            self.assertEqual(load_prepared(self.source, self.options), path.read_bytes())
            path.write_bytes(path.read_bytes() + b'bad')
            with self.assertRaisesRegex(ValueError, 'damaged'):
                load_prepared(self.source, self.options)
            self.source.write_bytes(b'changed source')
            self.assertNotEqual(cache_paths(self.source, self.options)[0], path)
            path2 = cache_paths(self.source, self.options)[0]
            self.plugin_binary.write_bytes(b'updated plugin')
            self.assertNotEqual(cache_paths(self.source, self.options)[0], path2)
            with self.assertRaisesRegex(ValueError, 'not prepared'):
                load_prepared(self.source, self.options)

    def test_native_process_is_reused_and_closed(self):
        session = self.session()
        with patch('processors.maschine_render._native_job', fake_native_job):
            self.assertTrue(session.render(12, self.root/'one.wav', None))
            pid = session.process.pid
            self.assertTrue(session.render(16, self.root/'two.wav', None))
            self.assertEqual(pid, session.process.pid)
        self.assertEqual((self.root/'one.wav').read_text(), '12')
        self.assertEqual((self.root/'two.wav').read_text(), '16')
        session.close()
        self.assertEqual((self.root/'two.closed').read_text(), 'clean')
        self.assertIsNone(session.process)

    def test_native_crash_and_timeout_release_child(self):
        for state, exception in ((b'crash', (RuntimeError, EOFError)), (b'slow', TimeoutError)):
            self.options.timeout = 5 if state == b'crash' else 1
            session = self.session(state)
            with patch('processors.maschine_render._native_job', fake_native_job):
                with self.assertRaises(exception):
                    session.render(12, self.root/'failed.wav', None)
            self.assertTrue(session.failed)
            self.assertIsNone(session.process)
            self.assertIsNone(session.connection)

    def test_cancel_stops_native_child(self):
        session = self.session(b'slow')
        worker = Mock()
        worker.cancel_requested.side_effect = [False, True]
        with patch('processors.maschine_render._native_job', fake_native_job):
            self.assertFalse(session.render(12, self.root/'cancelled.wav', worker))
        self.assertIsNone(session.process)
        self.assertFalse((self.root/'cancelled.wav').exists())

    def test_pad_failure_does_not_discard_other_instruments(self):
        session = self.session(b'pad_error')
        with patch('processors.maschine_render._native_job', fake_native_job):
            with self.assertRaisesRegex(RuntimeError, 'silent pad'):
                session.render(12, self.root/'silent.wav', None)
            self.assertFalse(session.failed)
            self.assertTrue(session.render(13, self.root/'good.wav', None))
        self.assertEqual((self.root/'good.wav').read_text(), '13')

    def test_failed_and_skipped_renders_preserve_existing_output(self):
        target = self.root/'12_Tom.wav'
        target.write_bytes(b'previous export')
        exporter = SimpleNamespace(_worker=None, skip_existing=True, logger=Mock(), _current_name='Kit', _write_sample=Mock())
        renderer = Mock()
        sample = dict(pad=12, name='Tom', instrument={'module': 'Tom'})
        self.assertEqual(export_instrument(exporter, renderer, sample, target), 'skipped')
        renderer.render.assert_not_called()
        exporter.skip_existing = False
        renderer.render.side_effect = RuntimeError('host failed')
        self.assertEqual(export_instrument(exporter, renderer, sample, target), 'errors')
        self.assertEqual(target.read_bytes(), b'previous export')
        exporter._write_sample.assert_not_called()

    def test_render_options_reject_nonfinite_and_out_of_range_values(self):
        for values in (dict(note=128), dict(velocity=0), dict(hold=float('nan')), dict(tail=float('inf')), dict(timeout=0)):
            with self.assertRaises(ValueError):
                RenderOptions(**values)


if __name__ == '__main__':
    unittest.main()
