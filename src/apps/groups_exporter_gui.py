import json  # Keep json for tempfile operations
import os
import subprocess
import sys
import tempfile

from PyQt6 import QtCore, QtGui, QtWidgets

from components.version_label import VersionLabel
from utils import config_utils
from utils.bundle_utils import get_bundled_path

from models.config import Config


class MatrixEditor(QtWidgets.QWidget):
    def __init__(self, default_matrix, parent=None):
        super().__init__(parent)

        self.grid = []
        main_layout = QtWidgets.QVBoxLayout()
        for row in range(4):
            row_layout = QtWidgets.QHBoxLayout()
            row_widgets = []
            for col in range(4):
                pad_num = row * 4 + col + 1
                container = QtWidgets.QWidget()
                container_layout = QtWidgets.QHBoxLayout()
                container_layout.setContentsMargins(0, 0, 0, 0)
                label = QtWidgets.QLabel(f"Pad {pad_num:02d} → ")
                spin = QtWidgets.QSpinBox()
                spin.setRange(1, 16)
                spin.setValue(default_matrix.get(pad_num, pad_num))
                container_layout.addWidget(label)
                container_layout.addWidget(spin)
                container_layout.addWidget(QtWidgets.QLabel(" "))
                container.setLayout(container_layout)
                row_layout.addWidget(container)
                row_widgets.append(spin)
            self.grid.append(row_widgets)
            main_layout.addLayout(row_layout)
        self.setLayout(main_layout)

    def get_matrix(self):
        matrix = {}
        for row in range(4):
            for col in range(4):
                pad_num = row * 4 + col + 1
                matrix[pad_num] = self.grid[row][col].value()
        return matrix


class PadFilterEditor(QtWidgets.QWidget):
    def __init__(self, default_filter, parent=None):
        super().__init__(parent)
        self.pad_select = QtWidgets.QComboBox()
        self.pad_select.addItems([str(i) for i in range(1, 17)])
        self.keyword_list = QtWidgets.QListWidget()
        self.keyword_input = QtWidgets.QLineEdit()
        self.add_btn = QtWidgets.QPushButton('Add')
        self.remove_btn = QtWidgets.QPushButton('Remove Selected')
        self.pad_filters = {i: default_filter.get(i, [])[:] for i in range(1, 17)}
        self.pad_select.currentIndexChanged.connect(self.load_pad_keywords)
        self.add_btn.clicked.connect(self.add_keyword)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.load_pad_keywords()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel('Pad (1-16):'))
        layout.addWidget(self.pad_select)
        layout.addWidget(QtWidgets.QLabel('Keywords:'))
        layout.addWidget(self.keyword_list)
        hlayout = QtWidgets.QHBoxLayout()
        hlayout.addWidget(self.keyword_input)
        hlayout.addWidget(self.add_btn)
        layout.addLayout(hlayout)
        layout.addWidget(self.remove_btn)
        self.setLayout(layout)

    def load_pad_keywords(self):
        pad = int(self.pad_select.currentText())
        self.keyword_list.clear()
        for kw in self.pad_filters.get(pad, []):
            self.keyword_list.addItem(kw)

    def add_keyword(self):
        pad = int(self.pad_select.currentText())
        kw = self.keyword_input.text().strip()
        if kw:
            self.pad_filters.setdefault(pad, []).append(kw)
            self.keyword_input.clear()
            self.load_pad_keywords()

    def remove_selected(self):
        pad = int(self.pad_select.currentText())
        selected = self.keyword_list.selectedItems()
        for item in selected:
            self.pad_filters[pad].remove(item.text())
        self.load_pad_keywords()

    def get_pad_filter(self):
        return {pad: kws for pad, kws in self.pad_filters.items() if kws}


class WorkerThread(QtCore.QThread):
    output_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal(int)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            self.output_signal.emit(line.rstrip())
        proc.wait()
        self.finished_signal.emit(proc.returncode)


class GroupsExporterGUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("img/logos/groups.png")))
        self.setWindowTitle('Groups Exporter')
        self.setGeometry(100, 100, 700, 800)
        self.config: Config = config_utils.load_config()
        self.worker = None
        self.progress_dialog = None
        self.cancelled = False
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
        build_group = QtWidgets.QGroupBox('Step 1: Build JSON from .mxgrp')
        build_layout = QtWidgets.QFormLayout()
        self.input_folder = QtWidgets.QLineEdit()
        self.input_folder_btn = QtWidgets.QPushButton('Choose')
        self.input_folder_btn.clicked.connect(self.choose_input_folder)
        input_folder_layout = QtWidgets.QHBoxLayout()
        input_folder_layout.addWidget(self.input_folder)
        input_folder_layout.addWidget(self.input_folder_btn)
        build_layout.addRow('Input folder:', input_folder_layout)
        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder_btn = QtWidgets.QPushButton('Choose')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_layout.addRow('Output folder:', output_folder_layout)
        self.generate_txt = QtWidgets.QCheckBox('Generate TXT files')
        build_layout.addRow('', self.generate_txt)
        self.run_build_btn = QtWidgets.QPushButton('Run build_json.py')
        self.run_build_btn.clicked.connect(self.run_build_json)
        build_layout.addRow('', self.run_build_btn)
        build_group.setLayout(build_layout)
        process_layout.addWidget(build_group)
        self.tab_process.setLayout(process_layout)
        self.tabs.addTab(self.tab_process, 'Process groups')
        # --- Tab 2: Export groups ---
        self.tab_export = QtWidgets.QWidget()
        export_layout = QtWidgets.QVBoxLayout()
        process_group = QtWidgets.QGroupBox('Step 2: Process groups')
        process_form_layout = QtWidgets.QFormLayout()
        self.json_path = QtWidgets.QLineEdit()
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        process_form_layout.addRow('JSON file:', json_path_layout)
        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder_btn = QtWidgets.QPushButton('Choose')
        self.proc_output_folder_btn.clicked.connect(self.choose_proc_output_folder)
        proc_output_folder_layout = QtWidgets.QHBoxLayout()
        proc_output_folder_layout.addWidget(self.proc_output_folder)
        proc_output_folder_layout.addWidget(self.proc_output_folder_btn)
        process_form_layout.addRow('Output folder:', proc_output_folder_layout)

        # --- Options group ---
        options_group = QtWidgets.QGroupBox('Options')
        options_layout = QtWidgets.QVBoxLayout()
        self.trim_silence = QtWidgets.QCheckBox('Trim silence')
        self.normalize = QtWidgets.QCheckBox('Normalize')
        self.sample_rate = QtWidgets.QLineEdit()
        self.sample_rate.setPlaceholderText('Sample rate (e.g. 48000)')
        self.bit_depth = QtWidgets.QLineEdit()
        self.bit_depth.setPlaceholderText('Bit depth (e.g. 16)')
        self.include_preview = QtWidgets.QCheckBox('Include preview samples')
        options_layout.addWidget(self.trim_silence)
        options_layout.addWidget(self.normalize)
        options_layout.addWidget(QtWidgets.QLabel('Sample rate:'))
        options_layout.addWidget(self.sample_rate)
        options_layout.addWidget(QtWidgets.QLabel('Bit depth:'))
        options_layout.addWidget(self.bit_depth)
        options_layout.addWidget(self.include_preview)
        options_group.setLayout(options_layout)
        process_form_layout.addRow(options_group)

        # --- Pad Reorder Matrix group ---
        matrix_group = QtWidgets.QGroupBox('Pad Reorder Matrix (4x4)')
        matrix_layout = QtWidgets.QVBoxLayout()
        self.enable_matrix = QtWidgets.QCheckBox('Enable matrix reorder')
        self.matrix_toggle_btn = QtWidgets.QPushButton('Show Matrix')
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
        self.pad_filter_toggle_btn = QtWidgets.QPushButton('Show Pad Filter Editor')
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
        self.fill_blanks_path = QtWidgets.QLineEdit()
        self.fill_blanks_path_btn = QtWidgets.QPushButton('Choose')
        self.fill_blanks_path_btn.clicked.connect(self.choose_fill_blanks_path)
        fill_blanks_path_layout = QtWidgets.QHBoxLayout()
        fill_blanks_path_layout.addWidget(self.fill_blanks_path)
        fill_blanks_path_layout.addWidget(self.fill_blanks_path_btn)
        fill_layout.addWidget(self.fill_blanks)
        fill_layout.addWidget(QtWidgets.QLabel('Fill blanks path:'))
        fill_layout.addLayout(fill_blanks_path_layout)
        fill_group.setLayout(fill_layout)
        process_form_layout.addRow(fill_group)
        self.run_process_btn = QtWidgets.QPushButton('Run process.py')
        self.run_process_btn.clicked.connect(self.run_process_py)
        process_form_layout.addRow('', self.run_process_btn)
        process_group.setLayout(process_form_layout)
        export_layout.addWidget(process_group)
        self.tab_export.setLayout(export_layout)
        self.tabs.addTab(self.tab_export, 'Export groups')
        main_layout.addWidget(self.tabs)

        # --- Log/output ---
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(self.log_output)

        # --- Bottom banner ---
        version = VersionLabel()
        main_layout.addWidget(version)

        self.setLayout(main_layout)
        self.set_step2_enabled(False)
        self.json_path.textChanged.connect(self.on_json_path_changed)
        self.setup_config_signals()
        # Connect enable checkboxes to update UI state
        self.enable_matrix.stateChanged.connect(self._update_matrix_editor_state)
        self.filter_pads.stateChanged.connect(self._update_pad_filter_editor_state)
        self.on_json_path_changed()  # Call once to set initial state based on json_path

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
            self.worker.terminate()
            self.cancelled = True
            self.on_subprocess_finished(-1)
        else:
            self.run_build_btn.setEnabled(True)
            self.run_process_btn.setEnabled(True)
            self.hide_loading()

    def on_subprocess_finished(self, code):
        if self.cancelled:
            self.log_output.append('Operation cancelled by user.\n')
        elif code == 0:
            self.log_output.append('Done\n')
            if self.tabs.currentIndex() == 0:
                self.tabs.setCurrentIndex(1)
        else:
            self.log_output.append(f'Process finished with exit code {code}\n')
        self.run_build_btn.setEnabled(True)
        self.run_process_btn.setEnabled(True)
        self.hide_loading()

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
            (self.enable_matrix, 'enable_matrix'),
            (self.filter_pads, 'filter_pads'),
            (self.include_preview, 'include_preview'),
            (self.fill_blanks, 'fill_blanks'),
            (self.fill_blanks_path, 'fill_blanks_path'),
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(lambda val, k=key: self.on_config_changed(k, val))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))

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
        generate_txt = 'true' if self.generate_txt.isChecked() else 'false'
        script_path = os.path.join('src', 'processors', 'groups', 'build_groups_json.py')
        cmd = [sys.executable, script_path, input_folder, output_folder, generate_txt]
        self.log_output.append(f"Running: {' '.join(cmd)}")
        self.show_loading('Processing groups...')
        self.run_subprocess(cmd)
        json_path = os.path.join(output_folder, 'all_groups.json')
        self.json_path.setText(json_path)
        self.proc_output_folder.setText(os.path.abspath('./out/groups'))

    def run_process_py(self):
        json_path = self.json_path.text().strip()
        output_folder = self.proc_output_folder.text().strip()
        matrix = self.matrix_editor.get_matrix()
        pad_filter = self.pad_filter_editor.get_pad_filter()
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.json') as matrix_file:
            json.dump(matrix, matrix_file)
            matrix_file_path = matrix_file.name
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.json') as pad_filter_file:
            json.dump(pad_filter, pad_filter_file)
            pad_filter_file_path = pad_filter_file.name
        script_path = os.path.join('src', 'processors', 'groups', 'process_groups_json.py')
        cmd = [sys.executable, script_path, json_path, output_folder]
        if self.config.groups_exporter.trim_silence:
            cmd.append('--trim_silence')
        if self.config.groups_exporter.normalize:
            cmd.append('--normalize')
        if self.config.groups_exporter.enable_matrix:
            cmd.extend(['--matrix_json', matrix_file_path])
        if self.config.groups_exporter.filter_pads:
            cmd.append('--filter_pads')
            cmd.extend(['--filter_pads_json', pad_filter_file_path])
        if self.config.groups_exporter.fill_blanks:
            cmd.append('--fill_blanks')
        if self.config.groups_exporter.fill_blanks_path:
            cmd.extend(['--fill_blanks_path', self.config.groups_exporter.fill_blanks_path])
        if self.config.groups_exporter.sample_rate:
            cmd.extend(['--sample_rate', self.config.groups_exporter.sample_rate])
        if self.config.groups_exporter.bit_depth:
            cmd.extend(['--bit_depth', self.config.groups_exporter.bit_depth])
        if self.config.groups_exporter.include_preview:
            cmd.append('--include_preview')
        self.log_output.append(f"Running: {' '.join(cmd)}")
        self.show_loading('Exporting groups...')
        self.run_subprocess(cmd)

    def run_subprocess(self, cmd):
        self.run_build_btn.setEnabled(False)
        self.run_process_btn.setEnabled(False)
        self.worker = WorkerThread(cmd)
        self.worker.output_signal.connect(self.log_output.append)
        self.worker.finished_signal.connect(self.on_subprocess_finished)
        self.worker.start()

    def on_subprocess_finished(self, code):
        if code == 0:
            self.log_output.append('Done\n')
            # Switch to Export groups tab if Process groups just finished
            if self.tabs.currentIndex() == 0:
                self.tabs.setCurrentIndex(1)
        else:
            self.log_output.append('Operation cancelled by user.\n')
        self.run_build_btn.setEnabled(True)
        self.run_process_btn.setEnabled(True)
        self.hide_loading()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = GroupsExporterGUI()
    gui.show()
    sys.exit(app.exec())
