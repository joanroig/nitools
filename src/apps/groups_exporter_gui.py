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
from models.config import Config
from processors.groups.build_groups_json import GroupsJsonBuilder
from processors.groups.process_groups_json import GroupsProcessor
from utils import config_utils
from utils.bundle_utils import get_bundled_path
from utils.worker_utils import WorkerThread


class GroupsExporterGUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("img/logos/groups.png")))
        self.setWindowTitle('NITools - Groups Exporter')
        self.setMinimumWidth(700)
        self.config: Config = config_utils.load_config()
        self.worker = None
        self.progress_dialog = None
        self.cancelled = False
        self.has_output = False
        self.last_built_json_path = None
        self.init_ui()
        self.load_config_to_ui()
        default_json = os.path.abspath('./out/all_groups.json')
        # Check if json_path is empty in config, then set default
        if os.path.isfile(default_json) and not self.config.groups_exporter.json_path:
            self.json_path.setText(default_json)
            self.config.groups_exporter.json_path = default_json
            config_utils.save_config(self.config)

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
        self.generate_txt.setToolTip('If checked, a .txt file will be generated for each group, listing its samples.')
        build_layout.addRow('', self.generate_txt)

        scroll_area_process = QtWidgets.QScrollArea()
        scroll_area_process.setWidgetResizable(True)
        scroll_area_process.setWidget(scroll_content)
        process_layout.addWidget(scroll_area_process)

        self.run_build_btn = QtWidgets.QPushButton('Process Groups')
        self.run_build_btn.clicked.connect(self.run_build_json)
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

        process_form_layout = QtWidgets.QFormLayout()
        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip('Select the JSON file generated in Step 1 (e.g., all_groups.json).')
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.setToolTip('Browse for the JSON file.')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        process_form_layout.addRow('JSON file:', json_path_layout)
        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip('Select the folder where the processed group samples will be exported.')
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
        self.include_preview = QtWidgets.QCheckBox('Include preview samples')
        self.include_preview.setToolTip('If checked, a short preview sample will be generated for each group.')
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
        options_layout.addWidget(self.include_preview)
        options_layout.addWidget(self.trim_silence)
        options_layout.addWidget(self.normalize)
        options_layout.addWidget(QtWidgets.QLabel('Sample rate:'))
        options_layout.addWidget(self.sample_rate)
        options_layout.addWidget(QtWidgets.QLabel('Bit depth:'))
        options_layout.addWidget(self.bit_depth)
        options_group.setLayout(options_layout)
        process_form_layout.addRow(options_group)

        # --- Pad Reorder Matrix group ---
        matrix_group = QtWidgets.QGroupBox('Pad Reorder Matrix (4x4)')
        matrix_layout = QtWidgets.QVBoxLayout()
        self.enable_matrix = QtWidgets.QCheckBox('Enable matrix reorder')
        self.enable_matrix.setToolTip('If checked, pads will be reordered according to the matrix below.')
        self.matrix_toggle_btn = QtWidgets.QPushButton('Show Matrix')
        self.matrix_toggle_btn.setToolTip('Toggle the visibility of the pad reorder matrix editor.')
        self.matrix_editor = MatrixEditor({
            1: 13, 2: 14, 3: 15, 4: 16,
            5: 9, 6: 10, 7: 11, 8: 12,
            9: 5, 10: 6, 11: 7, 12: 8,
            13: 1, 14: 2, 15: 3, 16: 4
        })
        self.matrix_editor.setVisible(False)
        self.matrix_toggle_btn.setCheckable(True)
        self.matrix_toggle_btn.setChecked(False)
        self.matrix_toggle_btn.toggled.connect(lambda checked: self.matrix_editor.setVisible(checked))
        self.matrix_toggle_btn.toggled.connect(lambda checked: self.matrix_toggle_btn.setText('Hide Matrix' if checked else 'Show Matrix'))
        matrix_layout.addWidget(self.enable_matrix)
        matrix_layout.addWidget(self.matrix_toggle_btn)
        matrix_layout.addWidget(self.matrix_editor)
        matrix_group.setLayout(matrix_layout)
        process_form_layout.addRow(matrix_group)

        # --- Pad Filter group ---
        pad_filter_group = QtWidgets.QGroupBox('Pad Filter Keywords')
        pad_filter_layout = QtWidgets.QVBoxLayout()
        self.filter_pads = QtWidgets.QCheckBox('Enable pad filtering')
        self.filter_pads.setToolTip('If checked, only groups where every pad matches at least one of its keywords will be included.')
        self.pad_filter_toggle_btn = QtWidgets.QPushButton('Show Pad Filter Editor')
        self.pad_filter_toggle_btn.setToolTip('Toggle the visibility of the pad filter editor.')
        self.pad_filter_editor = PadFilterEditor({
            1: ["kick"],
            2: ["snare", "snap", "clap"],
            3: ["hh", "hihat", "hi hat", "shaker"]
        })
        self.pad_filter_editor.setVisible(False)
        self.pad_filter_toggle_btn.setCheckable(True)
        self.pad_filter_toggle_btn.setChecked(False)
        self.pad_filter_toggle_btn.toggled.connect(lambda checked: self.pad_filter_editor.setVisible(checked))
        self.pad_filter_toggle_btn.toggled.connect(lambda checked: self.pad_filter_toggle_btn.setText('Hide Pad Filter Editor' if checked else 'Show Pad Filter Editor'))
        pad_filter_layout.addWidget(self.filter_pads)
        pad_filter_layout.addWidget(self.pad_filter_toggle_btn)
        pad_filter_layout.addWidget(self.pad_filter_editor)
        pad_filter_group.setLayout(pad_filter_layout)
        process_form_layout.addRow(pad_filter_group)

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
        process_form_layout.addRow(fill_group)

        scrollable_content_export_layout.addLayout(process_form_layout)  # Add the form layout directly

        scrollable_content_export.setLayout(scrollable_content_export_layout)
        scroll_area_export = QtWidgets.QScrollArea()
        scroll_area_export.setWidgetResizable(True)
        scroll_area_export.setWidget(scrollable_content_export)
        export_layout.addWidget(scroll_area_export)

        self.run_process_btn = QtWidgets.QPushButton('Export Groups')
        self.run_process_btn.clicked.connect(self.run_process_py)
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
            (self.bottom_banner.show_terminal_button, 'show_terminal'),
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(lambda val, k=key: self.on_config_changed(k, val))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))
            elif isinstance(widget, QtWidgets.QPushButton) and widget.isCheckable():
                widget.toggled.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))

    def on_config_changed(self, key, value):
        # Update the specific attribute in the groups_exporter sub-model
        setattr(self.config.groups_exporter, key, value)
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
        self.enable_matrix.setChecked(c.enable_matrix)
        self.filter_pads.setChecked(c.filter_pads)
        self.include_preview.setChecked(c.include_preview)
        self.fill_blanks.setChecked(c.fill_blanks)
        self.fill_blanks_path.setText(c.fill_blanks_path)
        self.bottom_banner.show_terminal_button.setChecked(c.show_terminal)

    def _update_matrix_editor_state(self):
        enabled = bool(self.json_path.text().strip()) and self.enable_matrix.isChecked()
        self.matrix_editor.setEnabled(enabled)
        self.matrix_toggle_btn.setEnabled(enabled)

    def _update_pad_filter_editor_state(self):
        enabled = bool(self.json_path.text().strip()) and self.filter_pads.isChecked()
        self.pad_filter_editor.setEnabled(enabled)
        self.pad_filter_toggle_btn.setEnabled(enabled)

    def set_step2_enabled(self, enabled):
        widgets = [
            self.proc_output_folder, self.proc_output_folder_btn,
            self.trim_silence, self.normalize,
            self.fill_blanks, self.fill_blanks_path, self.fill_blanks_path_btn,
            self.run_process_btn,
            self.sample_rate, self.bit_depth,
            self.include_preview
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
                fill_blanks_path_val = get_bundled_path("./assets/.wav")

        processor = GroupsProcessor(
            json_path=json_path,
            output_folder=output_folder,
            trim_silence_flag=self.config.groups_exporter.trim_silence,
            normalize_flag=self.config.groups_exporter.normalize,
            sample_rate=sample_rate_val,
            bit_depth=bit_depth_val,
            matrix=self.matrix_editor.get_matrix() if self.config.groups_exporter.enable_matrix else None,
            filter_pads=self.config.groups_exporter.filter_pads,
            pad_filter=self.pad_filter_editor.get_pad_filter() if self.config.groups_exporter.filter_pads else None,
            fill_blanks=fill_blanks_path_val,
            enable_matrix=self.config.groups_exporter.enable_matrix,
            include_preview=self.config.groups_exporter.include_preview
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

    def on_subprocess_finished(self, code):
        if self.cancelled:
            self.log_output.append('Operation cancelled by user.\n')
        elif code == 0 and self.has_output:  # Only switch if successful AND there was output
            self.log_output.append('Done\n')
            # Check if the process was 'build_groups_json.py' and if there were any groups processed
            if self.tabs.currentIndex() == 0 and self.last_built_json_path and os.path.exists(self.last_built_json_path):
                try:
                    with open(self.last_built_json_path, 'r') as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) == 0:
                            self.log_output.append('0 groups processed. Not switching tabs.\n')
                            error_dialog = ErrorDialog(
                                parent=self,
                                title="No Groups Processed",
                                message="No groups were found or processed. Please check your input folder and settings.",
                                detailed_text="The build process completed successfully, but the resulting JSON file indicates that no groups were processed. This might be due to incorrect input folder, no .mxgrp files found, or filters preventing any groups from being included.",
                                icon=QMessageBox.Icon.Information
                            )
                            error_dialog.exec()
                            # Do not switch tabs if 0 groups were processed
                        else:
                            self.tabs.setCurrentIndex(1)
                except json.JSONDecodeError:
                    self.log_output.append('Error reading JSON file. Switching tabs anyway.\n')
                    self.tabs.setCurrentIndex(1)
                except Exception as e:
                    self.log_output.append(f'An unexpected error occurred: {e}. Switching tabs anyway.\n')
                    self.tabs.setCurrentIndex(1)
            elif self.has_output:
                # For other processes, if successful and has output, switch tabs
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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = GroupsExporterGUI()
    gui.show()
    sys.exit(app.exec())
