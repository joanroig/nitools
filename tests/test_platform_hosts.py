"""Cross-platform host boundaries; native Cocoa checks run on the Mac CI jobs."""
from pathlib import Path
import plistlib
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hosts.maschine_macos import editor_view
from models.render_options import RenderOptions
from processors.instrument_render import InstrumentRenderer
from processors.maschine_render import cache_paths, plugin_path


class PlatformHostTests(unittest.TestCase):
    def test_mac_bundle_cache_tracks_executable_updates_and_architecture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plugin = root / 'Maschine 3.vst3'
            binary = plugin / 'Contents/MacOS/Maschine'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'version one')
            (plugin / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Maschine'}))
            source = root / 'Kit.mxgrp'
            source.write_bytes(b'synthetic kit')
            options = RenderOptions(maschine_plugin=str(plugin), cache_folder=str(root / 'cache'))
            with patch('processors.maschine_render.sys.platform', 'darwin'), patch('processors.maschine_render.platform.machine', return_value='arm64'):
                self.assertEqual(plugin_path(options), plugin.resolve())
                first = cache_paths(source, options)
                binary.write_bytes(b'changed version two')
                second = cache_paths(source, options)
                self.assertNotEqual(first, second)
                with patch('processors.maschine_render.platform.machine', return_value='x86_64'):
                    self.assertNotEqual(second, cache_paths(source, options))
                (plugin / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': '../escape'}))
                with self.assertRaisesRegex(ValueError, 'Invalid Maschine'):
                    plugin_path(options)

    def test_mac_rejects_windows_plugin_file(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = Path(folder) / 'Maschine 3.vst3'
            plugin.write_bytes(b'Windows DLL')
            with patch('processors.maschine_render.sys.platform', 'darwin'):
                with self.assertRaisesRegex(ValueError, 'not found'):
                    plugin_path(RenderOptions(maschine_plugin=str(plugin)))

    def test_mac_routes_external_instruments_through_maschine(self):
        with patch('processors.instrument_render.sys.platform', 'darwin'):
            host = InstrumentRenderer(RenderOptions(native_enabled=True))
            self.assertTrue(host.use_native({'render_support': 'vst2'}))
            self.assertEqual(host.plugins, {})
            with self.assertRaisesRegex(ValueError, 'Direct VST2'):
                InstrumentRenderer(RenderOptions(enabled=True))

    def test_dispatch_only_imports_selected_adapter(self):
        from processors.maschine_loader import load_kit
        adapter = SimpleNamespace(load_kit=Mock(return_value=b'verified'))
        with patch('processors.maschine_loader.sys.platform', 'darwin'), patch.dict(sys.modules, {'hosts.maschine_macos': adapter}):
            self.assertEqual(load_kit('host', 'kit', 30), b'verified')
        adapter.load_kit.assert_called_once_with('host', 'kit', 30)

    def test_editor_selection_rejects_ambiguity_hidden_views_and_sheets(self):
        window = Mock()
        view = Mock()
        view.isHiddenOrHasHiddenAncestor.return_value = False
        view.className.return_value = 'NI_QNSView'
        view.bounds.return_value = SimpleNamespace(size=SimpleNamespace(width=1200, height=700))
        view.subviews.return_value = []
        view.window.return_value = window
        window.isVisible.return_value = True
        window.contentView.return_value = view
        window.attachedSheet.return_value = None
        self.assertIs(editor_view([window]), view)
        with self.assertRaisesRegex(ValueError, 'one Maschine editor'):
            editor_view([window, window])
        view.isHiddenOrHasHiddenAncestor.return_value = True
        with self.assertRaises(ValueError):
            editor_view([window])
        view.isHiddenOrHasHiddenAncestor.return_value = False
        window.attachedSheet.return_value = object()
        with self.assertRaisesRegex(ValueError, 'dialog'):
            editor_view([window])

    @unittest.skipUnless(sys.platform == 'darwin', 'Requires the actual Cocoa bridge')
    def test_native_drag_info_signatures_and_private_pasteboard(self):
        from AppKit import NSMakePoint, NSPasteboard
        from hosts.maschine_macos import drag_info_class
        info = drag_info_class().alloc().init()
        board = NSPasteboard.pasteboardWithUniqueName()
        try:
            info.location = NSMakePoint(410, 155)
            info.pasteboard = board
            info.destination = None
            self.assertEqual(tuple(info.draggingLocation()), (410, 155))
            self.assertEqual(info.draggingSourceOperationMask(), 1)
            self.assertEqual(info.draggingPasteboard(), board)
        finally:
            board.releaseGlobally()
