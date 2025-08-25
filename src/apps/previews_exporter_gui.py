import logging
import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox

from components.ansi_text_edit import AnsiTextEdit
from components.bottom_banner import BottomBanner
from components.resizable_log_splitter import ResizableLogSplitter
from dialogs.error_dialog import ErrorDialog
from models.config import Config
from processors.previews.build_previews_json import PreviewsJsonBuilder
from processors.previews.process_previews_json import PreviewsProcessor
from utils import config_utils
from utils.bundle_utils import get_bundled_path
from utils.worker_utils import WorkerThread


class PreviewsExporterGUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("img/logos/previews.png")))
        self.setWindowTitle('NITools - Previews Exporter')
        self.setMinimumWidth(700)
        self.config: Config = config_utils.load_config()
        self.worker = None
        self.progress_dialog = None
        self.cancelled = False
        self.has_output = False  # Initialize the flag
        self.init_ui()
        self.load_config_to_ui()
        default_json = os.path.abspath('./out/all_previews.json')
        # Check if json_path is empty in config, then set default
        if os.path.isfile(default_json) and not self.config.previews_exporter.json_path:
            self.json_path.setText(default_json)
            self.config.previews_exporter.json_path = default_json
            config_utils.save_config(self.config)

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget()

        # --- Tab 1: Build JSON ---
        self.tab_build = QtWidgets.QWidget()
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
        build_layout.addWidget(self.run_build_btn)

        self.tab_build.setLayout(build_layout)
        self.tabs.addTab(self.tab_build, 'Process Previews')

        # --- Tab 2: Process Previews ---
        self.tab_process = QtWidgets.QWidget()
        process_layout = QtWidgets.QVBoxLayout()

        # Step 2 label
        step2_label = QtWidgets.QLabel("Step 2: Export Previews")
        step2_label.setStyleSheet("font-weight: bold;")
        process_layout.addWidget(step2_label)

        # Scrollable content for Tab 2
        scrollable_content_process = QtWidgets.QWidget()
        scrollable_content_process_layout = QtWidgets.QVBoxLayout()

        process_form_layout = QtWidgets.QFormLayout()

        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip('Select the JSON file generated in Step 1 (e.g., previews.json).')
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.setToolTip('Browse for the JSON file.')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        process_form_layout.addRow('JSON file:', json_path_layout)

        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip('Select the folder where the processed preview samples will be exported.')
        self.proc_output_folder_btn = QtWidgets.QPushButton('Choose')
        self.proc_output_folder_btn.setToolTip('Browse for the output folder.')
        self.proc_output_folder_btn.clicked.connect(self.choose_proc_output_folder)
        proc_output_folder_layout = QtWidgets.QHBoxLayout()
        proc_output_folder_layout.addWidget(self.proc_output_folder)
        proc_output_folder_layout.addWidget(self.proc_output_folder_btn)
        process_form_layout.addRow('Output folder:', proc_output_folder_layout)

        # --- Options group ---
        options_group = QtWidgets.QGroupBox('Options')
        options_layout = QtWidgets.QVBoxLayout()
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
        options_layout.addWidget(self.trim_silence)
        options_layout.addWidget(self.normalize)
        options_layout.addWidget(QtWidgets.QLabel('Sample rate:'))
        options_layout.addWidget(self.sample_rate)
        options_layout.addWidget(QtWidgets.QLabel('Bit depth:'))
        options_layout.addWidget(self.bit_depth)
        options_group.setLayout(options_layout)
        process_form_layout.addRow(options_group)

        scrollable_content_process_layout.addLayout(process_form_layout)

        scrollable_content_process.setLayout(scrollable_content_process_layout)
        scroll_area_process = QtWidgets.QScrollArea()
        scroll_area_process.setWidgetResizable(True)
        scroll_area_process.setWidget(scrollable_content_process)
        process_layout.addWidget(scroll_area_process)

        self.run_process_btn = QtWidgets.QPushButton('Export Previews')
        self.run_process_btn.clicked.connect(self.run_process_py)
        process_layout.addWidget(self.run_process_btn)

        self.tab_process.setLayout(process_layout)
        self.tabs.addTab(self.tab_process, 'Export Previews')

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
            # Manually call finished handler to update UI state
            self.on_subprocess_finished(-1)
            # Clear the worker reference
            self.worker = None
        else:
            self.run_build_btn.setEnabled(True)
            self.run_process_btn.setEnabled(True)
            self.hide_loading()

    def on_worker_output(self, text):
        self.log_output.append(text)
        self.has_output = True

    def on_subprocess_finished(self, code):
        if self.cancelled:
            self.log_output.append('Operation cancelled by user.\n')
        elif code == 0 and self.has_output:  # Only switch if successful AND there was output
            self.log_output.append('Done\n')
            if self.tabs.currentIndex() == 0:
                self.tabs.setCurrentIndex(1)
        elif code == 0 and not self.has_output:  # If successful but no output, just say Done
            self.log_output.append('Done\n')
        else:
            error_message = f'Process finished with exit code {code}\n'
            self.log_output.append(error_message)

            full_log = self.log_output.toPlainText()
            log_lines = full_log.splitlines()
            # Take the last 20 lines as detailed error, or fewer if the log is shorter
            detailed_error_text = "\n".join(log_lines[-20:])

            error_dialog = ErrorDialog(
                parent=self,
                title="Subprocess Error",
                message=f"A script finished with an error (exit code {code}). Please check the detailed log for more information.",
                detailed_text=detailed_error_text,
                icon=QMessageBox.Icon.Critical
            )
            error_dialog.exec()
        self.run_build_btn.setEnabled(True)
        self.run_process_btn.setEnabled(True)
        self.hide_loading()

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
        self.bottom_banner.show_terminal_button.setChecked(c.show_terminal)

    def set_step2_enabled(self, enabled):
        widgets = [
            self.proc_output_folder, self.proc_output_folder_btn,
            self.trim_silence, self.normalize,
            self.run_process_btn,
            self.sample_rate, self.bit_depth,
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

        json_path = os.path.join(output_folder, 'previews.json')
        self.json_path.setText(json_path)
        self.proc_output_folder.setText(os.path.abspath('./out/previews'))

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
