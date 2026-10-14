"""Exercise real GUI workers without changing the user's saved configuration."""

import json
import importlib
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6 import QtCore, QtGui, QtWidgets

from apps import groups_exporter_gui, kits_exporter_gui, previews_exporter_gui
from models.config import Config
from components import exporter_workflow
from components.progress_dialog import ProgressDialog
from processors import audio_export
from utils.enums import Style


class ExporterGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def wait_for_worker(self, worker):
        loop = QtCore.QEventLoop()
        timeout = QtCore.QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        timeout.start(10000)
        poll = QtCore.QTimer()
        poll.timeout.connect(lambda: loop.quit() if not worker.isRunning() else None)
        poll.start(10)
        loop.exec()
        poll.stop()
        timeout.stop()
        self.assertTrue(worker.wait(1000), "Export worker timed out")
        self.app.processEvents()

    def test_instrument_settings_round_trip_and_preparation_dialog_geometry(self):
        from components.prepare_maschine_dialog import PrepareMaschineDialog
        from models.render_options import RenderOptions
        config = Config()
        config.groups_exporter.instrument_render = RenderOptions(
            enabled=True, native_enabled=True, note=53, velocity=97, hold=0.75,
            tail=4.25, maschine_plugin='Q:/Maschine 3.vst3', cache_folder='Q:/cache',
            auto_prepare=False, prepare_timeout=210)
        with patch.object(groups_exporter_gui.config_utils, 'load_config', return_value=config), \
             patch.object(groups_exporter_gui.config_utils, 'save_config'):
            gui = groups_exporter_gui.GroupsExporterGUI()
            try:
                self.assertEqual(gui.render_instruments.isChecked(), sys.platform == 'win32')
                self.assertEqual(config.groups_exporter.instrument_render.enabled, sys.platform == 'win32')
                self.assertTrue(gui.render_maschine.isChecked())
                self.assertFalse(gui.auto_prepare.isChecked())
                self.assertEqual(gui.prepare_timeout.value(), 210)
                gui.auto_prepare.setChecked(True)
                gui.prepare_timeout.setValue(180)
                self.assertTrue(config.groups_exporter.instrument_render.auto_prepare)
                self.assertEqual(config.groups_exporter.instrument_render.prepare_timeout, 180)
                self.assertEqual(gui.render_note.value(), 53)
                self.assertEqual(gui.render_velocity.value(), 97)
                self.assertEqual(gui.render_tail.value(), 4.25)
                self.assertEqual(gui.maschine_plugin.text(), 'Q:/Maschine 3.vst3')
                gui.render_instruments.setChecked(False)
                self.assertFalse(gui.render_note.isEnabled())
                self.assertFalse(gui.native_settings.isHidden())
                self.assertEqual(config.groups_exporter.instrument_render.cache_folder, 'Q:/cache')
                gui.render_tail.setValue(2.5)
                self.assertEqual(config.groups_exporter.instrument_render.tail, 2.5)
                gui.render_maschine.setChecked(False)
                self.assertTrue(gui.render_settings.isHidden())
                dialog = PrepareMaschineDialog('Kit.mxgrp', config.groups_exporter.instrument_render, gui)
                dialog.show()
                self.app.processEvents()
                size = dialog.size()
                dialog.finish(False, 'A long validation error ' * 60)
                self.app.processEvents()
                self.assertEqual(dialog.size(), size)
                self.assertTrue(dialog.rect().contains(dialog.close_button.geometry()))
                dialog.reject()
                self.assertIsNone(dialog.process)
                from components.prepare_maschine_batch_dialog import PrepareMaschineBatchDialog
                batch = PrepareMaschineBatchDialog('index.json', config.groups_exporter.instrument_render, gui)
                batch.show()
                self.app.processEvents()
                size = batch.size()
                batch.on_progress(1, 5000, 'Preparing a very long kit name ' * 60)
                self.app.processEvents()
                self.assertEqual(batch.size(), size)
                self.assertTrue(batch.rect().contains(batch.close_button.geometry()))
                batch.reject()
            finally:
                gui.close()

    def test_progress_geometry_stays_fixed_and_cancel_waits_for_worker(self):
        parent = QtWidgets.QDialog()
        parent.resize(800, 700)
        parent.show()
        dialog = ProgressDialog('Scanning folders…', parent)
        cancellations = []
        dialog.canceled.connect(lambda: (cancellations.append(True), dialog.set_cancelling()))
        dialog.show()
        self.app.processEvents()
        initial = dialog.geometry()
        try:
            for message in ('0/5849 groups processed\nStarting decoder…',
                            '15/5849 groups processed — ' + 'Very long kit name ' * 70 + '\n15 decoded · 0 errors',
                            'Finished', 'Scanning folders\nD:/' + 'Long folder/' * 80):
                dialog.setLabelText(message)
                dialog.setRange(0, 5849)
                dialog.setValue(15)
                self.app.processEvents()
                self.assertEqual(dialog.geometry(), initial)
                self.assertEqual(dialog.label.toolTip(), message)
                self.assertTrue(dialog.rect().contains(dialog.label.geometry()))
                self.assertTrue(dialog.rect().contains(dialog.cancel_button.geometry()))
            dialog.move(initial.topLeft() + QtCore.QPoint(30, 40))
            moved = dialog.geometry()
            dialog.setLabelText('Short name')
            dialog.setValue(5848)
            self.app.processEvents()
            self.assertEqual(dialog.geometry(), moved)
            dialog.close()
            self.app.processEvents()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.cancel_button.isEnabled())
            self.assertEqual(len(cancellations), 1)
            dialog.reject()
            self.assertEqual(len(cancellations), 1)
            self.assertEqual(dialog.geometry(), moved)
        finally:
            dialog.done(0)
            parent.close()

    def test_advanced_options_keep_preferences_and_log_controls_work(self):
        for module, gui_class, kind in (
            (groups_exporter_gui, groups_exporter_gui.GroupsExporterGUI, 'groups'),
            (kits_exporter_gui, kits_exporter_gui.KitsExporterGUI, 'kits'),
            (previews_exporter_gui, previews_exporter_gui.PreviewsExporterGUI, 'previews'),
        ):
            with self.subTest(kind=kind), ExitStack() as stack:
                config = Config()
                prefs = getattr(config, kind + '_exporter')
                before = prefs.model_dump()
                stack.enter_context(patch.object(module.config_utils, 'load_config', return_value=config))
                stack.enter_context(patch.object(module.config_utils, 'save_config'))
                stack.enter_context(patch.object(module, 'apply_style'))
                gui = gui_class()
                gui.show()
                gui.tabs.setCurrentIndex(1)
                self.app.processEvents()
                loaded = prefs.model_dump()  # Existing loading normalizes path separators.
                try:
                    options = gui.advanced_options
                    activity = gui.activity_panel
                    self.assertIs(activity.pages.currentWidget(), activity.empty)
                    self.assertFalse(activity.copy_button.isEnabled())
                    self.assertFalse(activity.clear_button.isEnabled())
                    self.assertFalse(activity.open_button.isEnabled())
                    checked = [switch.isChecked() for switch in options.switches]
                    self.assertFalse(options.content.isVisible())
                    self.assertIn(str(sum(checked)), options.toggle.text())
                    for _ in range(2):
                        options.toggle.click()
                        self.app.processEvents()
                    self.assertFalse(options.content.isVisible())
                    self.assertEqual([switch.isChecked() for switch in options.switches], checked)
                    self.assertEqual(prefs.model_dump(), loaded)
                    gui.log_output.append('A <kit> & sample\nSecond line')
                    self.assertIn('A <kit> & sample\nSecond line', gui.log_output.toPlainText())
                    self.assertIs(activity.pages.currentWidget(), gui.log_output)
                    self.assertEqual(activity.count.text(), '1 message')
                    with patch.object(QtWidgets.QApplication, 'clipboard') as clipboard:
                        activity.copy_button.click()
                        clipboard.return_value.setText.assert_called_once_with(gui.log_output.toPlainText())
                    activity.set_status('Processing…', busy=True)
                    gui.log_output.append('Still processing')
                    self.assertFalse(activity.clear_button.isEnabled())
                    activity.set_status('Complete')
                    gui.clear_log_button.click()
                    self.assertEqual(gui.log_output.toPlainText(), '')
                    self.assertIs(activity.pages.currentWidget(), activity.empty)
                    for number in range(40):
                        gui.log_output.append(f'Earlier activity {number}')
                    self.app.processEvents()
                    scroll = gui.log_output.verticalScrollBar()
                    self.assertGreater(scroll.maximum(), 0)
                    scroll.setValue(0)
                    gui.log_output.append('New activity while reading earlier lines')
                    self.app.processEvents()
                    self.assertEqual(scroll.value(), 0)
                    self.assertFalse(activity.follow_button.isChecked())
                    activity.follow_button.click()
                    self.assertTrue(gui.log_output.follow_output)
                    self.assertEqual(scroll.value(), scroll.maximum())
                    cursor = gui.log_output.textCursor()
                    cursor.setPosition(0)
                    cursor.setPosition(7, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    gui.log_output.setTextCursor(cursor)
                    selection = gui.log_output.textCursor().selectedText()
                    gui.log_output.append('Selection should remain available to copy')
                    self.assertEqual(gui.log_output.textCursor().selectedText(), selection)
                    retained = gui.log_output.toPlainText()
                    retained_scroll = scroll.value()

                    def inspect_reader(dialog):
                        reader = dialog.findChild(QtWidgets.QTextEdit)
                        self.assertTrue(reader.isReadOnly())
                        self.assertIsNot(reader.document(), gui.log_output.document())
                        self.assertEqual(reader.toPlainText(), retained)
                        reader.resize(1200, 500)
                        return 0

                    with patch.object(QtWidgets.QDialog, 'exec', new=inspect_reader):
                        activity.open_button.click()
                    self.app.processEvents()
                    self.assertEqual(gui.log_output.toPlainText(), retained)
                    self.assertEqual(scroll.value(), retained_scroll)
                    gui.bottom_banner.show_terminal_button.click()
                    self.assertFalse(gui.activity_panel.isVisible())
                    gui.bottom_banner.show_terminal_button.click()
                    self.assertTrue(gui.activity_panel.isVisible())
                    self.assertEqual(gui.sample_rate.currentData(), before['sample_rate'])
                    self.assertEqual(gui.bit_depth.currentData(), before['bit_depth'])
                finally:
                    gui.close()

    def test_saved_large_log_cannot_clip_export_settings(self):
        # Reproduce the owner's 800x749 window and pre-redesign splitter sizes,
        # using the real stylesheet instead of mocking away its layout costs.
        previous_font = self.app.font()
        previous_stylesheet = self.app.styleSheet()
        for font in ('segoeui.ttf', 'segoeuib.ttf'):
            path = Path('C:/Windows/Fonts') / font
            if path.exists():
                QtGui.QFontDatabase.addApplicationFont(str(path))
        self.app.setFont(QtGui.QFont('Segoe UI', 9))
        try:
            for module, gui_class, kind in (
                (groups_exporter_gui, groups_exporter_gui.GroupsExporterGUI, 'groups'),
                (kits_exporter_gui, kits_exporter_gui.KitsExporterGUI, 'kits'),
                (previews_exporter_gui, previews_exporter_gui.PreviewsExporterGUI, 'previews'),
            ):
                for saved_sizes in ([302, 422], [10, 1000]):
                    with self.subTest(kind=kind, sizes=saved_sizes), ExitStack() as stack:
                        config = Config(style=Style.DARK, log_panel_sizes=saved_sizes)
                        prefs = getattr(config, kind + '_exporter')
                        prefs.width, prefs.height = 800, 749
                        stack.enter_context(patch.object(module.config_utils, 'load_config', return_value=config))
                        stack.enter_context(patch.object(module.config_utils, 'save_config'))
                        stack.enter_context(patch('utils.style_utils.load_config', return_value=config))
                        gui = gui_class()
                        gui.show()
                        gui.tabs.setCurrentIndex(1)
                        self.app.processEvents()
                        scroll = gui.tab_export.findChild(QtWidgets.QScrollArea)
                        splitter = gui.findChild(QtWidgets.QSplitter)
                        try:
                            for size in ((800, 749), (1200, 900), (800, 600), (800, 749)):
                                gui.resize(*size)
                                self.app.processEvents()
                                self.assertEqual((gui.width(), gui.height()), size)
                                self.assertLessEqual(gui.activity_panel.height(), max(96, splitter.height() // 4))
                                self.assertGreaterEqual(gui.activity_panel.height(), 96)
                                if size[1] >= 749:
                                    self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
                                    for widget in (gui.trim_silence, gui.normalize, gui.skip_existing,
                                                   gui.sample_rate, gui.bit_depth, gui.advanced_options.toggle):
                                        top_left = widget.mapTo(scroll.viewport(), QtCore.QPoint())
                                        self.assertTrue(scroll.viewport().rect().contains(
                                            QtCore.QRect(top_left, widget.size())), widget.objectName() or widget.__class__.__name__)
                            gui.advanced_options.toggle.click()
                            self.app.processEvents()
                            self.assertTrue(gui.advanced_options.content.isVisible())
                            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
                            self.assertTrue(gui.run_process_btn.isVisible())
                            gui.advanced_options.toggle.click()
                            gui.bottom_banner.show_terminal_button.click()
                            self.app.processEvents()
                            self.assertFalse(gui.activity_panel.isVisible())
                            gui.bottom_banner.show_terminal_button.click()
                            self.app.processEvents()
                            self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
                            self.assertLessEqual(gui.activity_panel.height(), max(96, splitter.height() // 4))
                        finally:
                            gui.close()
        finally:
            self.app.setFont(previous_font)
            self.app.setStyleSheet(previous_stylesheet)

    def test_all_builders_show_live_progress_keep_destination_and_cancel_safely(self):
        for module, gui_class, kind, extension, target in (
            (kits_exporter_gui, kits_exporter_gui.KitsExporterGUI, 'kits', 'nbkt', 'process_nbkt_file'),
            (groups_exporter_gui, groups_exporter_gui.GroupsExporterGUI, 'groups', 'mxgrp', 'process_mxgrp_file'),
            (previews_exporter_gui, previews_exporter_gui.PreviewsExporterGUI, 'previews', 'ogg', 'collect_samples_from_path'),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                source = root / 'input'
                source.mkdir()
                (source / ('Test.' + extension)).write_bytes(b'fixture')
                config = Config()
                stack.enter_context(patch.object(module.config_utils, 'load_config', return_value=config))
                stack.enter_context(patch.object(module.config_utils, 'save_config'))
                stack.enter_context(patch.object(module, 'apply_style'))
                info = stack.enter_context(patch.object(exporter_workflow.QMessageBox, 'information'))
                stack.enter_context(patch.object(QtWidgets.QApplication, 'beep'))
                error = stack.enter_context(patch.object(exporter_workflow, 'ErrorDialog'))
                complete = stack.enter_context(patch.object(exporter_workflow, 'show_export_complete_dialog'))
                builder_module = importlib.import_module(f'processors.{kind}.build_{kind}_json')
                if kind == 'previews':
                    stack.enter_context(patch.object(builder_module, 'get_ni_content_paths', return_value=[('Test', source)]))
                gui = gui_class()
                try:
                    if hasattr(gui, 'input_folder'):
                        gui.input_folder.setText(str(source))
                    gui.output_folder.setText(str(root / 'index'))
                    chosen = str(root / 'My exports')
                    gui.proc_output_folder.setText(chosen)
                    for cancel in (False, True):
                        entered, release = threading.Event(), threading.Event()

                        def build(*args, **kwargs):
                            entered.set()
                            if not release.wait(5):
                                raise TimeoutError('No GUI progress delivered during parsing')
                            record = {'instrument': 'Test', 'ogg_path': str(source / 'Test.ogg'), 'wav_name': 'Test.wav'}
                            return [record] if kind == 'previews' else {'samples': [], 'parser': 'structured-v1'}

                        with patch.object(builder_module, target, side_effect=build):
                            gui.tabs.setCurrentIndex(0)
                            gui.run_build_json()
                            worker = gui.worker
                            try:
                                loop = QtCore.QEventLoop()
                                poll = QtCore.QTimer()
                                poll.timeout.connect(lambda: loop.quit() if entered.is_set() and gui.progress_dialog.maximum() == 1 else None)
                                poll.start(10)
                                QtCore.QTimer.singleShot(3000, loop.quit)
                                loop.exec()
                                poll.stop()
                                self.assertTrue(worker.isRunning())
                                self.assertEqual(gui.progress_dialog.maximum(), 1)
                                self.assertEqual(gui.progress_dialog.value(), 0)
                                self.assertEqual(gui.proc_output_folder.text(), chosen)
                                self.assertFalse(gui.tabs.isEnabled())
                                if cancel:
                                    gui.cancel_worker()
                                    self.assertIs(gui.worker, worker)
                                    self.assertFalse(gui.run_build_btn.isEnabled())
                            finally:
                                release.set()
                                self.wait_for_worker(worker)
                        self.assertTrue(gui.run_build_btn.isEnabled())
                        self.assertEqual(gui.proc_output_folder.text(), chosen)
                    self.assertEqual(error.call_count, 0)
                    self.assertEqual(complete.call_count, 0)
                    self.assertEqual(info.call_count, 2)
                    self.assertEqual(info.call_args.args[1], 'Process Cancelled')
                finally:
                    gui.close()
                    self.app.processEvents()

    def test_exact_missing_reference_produces_error_not_success_or_cancellation(self):
        for module, gui_class, kind, config_key in (
            (kits_exporter_gui, kits_exporter_gui.KitsExporterGUI, "kit", "kits_exporter"),
            (groups_exporter_gui, groups_exporter_gui.GroupsExporterGUI, "group", "groups_exporter"),
            (previews_exporter_gui, previews_exporter_gui.PreviewsExporterGUI, "preview", "previews_exporter"),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "Samples").mkdir()
                (root / "Samples" / "Kick.wav").write_bytes(b"sample copied without conversion")
                index = root / "index.json"
                record = {kind: "Test", "parser": "structured-v1", "path": str(root), "samples": [{"pad": 3, "type": "sample", "path": "Samples/Kick.wav"}]}
                if kind == 'preview':
                    record = {'instrument': 'Test', 'ogg_path': str(root / 'Samples/Kick.wav'), 'wav_name': 'Kick.wav'}
                config = Config()
                prefs = getattr(config, config_key)
                for key, value in {
                    "trim_silence": False, "normalize": False, "sample_rate": "",
                    "bit_depth": "", "enable_matrix": False, "filter_pads": False,
                    "include_preview": False, "skip_existing": False,
                }.items():
                    if hasattr(prefs, key):
                        setattr(prefs, key, value)
                if kind == "group":
                    prefs.fill_blanks = False
                with (
                    patch.object(module.config_utils, "load_config", return_value=config),
                    patch.object(module.config_utils, "save_config"),
                    patch.object(module, "apply_style"),
                    patch.object(exporter_workflow, "show_export_complete_dialog") as complete,
                    patch.object(exporter_workflow, "ErrorDialog") as error,
                    patch.object(module.QMessageBox, "information") as information,
                    patch.object(module.QMessageBox, "warning"),
                    patch.object(QtWidgets.QApplication, "beep"),
                ):
                    gui = gui_class()
                    try:
                        gui.json_path.setText(str(index))
                        gui.proc_output_folder.setText(str(root / "output"))
                        gui.tabs.setCurrentIndex(1)
                        for missing in (False, True):
                            if missing:
                                if kind == 'preview':
                                    record['ogg_path'] = str(root / 'Samples/Missing.wav')
                                else:
                                    record["samples"][0]["path"] = "Samples/Missing.wav"
                            index.write_text(json.dumps([record]), encoding="utf-8")
                            entered, release = threading.Event(), threading.Event()
                            original_copy = audio_export.shutil.copy2

                            def blocked_copy(*args):
                                entered.set()
                                if not release.wait(5):
                                    raise TimeoutError("Progress was not delivered while export was running")
                                return original_copy(*args)

                            with patch.object(audio_export.shutil, "copy2", side_effect=blocked_copy):
                                try:
                                    gui.run_process_py()
                                    if not missing:
                                        loop = QtCore.QEventLoop()
                                        poll = QtCore.QTimer()
                                        poll.timeout.connect(lambda: loop.quit() if entered.is_set() and "Exporting" in gui.log_output.toPlainText() and gui.progress_dialog.maximum() == 1 else None)
                                        poll.start(10)
                                        QtCore.QTimer.singleShot(3000, loop.quit)
                                        loop.exec()
                                        poll.stop()
                                        self.assertTrue(gui.worker.isRunning())
                                        self.assertIn("[1/1] Exporting", gui.log_output.toPlainText())
                                        self.assertEqual(gui.progress_dialog.maximum(), 1)
                                        self.assertEqual(gui.progress_dialog.value(), 0)
                                        self.assertIn("Test", gui.progress_dialog.labelText())
                                finally:
                                    release.set()
                                    self.wait_for_worker(gui.worker)
                            self.assertEqual(complete.call_count, 1)
                            self.assertEqual(error.call_count, int(missing))
                        self.assertEqual(information.call_count, 0, "Export was misreported as cancellation")
                        self.assertIn("1 unresolved paths", gui.log_output.toPlainText())
                        if kind == "kit":
                            self.assertFalse(hasattr(gui, "replace_missing"))
                    finally:
                        gui.close()
                        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
