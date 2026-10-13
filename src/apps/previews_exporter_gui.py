import os
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QMessageBox

from components.ansi_text_edit import AnsiTextEdit
from components.exporter_workflow import ExporterWorkflow
from components.exporter_layout import ExpandableOptions, activity_panel, audio_options, finish_layout
from components.bottom_banner import BottomBanner
from components.no_wheel_combo_box import NoWheelComboBox
from components.resizable_log_splitter import ResizableLogSplitter
from models.config import Config
from processors.previews.build_previews_json import PreviewsJsonBuilder
from processors.previews.process_previews_json import PreviewsProcessor
from utils import config_utils
from utils.bundle_utils import get_bundled_path
from utils.style_utils import apply_style


class PreviewsExporterGUI(ExporterWorkflow, QtWidgets.QDialog):
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
        step1_label = QtWidgets.QLabel("Find your library previews")
        step1_label.setStyleSheet("font-weight: bold;")
        build_layout.addWidget(step1_label)

        source_note = QtWidgets.QLabel("Find previews in the Native Instruments libraries installed on this computer.")
        source_note.setWordWrap(True)
        build_layout.addWidget(source_note)

        # Scrollable content
        scroll_content_build = QtWidgets.QWidget()
        build_form_layout = QtWidgets.QFormLayout(scroll_content_build)

        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder.setToolTip('Select the folder where the generated JSON file will be saved.')
        self.output_folder.setPlaceholderText('e.g., C:/Users/YourName/Documents/NITools/PreviewsJSON')
        self.output_folder_btn = QtWidgets.QPushButton('Choose')
        self.output_folder_btn.setToolTip('Browse for the output folder.')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_form_layout.addRow('Index folder', output_folder_layout)

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
        export_note = QtWidgets.QLabel('Choose an index, destination and audio settings.')
        export_note.setWordWrap(True)
        export_layout.addWidget(export_note)

        # Scrollable content for Tab 2
        scroll_content_export = QtWidgets.QWidget()
        scroll_content_export_layout = QtWidgets.QVBoxLayout()

        export_form_layout = QtWidgets.QFormLayout()

        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip('Select the JSON file generated in Step 1 (e.g., all_previews.json).')
        self.json_path.setPlaceholderText('e.g., C:/Users/YourName/Documents/NITools/PreviewsJSON/all_previews.json')
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.setToolTip('Browse for the JSON file.')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        export_form_layout.addRow('Index file', json_path_layout)

        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip('Select the folder where the processed preview samples will be exported.')
        self.proc_output_folder.setPlaceholderText('e.g., C:/Users/YourName/Documents/NITools/ExportedPreviews')
        self.proc_output_folder_btn = QtWidgets.QPushButton('Choose')
        self.proc_output_folder_btn.setToolTip('Browse for the output folder.')
        self.proc_output_folder_btn.clicked.connect(self.choose_proc_output_folder)
        proc_output_folder_layout = QtWidgets.QHBoxLayout()
        proc_output_folder_layout.addWidget(self.proc_output_folder)
        proc_output_folder_layout.addWidget(self.proc_output_folder_btn)
        export_form_layout.addRow('Export folder', proc_output_folder_layout)

        # --- Options group ---
        self.skip_existing = QtWidgets.QCheckBox('Skip existing files')
        self.skip_existing.setToolTip('If checked, samples that already exist in the output folder will be skipped.')
        self.trim_silence = QtWidgets.QCheckBox('Trim silence')
        self.trim_silence.setToolTip('If checked, leading and trailing silence will be removed from samples.')
        self.normalize = QtWidgets.QCheckBox('Normalize')
        self.normalize.setToolTip('Normalize sample peaks to just below full scale. Silent samples are left unchanged.')
        self.sample_rate = NoWheelComboBox()
        self.sample_rate.addItem('Keep Original', '')
        self.sample_rate.addItem('44100 Hz', '44100')
        self.sample_rate.addItem('48000 Hz (Recommended)', '48000')
        self.sample_rate.setToolTip('Sample rate for export.')
        self.bit_depth = NoWheelComboBox()
        self.bit_depth.addItem('Keep Original', '')
        self.bit_depth.addItem('8-bit', '8')
        self.bit_depth.addItem('16-bit (Recommended)', '16')
        self.bit_depth.addItem('24-bit', '24')
        self.bit_depth.addItem('32-bit (Warning: SP 404 MK2 does not read 32-bit)', '32')
        self.bit_depth.setCurrentIndex(2)
        self.bit_depth.setToolTip('Bit depth for export.')
        export_form_layout.addRow(audio_options(self))

        # --- Skip Options group ---
        skip_content_group = QtWidgets.QGroupBox('Skip Content')
        skip_content_layout = QtWidgets.QVBoxLayout()
        self.skip_maschine_folders = QtWidgets.QCheckBox('Skip Maschine group previews (.mxgrp)')
        self.skip_maschine_folders.setToolTip('Skip preview files ending with .mxgrp.ogg.')
        self.skip_battery_kits = QtWidgets.QCheckBox('Skip Battery kits (.nbkt)')
        self.skip_battery_kits.setToolTip('If checked, files ending with .nbkt.ogg will be skipped.')
        self.skip_native_browser_preview_library = QtWidgets.QCheckBox('Skip Native Browser Preview Library')
        self.skip_native_browser_preview_library.setToolTip("If checked, previews from the 'Native Browser Preview Library' will be skipped completely.")
        self.find_real_instrument_folder = QtWidgets.QCheckBox('Use instrument names for Native Browser previews')
        self.find_real_instrument_folder.setToolTip('If checked, try to find the real instrument name for the "Native Browser Preview Library" previews.')
        skip_content_layout.addWidget(self.skip_maschine_folders)
        skip_content_layout.addWidget(self.skip_battery_kits)
        skip_content_layout.addWidget(self.skip_native_browser_preview_library)
        skip_content_layout.addWidget(self.find_real_instrument_folder)
        skip_content_group.setLayout(skip_content_layout)
        self.advanced_options = ExpandableOptions('Content options', [skip_content_group],
            [self.skip_maschine_folders, self.skip_battery_kits, self.skip_native_browser_preview_library, self.find_real_instrument_folder])
        export_form_layout.addRow(self.advanced_options)

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
        self.log_output = AnsiTextEdit(self.config.max_log_lines)
        self.log_output.setReadOnly(True)

        # Create a splitter to make the log_output resizable
        self.activity_panel = activity_panel(self)
        splitter = ResizableLogSplitter(self.config, self.tabs, self.activity_panel)
        main_layout.addWidget(splitter)

        # --- Bottom banner ---
        self.bottom_banner = BottomBanner(self.config.previews_exporter.show_terminal)
        self.bottom_banner.terminal_toggled.connect(self.toggle_terminal_visibility)
        main_layout.addWidget(self.bottom_banner)

        self.setLayout(main_layout)
        finish_layout(self, 'Library Previews', 'Collect and convert your installed library previews.')
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
        if self.stop_before_close(event):
            return
        # Save current window size to config
        self.config.previews_exporter.width = self.width()
        self.config.previews_exporter.height = self.height()
        config_utils.save_config(self.config)
        super().closeEvent(event)

    def toggle_terminal_visibility(self, state):
        self.activity_panel.setVisible(state)
        self.config.previews_exporter.show_terminal = state
        config_utils.save_config(self.config)


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
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(lambda _, k=key, w=widget: self.on_config_changed(k, w.currentData()))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))
            elif isinstance(widget, QtWidgets.QPushButton) and widget.isCheckable():
                widget.toggled.connect(lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked()))

    def on_config_changed(self, key, value):
        # Update the specific attribute in the previews_exporter sub-model
        setattr(self.config.previews_exporter, key, value)
        config_utils.save_config(self.config)

    def normalize_path(self, path: str) -> str:
        return os.path.normpath(path) if path else path

    def load_config_to_ui(self):
        c = self.config.previews_exporter
        self.output_folder.setText(self.normalize_path(c.output_folder))
        self.json_path.setText(self.normalize_path(c.json_path))
        self.proc_output_folder.setText(self.normalize_path(c.proc_output_folder))
        self.trim_silence.setChecked(c.trim_silence)
        self.normalize.setChecked(c.normalize)
        saved_sample_rate = c.sample_rate if c.sample_rate else ''
        for index in range(self.sample_rate.count()):
            if self.sample_rate.itemData(index) == saved_sample_rate:
                self.sample_rate.setCurrentIndex(index)
                break
        else:
            self.sample_rate.setCurrentIndex(0)

        saved_bit_depth = c.bit_depth if c.bit_depth else ''
        for index in range(self.bit_depth.count()):
            if self.bit_depth.itemData(index) == saved_bit_depth:
                self.bit_depth.setCurrentIndex(index)
                break
        else:
            self.bit_depth.setCurrentIndex(0)
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
        self.find_real_instrument_folder.setEnabled(enabled and not self.skip_native_browser_preview_library.isChecked())

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

        json_path = os.path.join(output_folder, 'all_previews.json')
        self.json_path.setText(json_path)
        self.last_built_json_path = json_path
        self.run_worker(builder.run, {}, logger_name="PreviewsBuilder")

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
        sample_rate_value = self.sample_rate.currentData()
        if sample_rate_value:
            try:
                sample_rate_val = int(sample_rate_value)
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Sample rate must be a valid value.")
                return

        bit_depth_val = None
        bit_depth_value = self.bit_depth.currentData()
        if bit_depth_value:
            try:
                bit_depth_val = int(bit_depth_value)
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Bit depth must be a valid value.")
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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = PreviewsExporterGUI()
    gui.show()
    sys.exit(app.exec())
