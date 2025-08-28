import json
import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox

from components.ansi_text_edit import AnsiTextEdit
from components.bottom_banner import BottomBanner
from components.resizable_log_splitter import ResizableLogSplitter
from dialogs.error_dialog import ErrorDialog
from dialogs.export_complete_dialog import show_export_complete_dialog
from models.config import Config
from processors.previews.build_previews_json import PreviewsJsonBuilder
from processors.previews.process_previews_json import PreviewsProcessor
from utils import config_utils
from utils.bundle_utils import get_bundled_path
from utils.utils import apply_style
from utils.worker_utils import WorkerThread


class PreviewsExporterGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("resources/icons/previews.png")))
        self.setWindowTitle('NITools - Previews Exporter')
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)  # Add minimum height
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.WindowMaximizeButtonHint)  # Allow maximizing
        self.config: Config = config_utils.load_config()
        apply_style(self.config.style)  # Apply style for standalone execution
        self.worker = None
        self.progress_dialog = None
        self.cancelled = False
        self.has_output = False
        self.last_built_json_path = None
        self.init_ui()
        self.load_config_to_ui()

        # Restore window size if saved
        if self.config.previews_exporter.width > 0 and self.config.previews_exporter.height > 0:
            self.resize(self.config.previews_exporter.width, self.config.previews_exporter.height)

        # Switch to export tab if json_path is already set
        if self.json_path.text().strip() and os.path.isfile(self.json_path.text().strip()):
            self.tabs.setCurrentIndex(1)

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget()

        # --- Tab 1: Process previews ---
        self.tab_process = QtWidgets.QWidget()
        build_layout = QtWidgets.QVBoxLayout()

        # Step 1 label
        step1_label = QtWidgets.QLabel("Step 1: Build JSON from Previews")
        step1_label.setStyleSheet("font-weight: bold;")
        build_layout.addWidget(step1_label)

        # Scrollable content
        scroll_content_build = QtWidgets.QWidget()
        build_form_layout = QtWidgets.QFormLayout(scroll_content_build)

        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder.setToolTip('Select the folder where the generated JSON file will be saved.')
        self.output_folder_btn = QtWidgets.QPushButton('Choose')
        self.output_folder_btn.setToolTip('Browse for the output folder.')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_form_layout.addRow('Output folder:', output_folder_layout)

        scroll_area_build = QtWidgets.QScrollArea()
        scroll_area_build.setWidgetResizable(True)
        scroll_area_build.setWidget(scroll_content_build)
        build_layout.addWidget(scroll_area_build)

        self.run_build_btn = QtWidgets.QPushButton('Process Previews')
        self.run_build_btn.clicked.connect(self.run_build_json)

        self.run_build_btn.setProperty("class", "accent")
        build_layout.addWidget(self.run_build_btn)

        self.tab_process.setLayout(build_layout)
        self.tabs.addTab(self.tab_process, 'Process Previews')

        # --- Tab 2: Export Previews ---
        self.tab_export = QtWidgets.QWidget()
        export_layout = QtWidgets.QVBoxLayout()

        # Step 2 label
        step2_label = QtWidgets.QLabel("Step 2: Export Previews")
        step2_label.setStyleSheet("font-weight: bold;")
        export_layout.addWidget(step2_label)

        # Scrollable content for Tab 2
        scroll_content_export = QtWidgets.QWidget()
        scroll_content_export_layout = QtWidgets.QVBoxLayout()

        export_form_layout = QtWidgets.QFormLayout()

        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip('Select the JSON file generated in Step 1 (e.g., all_previews.json).')
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.setToolTip('Browse for the JSON file.')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        export_form_layout.addRow('JSON file:', json_path_layout)

        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip('Select the folder where the processed preview samples will be exported.')
        self.proc_output_folder_btn = QtWidgets.QPushButton('Choose')
        self.proc_output_folder_btn.setToolTip('Browse for the output folder.')
        self.proc_output_folder_btn.clicked.connect(self.choose_proc_output_folder)
        proc_output_folder_layout = QtWidgets.QHBoxLayout()
        proc_output_folder_layout.addWidget(self.proc_output_folder)
        proc_output_folder_layout.addWidget(self.proc_output_folder_btn)
        export_form_layout.addRow('Output folder:', proc_output_folder_layout)

        # --- Options group ---
        options_group = QtWidgets.QGroupBox('Options')
        options_layout = QtWidgets.QVBoxLayout()
        self.skip_existing = QtWidgets.QCheckBox('Skip already processed')
        self.skip_existing.setToolTip('If checked, samples that already exist in the output folder will be skipped.')
        self.trim_silence = QtWidgets.QCheckBox('Trim silence')
        self.trim_silence.setToolTip('If checked, leading and trailing silence will be removed from samples.')
        self.normalize = QtWidgets.QCheckBox('Normalize')
        self.normalize.setToolTip('If checked, audio samples will be normalized to a standard loudness level.')
        self.sample_rate = QtWidgets.QLineEdit()
        self.sample_rate.setPlaceholderText('Sample rate (e.g. 48000)')
        self.sample_rate.setToolTip('Set the sample rate for exported audio (e.g., 44100, 48000). Leave blank for original.')
        self.bit_depth = QtWidgets.QLineEdit()
        self.bit_depth.setPlaceholderText('Bit depth (e.g. 16)')
        self.bit_depth.setToolTip('Set the bit depth for exported audio (e.g., 16, 24). Leave blank for original.')
        options_layout.addWidget(self.skip_existing)
        options_layout.addWidget(self.trim_silence)
        options_layout.addWidget(self.normalize)
        options_layout.addWidget(QtWidgets.QLabel('Sample rate:'))
        options_layout.addWidget(self.sample_rate)
        options_layout.addWidget(QtWidgets.QLabel('Bit depth:'))
        options_layout.addWidget(self.bit_depth)
        options_group.setLayout(options_layout)
        export_form_layout.addRow(options_group)

        # --- Skip Options group ---
        skip_content_group = QtWidgets.QGroupBox('Skip Content')
        skip_content_layout = QtWidgets.QVBoxLayout()
        self.skip_maschine_folders = QtWidgets.QCheckBox('Skip Maschine folders (.mxgrp)')
        self.skip_maschine_folders.setToolTip('If checked, folders containing .mxgrp files will be skipped.')
        self.skip_battery_kits = QtWidgets.QCheckBox('Skip Battery kits (.nbkt)')
        self.skip_battery_kits.setToolTip('If checked, files ending with .nbkt.ogg will be skipped.')
        self.skip_native_browser_preview_library = QtWidgets.QCheckBox("Skip 'Native Browser Preview Library' folder (it's huge!)")
        self.skip_native_browser_preview_library.setToolTip("If checked, previews from the 'Native Browser Preview Library' will be skipped completely.")
        self.find_real_instrument_folder = QtWidgets.QCheckBox("Find real instrument folder names for the 'Native Browser Preview Library'")
        self.find_real_instrument_folder.setToolTip('If checked, try to find the real instrument name for the "Native Browser Preview Library" previews.')
        skip_content_layout.addWidget(self.skip_maschine_folders)
        skip_content_layout.addWidget(self.skip_battery_kits)
        skip_content_layout.addWidget(self.skip_native_browser_preview_library)
        skip_content_layout.addWidget(self.find_real_instrument_folder)
        skip_content_group.setLayout(skip_content_layout)
        export_form_layout.addRow(skip_content_group)

        scroll_content_export_layout.addLayout(export_form_layout)

        scroll_content_export.setLayout(scroll_content_export_layout)
        scroll_area_process = QtWidgets.QScrollArea()
        scroll_area_process.setWidgetResizable(True)
        scroll_area_process.setWidget(scroll_content_export)
        export_layout.addWidget(scroll_area_process)

        self.run_process_btn = QtWidgets.QPushButton('Export Previews')
        self.run_process_btn.clicked.connect(self.run_process_py)
        self.run_process_btn.setProperty("class", "accent")
        export_layout.addWidget(self.run_process_btn)

        self.tab_export.setLayout(export_layout)
        self.tabs.addTab(self.tab_export, 'Export Previews')

        # --- Log/output ---
        self.log_output = AnsiTextEdit()
        self.log_output.setReadOnly(True)

        # Create a splitter to make the log_output resizable
        splitter = ResizableLogSplitter(self.config, self.tabs, self.log_output)
        main_layout.addWidget(splitter)

        # --- Bottom banner ---
        self.bottom_banner = BottomBanner(self.config.previews_exporter.show_terminal)
        self.bottom_banner.terminal_toggled.connect(self.toggle_terminal_visibility)
        main_layout.addWidget(self.bottom_banner)

        self.setLayout(main_layout)
        self.set_step2_enabled(False)
        self.json_path.textChanged.connect(self.on_json_path_changed)
        self.setup_config_signals()
        self.on_json_path_changed()  # Call once to set initial state based on json_path
        self.toggle_terminal_visibility(self.config.previews_exporter.show_terminal)

        self.skip_native_browser_preview_library.toggled.connect(self._update_find_real_instrument_folder_state)
        self._update_find_real_instrument_folder_state(self.skip_native_browser_preview_library.isChecked())

    def _update_find_real_instrument_folder_state(self, checked):
        self.find_real_instrument_folder.setEnabled(not checked)

    def closeEvent(self, event):
        # Save current window size to config
        self.config.previews_exporter.width = self.width()
        self.config.previews_exporter.height = self.height()
        config_utils.save_config(self.config)
        super().closeEvent(event)

    def toggle_terminal_visibility(self, state):
        self.log_output.setVisible(state)
        self.config.previews_exporter.show_terminal = state
        config_utils.save_config(self.config)

    def show_loading(self, message):
        self.cancelled = False
        self.progress_dialog = QtWidgets.QProgressDialog(message, 'Cancel', 0, 0, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setWindowTitle('Please wait')
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self.cancel_worker)
        self.progress_dialog.show()

    def hide_loading(self):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

    def cancel_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_cancel()  # Request cancellation
            self.cancelled = True
            self.worker = None  # Clear the worker reference
        else:
            self.run_build_btn.setEnabled(True)
            self.run_process_btn.setEnabled(True)
            self.hide_loading()

    def on_worker_output(self, text):
        self.log_output.append(text)
        self.has_output = True

    def on_subprocess_finished(self, code: int):
        # Hide the loading and make a sound
        self.hide_loading()
        QtWidgets.QApplication.instance().beep()

        # Determine current tab: 0 = Process, 1 = Export
        is_process_tab = (self.tabs.currentIndex() == 0)
        context = "Process" if is_process_tab else "Export"

        # Default log append
        self.log_output.append(f"{context} finished with code {code}\n")

        # --- Handle Cancel ---
        if self.cancelled or code == -1:
            self.log_output.append(f"{context} cancelled by user.\n")
            QMessageBox.information(self, f"{context} Cancelled", f"The {context.lower()} was cancelled.")

        # --- Handle Success ---
        elif code == 0:
            if not self.has_output:
                # Success but no output
                self.log_output.append(f"{context} finished with no output.\n")
                QMessageBox.warning(
                    self,
                    f"{context} Empty",
                    f"The {context.lower()} finished successfully but produced no output."
                )
            else:
                self.log_output.append("Done\n")

                if is_process_tab:
                    # Check if built JSON has previews
                    if self.last_built_json_path and os.path.exists(self.last_built_json_path):
                        try:
                            with open(self.last_built_json_path, 'r') as f:
                                data = json.load(f)
                                if isinstance(data, list) and len(data) == 0:
                                    # Empty JSON result
                                    self.log_output.append("0 previews processed.\n")
                                    QMessageBox.warning(self, "No Previews Processed", "The process completed but no previews were found or processed.")
                                else:
                                    # Success with previews
                                    self.tabs.setCurrentIndex(1)
                                    QMessageBox.information(self, "Process Complete", "Previews JSON file has been successfully built!")
                        except Exception as e:
                            # Unexpected JSON read error → still treat as success
                            self.log_output.append(f"Warning: Could not verify JSON file: {e}\n")
                            self.tabs.setCurrentIndex(1)
                            QMessageBox.information(self, "Process Complete", "Previews JSON file built, but verification failed. Proceed with caution.")
                    else:
                        # No JSON path set → treat as empty
                        QMessageBox.warning(self, "No Output JSON", "The process finished but no JSON file was found.")

                else:  # Export tab
                    show_export_complete_dialog(parent=self, output_folder=self.proc_output_folder.text().strip(), log_content=self.log_output.toPlainText(),
                                                title="Export Complete", message="Previews export process finished successfully.")

        # --- Handle Failure ---
        else:
            error_message = f"{context} failed with exit code {code}"
            self.log_output.append(error_message + "\n")

            full_log = self.log_output.toPlainText()
            log_lines = full_log.splitlines()
            detailed_error_text = "\n".join(log_lines[-20:])

            ErrorDialog(parent=self, title=f"{context} Failed", message=f"The {context.lower()} failed (exit code {code}). See details below.", detailed_text=detailed_error_text, icon=QMessageBox.Icon.Critical).exec()

        # Reset state
        self.run_build_btn.setEnabled(True)
        self.run_process_btn.setEnabled(True)
        self.cancelled = False

    def setup_config_signals(self):
        # Save config on change, the keys here should match the attribute names in PreviewsExporterConfig
        for widget, key in [
            (self.output_folder, 'output_folder'),
            (self.json_path, 'json_path'),
            (self.proc_output_folder, 'proc_output_folder'),
            (self.trim_silence, 'trim_silence'),
            (self.normalize, 'normalize'),
            (self.sample_rate, 'sample_rate'),
            (self.bit_depth, 'bit_depth'),
            (self.skip_existing, 'skip_existing'),
            (self.skip_maschine_folders, 'skip_maschine_folders'),
            (self.skip_battery_kits, 'skip_battery_kits'),
            (self.skip_native_browser_preview_library, 'skip_native_browser_preview_library'),
            (self.find_real_instrument_folder, 'find_real_instrument_folder'),
            (self.bottom_banner.show_terminal_button, 'show_terminal'),
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(lambda val, k=key: self.on_config_changed(k, val))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))
            elif isinstance(widget, QtWidgets.QPushButton) and widget.isCheckable():
                widget.toggled.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))

    def on_config_changed(self, key, value):
        # Update the specific attribute in the previews_exporter sub-model
        setattr(self.config.previews_exporter, key, value)
        config_utils.save_config(self.config)

    def load_config_to_ui(self):
        c = self.config.previews_exporter
        self.output_folder.setText(c.output_folder)
        self.json_path.setText(c.json_path)
        self.proc_output_folder.setText(c.proc_output_folder)
        self.trim_silence.setChecked(c.trim_silence)
        self.normalize.setChecked(c.normalize)
        self.sample_rate.setText(c.sample_rate)
        self.bit_depth.setText(c.bit_depth)
        self.skip_existing.setChecked(c.skip_existing)
        self.skip_maschine_folders.setChecked(c.skip_maschine_folders)
        self.skip_battery_kits.setChecked(c.skip_battery_kits)
        self.skip_native_browser_preview_library.setChecked(c.skip_native_browser_preview_library)
        self.find_real_instrument_folder.setChecked(c.find_real_instrument_folder)
        self.bottom_banner.show_terminal_button.setChecked(c.show_terminal)

    def set_step2_enabled(self, enabled):
        widgets = [
            self.proc_output_folder, self.proc_output_folder_btn,
            self.trim_silence, self.normalize,
            self.run_process_btn,
            self.sample_rate, self.bit_depth,
            self.skip_existing,
            self.skip_maschine_folders,
            self.skip_battery_kits,
            self.skip_native_browser_preview_library,
            self.find_real_instrument_folder,
        ]
        for w in widgets:
            w.setEnabled(enabled)

    def on_json_path_changed(self):
        enabled = bool(self.json_path.text().strip())
        self.set_step2_enabled(enabled)

    def choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Output Folder', self.output_folder.text())
        if folder:
            self.output_folder.setText(folder)

    def choose_json_file(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select JSON File', self.json_path.text(), 'JSON Files (*.json)')
        if file:
            self.json_path.setText(file)

    def choose_proc_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Output Folder', self.proc_output_folder.text())
        if folder:
            self.proc_output_folder.setText(folder)

    def run_build_json(self):
        output_folder = self.output_folder.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "Input Error", "Please select an output folder for the JSON file.")
            return

        builder = PreviewsJsonBuilder(output_folder=output_folder)
        self.log_output.append(f"Starting JSON build process for output folder: {output_folder}")
        self.show_loading('Building previews JSON...')
        self.run_worker(builder.run, {}, logger_name="PreviewsBuilder")

        json_path = os.path.join(output_folder, 'all_previews.json')
        self.json_path.setText(json_path)
        self.proc_output_folder.setText(os.path.abspath('./out/previews'))
        self.last_built_json_path = json_path

    def run_process_py(self):
        json_path = self.json_path.text().strip()
        output_folder = self.proc_output_folder.text().strip()

        if not json_path or not os.path.exists(json_path):
            QMessageBox.warning(self, "Input Error", "Please select a valid JSON file.")
            return
        if not output_folder:
            QMessageBox.warning(self, "Input Error", "Please select an output folder for the processed previews.")
            return

        sample_rate_val = None
        if self.sample_rate.text().strip():
            try:
                sample_rate_val = int(self.sample_rate.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Sample rate must be an integer.")
                return

        bit_depth_val = None
        if self.bit_depth.text().strip():
            try:
                bit_depth_val = int(self.bit_depth.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Bit depth must be an integer.")
                return

        processor = PreviewsProcessor(
            json_path=json_path,
            output_folder=output_folder,
            trim_silence=self.config.previews_exporter.trim_silence,
            normalize=self.config.previews_exporter.normalize,
            sample_rate=sample_rate_val,
            bit_depth=bit_depth_val,
            skip_existing=self.config.previews_exporter.skip_existing,
            skip_maschine_folders=self.config.previews_exporter.skip_maschine_folders,
            skip_battery_kits=self.config.previews_exporter.skip_battery_kits,
            skip_native_browser_preview_library=self.config.previews_exporter.skip_native_browser_preview_library,
            find_real_instrument_folder=self.config.previews_exporter.find_real_instrument_folder,
        )
        self.log_output.append(f"Starting preview export process for JSON: {json_path}")
        self.show_loading('Exporting previews...')
        # Pass the logger name "PreviewsProcessor" to the worker
        self.run_worker(processor.run, {}, logger_name="PreviewsProcessor")

    def run_worker(self, target_callable, kwargs, logger_name=None):
        self.run_build_btn.setEnabled(False)
        self.run_process_btn.setEnabled(False)
        self.has_output = False  # Reset flag before new process
        self.worker = WorkerThread(target_callable, kwargs, logger_name)
        self.worker.output_signal.connect(self.on_worker_output)
        self.worker.finished_signal.connect(self.on_subprocess_finished)
        self.worker.start()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = PreviewsExporterGUI()
    gui.show()
    sys.exit(app.exec())
