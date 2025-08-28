import json
import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox

from components.ansi_text_edit import AnsiTextEdit
from components.bottom_banner import BottomBanner
from components.matrix_editor import MatrixEditor
from components.pad_filter_editor import PadFilterEditor
from components.resizable_log_splitter import ResizableLogSplitter
from dialogs.error_dialog import ErrorDialog
from dialogs.export_complete_dialog import show_export_complete_dialog
from models.config import Config
from processors.groups.build_groups_json import GroupsJsonBuilder
from processors.groups.process_groups_json import GroupsProcessor
from utils import config_utils
from utils.bundle_utils import get_bundled_path
from utils.utils import apply_style
from utils.worker_utils import WorkerThread


class GroupsExporterGUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("resources/icons/groups.png")))
        self.setWindowTitle('NITools - Groups Exporter')
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
        if self.config.groups_exporter.width > 0 and self.config.groups_exporter.height > 0:
            self.resize(self.config.groups_exporter.width, self.config.groups_exporter.height)

        # Switch to export tab if json_path is already set
        if self.json_path.text().strip() and os.path.isfile(self.json_path.text().strip()):
            self.tabs.setCurrentIndex(1)

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget()

        # --- Tab 1: Process groups ---
        self.tab_process = QtWidgets.QWidget()
        process_layout = QtWidgets.QVBoxLayout()

        # Step 1 label
        step1_label = QtWidgets.QLabel("Step 1: Build JSON from .mxgrp")
        step1_label.setStyleSheet("font-weight: bold;")
        process_layout.addWidget(step1_label)

        # Scrollable content
        scroll_content = QtWidgets.QWidget()
        build_layout = QtWidgets.QFormLayout(scroll_content)

        self.input_folder = QtWidgets.QLineEdit()
        self.input_folder.setToolTip('Select the folder containing your .mxgrp files.')
        self.input_folder_btn = QtWidgets.QPushButton('Choose')
        self.input_folder_btn.setToolTip('Browse for the input folder.')
        self.input_folder_btn.clicked.connect(self.choose_input_folder)
        input_folder_layout = QtWidgets.QHBoxLayout()
        input_folder_layout.addWidget(self.input_folder)
        input_folder_layout.addWidget(self.input_folder_btn)
        build_layout.addRow('Input folder:', input_folder_layout)

        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder.setToolTip('Select the folder where the generated JSON and optional TXT files will be saved.')
        self.output_folder_btn = QtWidgets.QPushButton('Choose')
        self.output_folder_btn.setToolTip('Browse for the output folder.')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_layout.addRow('Output folder:', output_folder_layout)

        self.generate_txt = QtWidgets.QCheckBox('Generate TXT files')
        self.generate_txt.setToolTip('If checked, a .txt file will be generated for each group, listing unprocessed data for debug purposes.')
        build_layout.addRow('', self.generate_txt)

        scroll_area_process = QtWidgets.QScrollArea()
        scroll_area_process.setWidgetResizable(True)
        scroll_area_process.setWidget(scroll_content)
        process_layout.addWidget(scroll_area_process)

        self.run_build_btn = QtWidgets.QPushButton('Process Groups')
        self.run_build_btn.clicked.connect(self.run_build_json)
        self.run_build_btn.setProperty("class", "accent")
        process_layout.addWidget(self.run_build_btn)

        self.tab_process.setLayout(process_layout)
        self.tabs.addTab(self.tab_process, 'Process Groups')

        # --- Tab 2: Export groups ---
        self.tab_export = QtWidgets.QWidget()
        export_layout = QtWidgets.QVBoxLayout()

        # Step 2 label
        step2_label = QtWidgets.QLabel("Step 2: Export Groups")
        step2_label.setStyleSheet("font-weight: bold;")
        export_layout.addWidget(step2_label)

        # Scrollable content for Tab 2
        scrollable_content_export = QtWidgets.QWidget()
        scrollable_content_export_layout = QtWidgets.QVBoxLayout()

        export_form_layout = QtWidgets.QFormLayout()
        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip('Select the JSON file generated in Step 1 (e.g., all_groups.json).')
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.setToolTip('Browse for the JSON file.')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        export_form_layout.addRow('JSON file:', json_path_layout)
        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip('Select the folder where the processed group samples will be exported.')
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
        self.include_preview = QtWidgets.QCheckBox('Include preview samples')
        self.include_preview.setToolTip('If checked, a short preview sample will be generated for each group.')
        self.sample_rate = QtWidgets.QLineEdit()
        self.sample_rate.setPlaceholderText('Sample rate (e.g. 48000)')
        self.sample_rate.setToolTip('Set the sample rate for exported audio (e.g., 44100, 48000). Leave blank for original.')
        self.bit_depth = QtWidgets.QLineEdit()
        self.bit_depth.setPlaceholderText('Bit depth (e.g. 16)')
        self.bit_depth.setToolTip('Set the bit depth for exported audio (e.g., 16, 24). Leave blank for original.')
        options_layout.addWidget(self.skip_existing)
        options_layout.addWidget(self.trim_silence)
        options_layout.addWidget(self.normalize)
        options_layout.addWidget(self.include_preview)
        options_layout.addWidget(QtWidgets.QLabel('Sample rate:'))
        options_layout.addWidget(self.sample_rate)
        options_layout.addWidget(QtWidgets.QLabel('Bit depth:'))
        options_layout.addWidget(self.bit_depth)
        options_group.setLayout(options_layout)
        export_form_layout.addRow(options_group)

        # --- Pad Reorder Matrix group ---
        matrix_group = QtWidgets.QGroupBox('Pad Reorder Matrix (4x4)')
        matrix_layout = QtWidgets.QVBoxLayout()
        self.enable_matrix = QtWidgets.QCheckBox('Enable matrix reorder')
        self.enable_matrix.setToolTip('If checked, pads will be reordered according to the matrix below.')
        self.matrix_toggle_btn = QtWidgets.QPushButton('Show Matrix')
        self.matrix_toggle_btn.setToolTip('Toggle the visibility of the pad reorder matrix editor.')
        self.matrix_editor = MatrixEditor()
        self.matrix_editor.setVisible(False)
        self.matrix_toggle_btn.setCheckable(True)
        self.matrix_toggle_btn.setChecked(False)
        self.matrix_toggle_btn.toggled.connect(lambda checked: self.matrix_editor.setVisible(checked))
        self.matrix_toggle_btn.toggled.connect(lambda checked: self.matrix_toggle_btn.setText('Hide Matrix' if checked else 'Show Matrix'))
        matrix_layout.addWidget(self.enable_matrix)
        matrix_layout.addWidget(self.matrix_toggle_btn)
        matrix_layout.addWidget(self.matrix_editor)
        matrix_group.setLayout(matrix_layout)
        export_form_layout.addRow(matrix_group)

        # --- Pad Filter group ---
        pad_filter_group = QtWidgets.QGroupBox('Pad Filter Keywords')
        pad_filter_layout = QtWidgets.QVBoxLayout()
        self.filter_pads = QtWidgets.QCheckBox('Enable pad filtering')
        self.filter_pads.setToolTip('If checked, only groups where every pad matches at least one of its keywords will be included.')
        self.pad_filter_toggle_btn = QtWidgets.QPushButton('Show Pad Filter Editor')
        self.pad_filter_toggle_btn.setToolTip('Toggle the visibility of the pad filter editor.')
        self.pad_filter_editor = PadFilterEditor()
        self.pad_filter_editor.setVisible(False)
        self.pad_filter_toggle_btn.setCheckable(True)
        self.pad_filter_toggle_btn.setChecked(False)
        self.pad_filter_toggle_btn.toggled.connect(lambda checked: self.pad_filter_editor.setVisible(checked))
        self.pad_filter_toggle_btn.toggled.connect(lambda checked: self.pad_filter_toggle_btn.setText('Hide Pad Filter Editor' if checked else 'Show Pad Filter Editor'))
        pad_filter_layout.addWidget(self.filter_pads)
        pad_filter_layout.addWidget(self.pad_filter_toggle_btn)
        pad_filter_layout.addWidget(self.pad_filter_editor)
        pad_filter_group.setLayout(pad_filter_layout)
        export_form_layout.addRow(pad_filter_group)

        # --- Fill blanks group ---
        fill_group = QtWidgets.QGroupBox('Fill Blank Pads')
        fill_layout = QtWidgets.QVBoxLayout()
        self.fill_blanks = QtWidgets.QCheckBox('Fill blank pads')
        self.fill_blanks.setToolTip('If checked, blank pads will be filled with the specified sample or with random samples from the specified folder.')
        self.fill_blanks_path = QtWidgets.QLineEdit()
        self.fill_blanks_path.setPlaceholderText('Path to sample or folder (leave blank for a default silence sample)')
        self.fill_blanks_path.setToolTip('Select the file or folder containing samples to fill blank pads. If left blank, a default silence sample will be used.')
        self.fill_blanks_path_btn = QtWidgets.QPushButton('Choose')
        self.fill_blanks_path_btn.setToolTip('Browse for the fill blanks path.')
        self.fill_blanks_path_btn.clicked.connect(self.choose_fill_blanks_path)
        fill_blanks_path_layout = QtWidgets.QHBoxLayout()
        fill_blanks_path_layout.addWidget(self.fill_blanks_path)
        fill_blanks_path_layout.addWidget(self.fill_blanks_path_btn)
        fill_layout.addWidget(self.fill_blanks)
        fill_layout.addWidget(QtWidgets.QLabel('Fill blanks path:'))
        fill_layout.addLayout(fill_blanks_path_layout)
        fill_group.setLayout(fill_layout)
        export_form_layout.addRow(fill_group)

        scrollable_content_export_layout.addLayout(export_form_layout)

        scrollable_content_export.setLayout(scrollable_content_export_layout)
        scroll_area_export = QtWidgets.QScrollArea()
        scroll_area_export.setWidgetResizable(True)
        scroll_area_export.setWidget(scrollable_content_export)
        export_layout.addWidget(scroll_area_export)

        self.run_process_btn = QtWidgets.QPushButton('Export Groups')
        self.run_process_btn.clicked.connect(self.run_process_py)
        self.run_process_btn.setProperty("class", "accent")
        export_layout.addWidget(self.run_process_btn)
        self.tab_export.setLayout(export_layout)
        self.tabs.addTab(self.tab_export, 'Export Groups')

        # --- Log/output ---
        self.log_output = AnsiTextEdit()
        self.log_output.setReadOnly(True)

        # Create a splitter to make the log_output resizable
        splitter = ResizableLogSplitter(self.config, self.tabs, self.log_output)
        main_layout.addWidget(splitter)

        # --- Bottom banner ---
        self.bottom_banner = BottomBanner(self.config.groups_exporter.show_terminal)
        self.bottom_banner.terminal_toggled.connect(self.toggle_terminal_visibility)
        main_layout.addWidget(self.bottom_banner)

        self.setLayout(main_layout)
        self.set_step2_enabled(False)
        self.json_path.textChanged.connect(self.on_json_path_changed)
        self.setup_config_signals()
        # Connect enable checkboxes to update UI state
        self.enable_matrix.stateChanged.connect(self._update_matrix_editor_state)
        self.filter_pads.stateChanged.connect(self._update_pad_filter_editor_state)
        self.on_json_path_changed()  # Call once to set initial state based on json_path
        self.toggle_terminal_visibility(self.config.groups_exporter.show_terminal)

    def closeEvent(self, event):
        # Save current window size to config
        self.config.groups_exporter.width = self.width()
        self.config.groups_exporter.height = self.height()
        config_utils.save_config(self.config)
        super().closeEvent(event)

    def toggle_terminal_visibility(self, state):
        self.log_output.setVisible(state)
        self.config.groups_exporter.show_terminal = state
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
            self.worker = None
        else:
            self.run_build_btn.setEnabled(True)
            self.run_process_btn.setEnabled(True)
            self.hide_loading()

    def on_worker_output(self, text):
        self.log_output.append(text)
        self.has_output = True

    def setup_config_signals(self):
        # Save config on change
        # The keys here should match the attribute names in GroupsExporterConfig
        for widget, key in [
            (self.input_folder, 'input_folder'),
            (self.output_folder, 'output_folder'),
            (self.generate_txt, 'generate_txt'),
            (self.json_path, 'json_path'),
            (self.proc_output_folder, 'proc_output_folder'),
            (self.trim_silence, 'trim_silence'),
            (self.normalize, 'normalize'),
            (self.sample_rate, 'sample_rate'),
            (self.bit_depth, 'bit_depth'),
            (self.include_preview, 'include_preview'),
            (self.fill_blanks, 'fill_blanks'),
            (self.fill_blanks_path, 'fill_blanks_path'),
            (self.skip_existing, 'skip_existing'),
            (self.bottom_banner.show_terminal_button, 'show_terminal'),
            (self.enable_matrix, 'enable_matrix'),
            (self.filter_pads, 'filter_pads'),
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(lambda val, k=key: self.on_config_changed(k, val))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))
            elif isinstance(widget, QtWidgets.QPushButton) and widget.isCheckable():
                widget.toggled.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))

        # Connect editor-specific signals
        self.matrix_editor.matrix_changed.connect(self.on_matrix_config_changed)
        self.pad_filter_editor.pad_filter_changed.connect(self.on_pad_filter_config_changed)

    def on_config_changed(self, key, value):
        # Update the specific attribute in the groups_exporter sub-model
        setattr(self.config.groups_exporter, key, value)
        config_utils.save_config(self.config)

    def on_matrix_config_changed(self):
        self.config.groups_exporter.matrix_config = self.matrix_editor.get_matrix()
        config_utils.save_config(self.config)

    def on_pad_filter_config_changed(self):
        self.config.groups_exporter.pad_filter_config = self.pad_filter_editor.get_pad_filter()
        config_utils.save_config(self.config)

    def load_config_to_ui(self):
        c = self.config.groups_exporter
        self.input_folder.setText(c.input_folder)
        self.output_folder.setText(c.output_folder)
        self.generate_txt.setChecked(c.generate_txt)
        self.json_path.setText(c.json_path)
        self.proc_output_folder.setText(c.proc_output_folder)
        self.trim_silence.setChecked(c.trim_silence)
        self.normalize.setChecked(c.normalize)
        self.sample_rate.setText(c.sample_rate)
        self.bit_depth.setText(c.bit_depth)
        self.skip_existing.setChecked(c.skip_existing)
        self.enable_matrix.setChecked(c.enable_matrix)
        self.matrix_editor.set_matrix(self.config.groups_exporter.matrix_config)
        self.filter_pads.setChecked(c.filter_pads)
        self.pad_filter_editor.set_pad_filter(self.config.groups_exporter.pad_filter_config)
        self.include_preview.setChecked(c.include_preview)
        self.fill_blanks.setChecked(c.fill_blanks)
        self.fill_blanks_path.setText(c.fill_blanks_path)
        self.bottom_banner.show_terminal_button.setChecked(c.show_terminal)

    def _update_matrix_editor_state(self):
        enabled = bool(self.json_path.text().strip()) and self.enable_matrix.isChecked()
        self.matrix_editor.setEnabled(enabled)
        self.matrix_toggle_btn.setEnabled(enabled)
        # Ensure matrix editor visibility is consistent with toggle button state
        self.matrix_editor.setVisible(self.matrix_toggle_btn.isChecked() and enabled)

    def _update_pad_filter_editor_state(self):
        enabled = bool(self.json_path.text().strip()) and self.filter_pads.isChecked()
        self.pad_filter_editor.setEnabled(enabled)
        self.pad_filter_toggle_btn.setEnabled(enabled)
        # Ensure pad filter editor visibility is consistent with toggle button state
        self.pad_filter_editor.setVisible(self.pad_filter_toggle_btn.isChecked() and enabled)

    def set_step2_enabled(self, enabled):
        widgets = [
            self.proc_output_folder, self.proc_output_folder_btn,
            self.trim_silence, self.normalize,
            self.fill_blanks, self.fill_blanks_path, self.fill_blanks_path_btn,
            self.run_process_btn,
            self.sample_rate, self.bit_depth,
            self.include_preview,
            self.skip_existing
        ]
        for w in widgets:
            w.setEnabled(enabled)

        # Enable/disable the checkboxes themselves
        self.enable_matrix.setEnabled(enabled)
        self.filter_pads.setEnabled(enabled)

        # Call the specific update methods to ensure matrix/filter editors and their toggles
        # are correctly enabled/disabled based on both the overall step2 state AND their own checkboxes.
        self._update_matrix_editor_state()
        self._update_pad_filter_editor_state()

    def on_json_path_changed(self):
        enabled = bool(self.json_path.text().strip())
        self.set_step2_enabled(enabled)
        self._update_matrix_editor_state()
        self._update_pad_filter_editor_state()

    def choose_input_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Input Folder', self.input_folder.text())
        if folder:
            self.input_folder.setText(folder)

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

    def choose_fill_blanks_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Fill Blanks Folder', self.fill_blanks_path.text())
        if path:
            self.fill_blanks_path.setText(path)

    def run_build_json(self):
        input_folder = self.input_folder.text().strip()
        output_folder = self.output_folder.text().strip()
        generate_txt = self.generate_txt.isChecked()

        if not input_folder:
            QMessageBox.warning(self, "Input Error", "Please select an input folder for .mxgrp files.")
            return
        if not output_folder:
            QMessageBox.warning(self, "Input Error", "Please select an output folder for the JSON file.")
            return

        builder = GroupsJsonBuilder(
            input_folder=input_folder,
            output_folder=output_folder,
            generate_txt=generate_txt
        )
        self.log_output.append(f"Starting JSON build process for input folder: {input_folder}")
        self.show_loading('Processing groups...')
        self.run_worker(builder.run, {}, logger_name="GroupsBuilder")

        json_path = os.path.join(output_folder, 'all_groups.json')
        self.json_path.setText(json_path)
        self.proc_output_folder.setText(os.path.abspath('./out/groups'))
        self.last_built_json_path = json_path

    def run_process_py(self):
        json_path = self.json_path.text().strip()
        output_folder = self.proc_output_folder.text().strip()

        if not json_path or not os.path.exists(json_path):
            QMessageBox.warning(self, "Input Error", "Please select a valid JSON file.")
            return
        if not output_folder:
            QMessageBox.warning(self, "Input Error", "Please select an output folder for the processed groups.")
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

        fill_blanks_path_val = None
        if self.config.groups_exporter.fill_blanks:
            if self.config.groups_exporter.fill_blanks_path:
                fill_blanks_path_val = self.config.groups_exporter.fill_blanks_path
            else:
                fill_blanks_path_val = get_bundled_path("resources/audio/.wav")

        processor = GroupsProcessor(
            json_path=json_path,
            output_folder=output_folder,
            trim_silence=self.config.groups_exporter.trim_silence,
            normalize=self.config.groups_exporter.normalize,
            sample_rate=sample_rate_val,
            bit_depth=bit_depth_val,
            matrix=self.matrix_editor.get_matrix() if self.config.groups_exporter.enable_matrix else None,
            filter_pads=self.config.groups_exporter.filter_pads,
            pad_filter=self.pad_filter_editor.get_pad_filter() if self.config.groups_exporter.filter_pads else None,
            fill_blanks=fill_blanks_path_val,
            enable_matrix=self.config.groups_exporter.enable_matrix,
            include_preview=self.config.groups_exporter.include_preview,
            skip_existing=self.config.groups_exporter.skip_existing
        )
        self.log_output.append(f"Starting group export process for JSON: {json_path}")
        self.show_loading('Exporting groups...')
        self.run_worker(processor.run, {}, logger_name="GroupsProcessor")

    def run_worker(self, target_callable, kwargs, logger_name=None):
        self.run_build_btn.setEnabled(False)
        self.run_process_btn.setEnabled(False)
        self.has_output = False
        self.worker = WorkerThread(target_callable, kwargs, logger_name)
        self.worker.output_signal.connect(self.on_worker_output)
        self.worker.finished_signal.connect(self.on_subprocess_finished)
        self.worker.start()

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
                    # Check if built JSON has groups
                    if self.last_built_json_path and os.path.exists(self.last_built_json_path):
                        try:
                            with open(self.last_built_json_path, 'r') as f:
                                data = json.load(f)
                                if isinstance(data, list) and len(data) == 0:
                                    # Empty JSON result
                                    self.log_output.append("0 groups processed.\n")
                                    QMessageBox.warning(self, "No Groups Processed", "The process completed but no groups were found or processed.")
                                else:
                                    # Success with groups
                                    self.tabs.setCurrentIndex(1)
                                    QMessageBox.information(self, "Process Complete", "Groups JSON file has been successfully built!")
                        except Exception as e:
                            # Unexpected JSON read error → still treat as success
                            self.log_output.append(f"Warning: Could not verify JSON file: {e}\n")
                            self.tabs.setCurrentIndex(1)
                            QMessageBox.information(self, "Process Complete", "Groups JSON file built, but verification failed. Proceed with caution.")
                    else:
                        # No JSON path set → treat as empty
                        QMessageBox.warning(self, "No Output JSON", "The process finished but no JSON file was found.")

                else:  # Export tab
                    show_export_complete_dialog(parent=self, output_folder=self.proc_output_folder.text().strip(), log_content=self.log_output.toPlainText(),
                                                title="Export Complete", message="Groups export process finished successfully.")

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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = GroupsExporterGUI()
    gui.show()
    sys.exit(app.exec())
