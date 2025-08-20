import json
import os
import subprocess
import sys
import tempfile

from PyQt6 import QtCore, QtGui, QtWidgets

from components.version_label import VersionLabel
from utils import config_utils
from utils.bundle_utils import get_bundled_path

from models.config import Config


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


class PreviewsExporterGUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("img/logos/previews.png")))
        self.setWindowTitle('Previews Exporter')
        self.setGeometry(100, 100, 700, 800)
        self.config: Config = config_utils.load_config()
        self.worker = None
        self.progress_dialog = None
        self.cancelled = False
        self.init_ui()
        self.load_config_to_ui()
        default_json = os.path.abspath('./out/previews.json')
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
        build_group = QtWidgets.QGroupBox('Step 1: Build JSON from Previews')
        build_form_layout = QtWidgets.QFormLayout()

        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder_btn = QtWidgets.QPushButton('Choose')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_form_layout.addRow('Output folder:', output_folder_layout)

        self.run_build_btn = QtWidgets.QPushButton('Run build_previews_json.py')
        self.run_build_btn.clicked.connect(self.run_build_json)
        build_form_layout.addRow('', self.run_build_btn)

        build_group.setLayout(build_form_layout)
        build_layout.addWidget(build_group)
        self.tab_build.setLayout(build_layout)
        self.tabs.addTab(self.tab_build, 'Build JSON')

        # --- Tab 2: Process Previews ---
        self.tab_process = QtWidgets.QWidget()
        process_layout = QtWidgets.QVBoxLayout()
        process_group = QtWidgets.QGroupBox('Step 2: Process Previews')
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
        options_layout.addWidget(self.trim_silence)
        options_layout.addWidget(self.normalize)
        options_layout.addWidget(QtWidgets.QLabel('Sample rate:'))
        options_layout.addWidget(self.sample_rate)
        options_layout.addWidget(QtWidgets.QLabel('Bit depth:'))
        options_layout.addWidget(self.bit_depth)
        options_group.setLayout(options_layout)
        process_form_layout.addRow(options_group)

        self.run_process_btn = QtWidgets.QPushButton('Run process_previews_json.py')
        self.run_process_btn.clicked.connect(self.run_process_py)
        process_form_layout.addRow('', self.run_process_btn)

        process_group.setLayout(process_form_layout)
        process_layout.addWidget(process_group)
        self.tab_process.setLayout(process_layout)
        self.tabs.addTab(self.tab_process, 'Process Previews')

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
        # The keys here should match the attribute names in PreviewsExporterConfig
        for widget, key in [
            (self.output_folder, 'output_folder'),
            (self.json_path, 'json_path'),
            (self.proc_output_folder, 'proc_output_folder'),
            (self.trim_silence, 'trim_silence'),
            (self.normalize, 'normalize'),
            (self.sample_rate, 'sample_rate'),
            (self.bit_depth, 'bit_depth'),
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(lambda val, k=key: self.on_config_changed(k, val))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))

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
        script_path = os.path.join('src', 'processors', 'previews', 'build_previews_json.py')
        cmd = [sys.executable, script_path, output_folder]
        self.log_output.append(f"Running: {' '.join(cmd)}")
        self.show_loading('Building previews JSON...')
        self.run_subprocess(cmd)
        json_path = os.path.join(output_folder, 'previews.json')
        self.json_path.setText(json_path)
        self.proc_output_folder.setText(os.path.abspath('./out/previews'))

    def run_process_py(self):
        json_path = self.json_path.text().strip()
        output_folder = self.proc_output_folder.text().strip()
        script_path = os.path.join('src', 'processors', 'previews', 'process_previews_json.py')
        cmd = [sys.executable, script_path, json_path, output_folder]
        if self.config.previews_exporter.trim_silence:
            cmd.append('--trim_silence')
        if self.config.previews_exporter.normalize:
            cmd.append('--normalize')
        if self.config.previews_exporter.sample_rate:
            cmd.extend(['--sample_rate', self.config.previews_exporter.sample_rate])
        if self.config.previews_exporter.bit_depth:
            cmd.extend(['--bit_depth', self.config.previews_exporter.bit_depth])
        self.log_output.append(f"Running: {' '.join(cmd)}")
        self.show_loading('Exporting previews...')
        self.run_subprocess(cmd)

    def run_subprocess(self, cmd):
        self.run_build_btn.setEnabled(False)
        self.run_process_btn.setEnabled(False)
        self.worker = WorkerThread(cmd)
        self.worker.output_signal.connect(self.log_output.append)
        self.worker.finished_signal.connect(self.on_subprocess_finished)
        self.worker.start()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = PreviewsExporterGUI()
    gui.show()
    sys.exit(app.exec())
