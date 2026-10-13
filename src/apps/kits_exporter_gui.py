import os
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QMessageBox

from components.ansi_text_edit import AnsiTextEdit
from components.exporter_workflow import ExporterWorkflow
from components.exporter_layout import ExpandableOptions, activity_panel, audio_options, finish_layout
from components.bottom_banner import BottomBanner
from components.matrix_editor import MatrixEditor
from components.no_wheel_combo_box import NoWheelComboBox
from components.pad_filter_editor import PadFilterEditor
from components.resizable_log_splitter import ResizableLogSplitter
from models.config import Config
from processors.kits.build_kits_json import KitsJsonBuilder
from processors.kits.process_kits_json import KitsProcessor
from utils import config_utils
from utils.bundle_utils import get_bundled_path
from utils.style_utils import apply_style


class KitsExporterGUI(ExporterWorkflow, QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QtGui.QIcon(get_bundled_path("resources/icons/kits.png")))
        self.setWindowTitle("NITools - Kits Exporter")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        self.config: Config = config_utils.load_config()
        apply_style(self.config.style)
        self.worker = None
        self.active_operation = None
        self.progress_dialog = None
        self.cancelled = False
        self.has_output = False
        self.last_built_json_path = None
        self.init_ui()
        self.load_config_to_ui()

        if self.config.kits_exporter.width > 0 and self.config.kits_exporter.height > 0:
            self.resize(self.config.kits_exporter.width, self.config.kits_exporter.height)

        if self.json_path.text().strip() and os.path.isfile(self.json_path.text().strip()):
            self.tabs.setCurrentIndex(1)

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget()

        # ── Tab 1: Process kits ──────────────────────────────────────────────
        self.tab_process = QtWidgets.QWidget()
        process_layout = QtWidgets.QVBoxLayout()

        step1_label = QtWidgets.QLabel("Choose your Battery library")
        step1_label.setStyleSheet("font-weight: bold;")
        process_layout.addWidget(step1_label)

        scroll_content = QtWidgets.QWidget()
        build_layout = QtWidgets.QFormLayout(scroll_content)

        self.input_folder = QtWidgets.QLineEdit()
        self.input_folder.setToolTip("Select the folder containing your .nbkt Battery kit files.")
        self.input_folder.setPlaceholderText(
            "e.g., C:/Users/YourName/Documents/Native Instruments/Battery 4/Presets"
        )
        self.input_folder_btn = QtWidgets.QPushButton("Choose")
        self.input_folder_btn.clicked.connect(self.choose_input_folder)
        input_folder_layout = QtWidgets.QHBoxLayout()
        input_folder_layout.addWidget(self.input_folder)
        input_folder_layout.addWidget(self.input_folder_btn)
        build_layout.addRow("Library folder", input_folder_layout)

        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder.setToolTip("Select the folder where the generated JSON and optional TXT files will be saved.")
        self.output_folder.setPlaceholderText("e.g., C:/Users/YourName/Documents/NITools/KitsJSON")
        self.output_folder_btn = QtWidgets.QPushButton("Choose")
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_layout.addRow("Index folder", output_folder_layout)

        self.generate_txt = QtWidgets.QCheckBox("Generate TXT files")
        self.generate_txt.setToolTip(
            "If checked, a .txt file is generated for each kit listing the decoded cell numbers and exact sample paths — useful for debugging."
        )
        build_layout.addRow("", self.generate_txt)

        scroll_area_process = QtWidgets.QScrollArea()
        scroll_area_process.setWidgetResizable(True)
        scroll_area_process.setWidget(scroll_content)
        process_layout.addWidget(scroll_area_process)

        self.run_build_btn = QtWidgets.QPushButton("Process Kits")
        self.run_build_btn.clicked.connect(self.run_build_json)
        self.run_build_btn.setProperty("class", "accent")
        process_layout.addWidget(self.run_build_btn)

        self.tab_process.setLayout(process_layout)
        self.tabs.addTab(self.tab_process, "Process Kits")

        # ── Tab 2: Export kits ───────────────────────────────────────────────
        self.tab_export = QtWidgets.QWidget()
        export_layout = QtWidgets.QVBoxLayout()

        path_note = QtWidgets.QLabel(
            "Choose an index, destination and audio settings."
        )
        path_note.setWordWrap(True)
        export_layout.addWidget(path_note)

        scrollable_content_export = QtWidgets.QWidget()
        scrollable_content_export_layout = QtWidgets.QVBoxLayout()

        export_form_layout = QtWidgets.QFormLayout()

        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip("Select the JSON file generated in Step 1 (e.g., all_kits.json).")
        self.json_path.setPlaceholderText(
            "e.g., C:/Users/YourName/Documents/NITools/KitsJSON/all_kits.json"
        )
        self.json_path_btn = QtWidgets.QPushButton("Choose")
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        export_form_layout.addRow("Index file", json_path_layout)

        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip(
            "Select the folder where the exported kit samples will be saved."
        )
        self.proc_output_folder.setPlaceholderText(
            "e.g., C:/Users/YourName/Documents/NITools/ExportedKits"
        )
        self.proc_output_folder_btn = QtWidgets.QPushButton("Choose")
        self.proc_output_folder_btn.clicked.connect(self.choose_proc_output_folder)
        proc_output_folder_layout = QtWidgets.QHBoxLayout()
        proc_output_folder_layout.addWidget(self.proc_output_folder)
        proc_output_folder_layout.addWidget(self.proc_output_folder_btn)
        export_form_layout.addRow("Export folder", proc_output_folder_layout)

        # Options group
        self.skip_existing = QtWidgets.QCheckBox("Skip existing files")
        self.skip_existing.setToolTip(
            "If checked, samples that already exist in the output folder will be skipped."
        )
        self.trim_silence = QtWidgets.QCheckBox("Trim silence")
        self.trim_silence.setToolTip("If checked, leading and trailing silence will be removed from samples.")
        self.normalize = QtWidgets.QCheckBox("Normalize")
        self.normalize.setToolTip("Normalize sample peaks to just below full scale. Silent samples are left unchanged.")
        self.include_preview = QtWidgets.QCheckBox("Include preview samples")
        self.include_preview.setToolTip("If checked, an existing kit preview is converted to WAV and included.")
        self.sample_rate = NoWheelComboBox()
        self.sample_rate.addItem('Keep Original', '')
        self.sample_rate.addItem('44100 Hz', '44100')
        self.sample_rate.addItem('48000 Hz (Recommended)', '48000')
        self.sample_rate.setToolTip(
            "Sample rate for export."
        )
        self.bit_depth = NoWheelComboBox()
        self.bit_depth.addItem('Keep Original', '')
        self.bit_depth.addItem('8-bit', '8')
        self.bit_depth.addItem('16-bit (Recommended)', '16')
        self.bit_depth.addItem('24-bit', '24')
        self.bit_depth.addItem('32-bit (Warning: SP 404 MK2 does not read 32-bit)', '32')
        self.bit_depth.setCurrentIndex(2)
        self.bit_depth.setToolTip(
            "Bit depth for export."
        )
        export_form_layout.addRow(audio_options(self))

        # Pad Reorder Matrix group
        matrix_group = QtWidgets.QGroupBox("Pad Reorder Matrix (4x4)")
        matrix_layout = QtWidgets.QVBoxLayout()
        self.enable_matrix = QtWidgets.QCheckBox("Enable matrix reorder")
        self.enable_matrix.setToolTip("Reorder cells 1–16 using this matrix. Cells above 16 keep their numbers.")
        self.matrix_toggle_btn = QtWidgets.QPushButton("Show Matrix")
        self.matrix_toggle_btn.setToolTip("Toggle the visibility of the pad reorder matrix editor.")
        self.matrix_editor = MatrixEditor()
        self.matrix_editor.setVisible(False)
        self.matrix_toggle_btn.setCheckable(True)
        self.matrix_toggle_btn.setChecked(False)
        self.matrix_toggle_btn.toggled.connect(
            lambda checked: self.matrix_editor.setVisible(checked)
        )
        self.matrix_toggle_btn.toggled.connect(
            lambda checked: self.matrix_toggle_btn.setText("Hide Matrix" if checked else "Show Matrix")
        )
        matrix_layout.addWidget(self.enable_matrix)
        matrix_layout.addWidget(self.matrix_toggle_btn)
        matrix_layout.addWidget(self.matrix_editor)
        matrix_group.setLayout(matrix_layout)

        # Pad Filter group
        pad_filter_group = QtWidgets.QGroupBox("Pad Filter Keywords")
        pad_filter_layout = QtWidgets.QVBoxLayout()
        self.filter_pads = QtWidgets.QCheckBox("Enable pad filtering")
        self.filter_pads.setToolTip(
            "If checked, only kits where every pad matches at least one of its keywords will be included."
        )
        self.pad_filter_toggle_btn = QtWidgets.QPushButton("Show Pad Filter Editor")
        self.pad_filter_toggle_btn.setToolTip("Toggle the visibility of the pad filter editor.")
        self.pad_filter_editor = PadFilterEditor()
        self.pad_filter_editor.setVisible(False)
        self.pad_filter_toggle_btn.setCheckable(True)
        self.pad_filter_toggle_btn.setChecked(False)
        self.pad_filter_toggle_btn.toggled.connect(
            lambda checked: self.pad_filter_editor.setVisible(checked)
        )
        self.pad_filter_toggle_btn.toggled.connect(
            lambda checked: self.pad_filter_toggle_btn.setText(
                "Hide Pad Filter Editor" if checked else "Show Pad Filter Editor"
            )
        )
        pad_filter_layout.addWidget(self.filter_pads)
        pad_filter_layout.addWidget(self.pad_filter_toggle_btn)
        pad_filter_layout.addWidget(self.pad_filter_editor)
        pad_filter_group.setLayout(pad_filter_layout)

        self.advanced_options = ExpandableOptions('Pad options', [matrix_group, pad_filter_group], [self.enable_matrix, self.filter_pads])
        export_form_layout.addRow(self.advanced_options)

        scrollable_content_export_layout.addLayout(export_form_layout)
        scrollable_content_export.setLayout(scrollable_content_export_layout)
        scroll_area_export = QtWidgets.QScrollArea()
        scroll_area_export.setWidgetResizable(True)
        scroll_area_export.setWidget(scrollable_content_export)
        export_layout.addWidget(scroll_area_export)

        self.run_process_btn = QtWidgets.QPushButton("Export Kits")
        self.run_process_btn.clicked.connect(self.run_process_py)
        self.run_process_btn.setProperty("class", "accent")
        export_layout.addWidget(self.run_process_btn)
        self.tab_export.setLayout(export_layout)
        self.tabs.addTab(self.tab_export, "Export Kits")

        # Log/output
        self.log_output = AnsiTextEdit(self.config.max_log_lines)
        self.log_output.setReadOnly(True)

        self.activity_panel = activity_panel(self)
        splitter = ResizableLogSplitter(self.config, self.tabs, self.activity_panel)
        main_layout.addWidget(splitter)

        self.bottom_banner = BottomBanner(self.config.kits_exporter.show_terminal)
        self.bottom_banner.terminal_toggled.connect(self.toggle_terminal_visibility)
        main_layout.addWidget(self.bottom_banner)

        self.setLayout(main_layout)
        finish_layout(self, 'Battery Kits', 'Export your Battery cells and sample layers.')
        self.set_step2_enabled(False)
        self.json_path.textChanged.connect(self.on_json_path_changed)
        self.setup_config_signals()

        self.enable_matrix.stateChanged.connect(self._update_matrix_editor_state)
        self.filter_pads.stateChanged.connect(self._update_pad_filter_editor_state)
        self.on_json_path_changed()
        self.toggle_terminal_visibility(self.config.kits_exporter.show_terminal)

    # ── Config persistence ───────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.stop_before_close(event):
            return
        self.config.kits_exporter.width = self.width()
        self.config.kits_exporter.height = self.height()
        config_utils.save_config(self.config)
        super().closeEvent(event)

    def toggle_terminal_visibility(self, state):
        self.activity_panel.setVisible(state)
        self.config.kits_exporter.show_terminal = state
        config_utils.save_config(self.config)

    def setup_config_signals(self):
        for widget, key in [
            (self.input_folder, "input_folder"),
            (self.output_folder, "output_folder"),
            (self.generate_txt, "generate_txt"),
            (self.json_path, "json_path"),
            (self.proc_output_folder, "proc_output_folder"),
            (self.trim_silence, "trim_silence"),
            (self.normalize, "normalize"),
            (self.sample_rate, "sample_rate"),
            (self.bit_depth, "bit_depth"),
            (self.include_preview, "include_preview"),
            (self.skip_existing, "skip_existing"),
            (self.bottom_banner.show_terminal_button, "show_terminal"),
            (self.enable_matrix, "enable_matrix"),
            (self.filter_pads, "filter_pads"),
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(lambda val, k=key: self.on_config_changed(k, val))
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(lambda _, k=key, w=widget: self.on_config_changed(k, w.currentData()))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(
                    lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked())
                )
            elif isinstance(widget, QtWidgets.QPushButton) and widget.isCheckable():
                widget.toggled.connect(
                    lambda val, k=key, w=widget: self.on_config_changed(k, w.isChecked())
                )

        self.matrix_editor.matrix_changed.connect(self.on_matrix_config_changed)
        self.pad_filter_editor.pad_filter_changed.connect(self.on_pad_filter_config_changed)

    def on_config_changed(self, key, value):
        setattr(self.config.kits_exporter, key, value)
        config_utils.save_config(self.config)

    def on_matrix_config_changed(self):
        self.config.kits_exporter.matrix_config = self.matrix_editor.get_matrix()
        config_utils.save_config(self.config)

    def on_pad_filter_config_changed(self):
        self.config.kits_exporter.pad_filter_config = self.pad_filter_editor.get_pad_filter()
        config_utils.save_config(self.config)

    def normalize_path(self, path: str) -> str:
        return os.path.normpath(path) if path else path

    def load_config_to_ui(self):
        c = self.config.kits_exporter
        self.input_folder.setText(self.normalize_path(c.input_folder))
        self.output_folder.setText(self.normalize_path(c.output_folder))
        self.generate_txt.setChecked(c.generate_txt)
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
        self.enable_matrix.setChecked(c.enable_matrix)
        self.matrix_editor.set_matrix(self.config.kits_exporter.matrix_config)
        self.filter_pads.setChecked(c.filter_pads)
        self.pad_filter_editor.set_pad_filter(self.config.kits_exporter.pad_filter_config)
        self.include_preview.setChecked(c.include_preview)
        self.bottom_banner.show_terminal_button.setChecked(c.show_terminal)

    # ── UI state helpers ─────────────────────────────────────────────────────

    def _update_matrix_editor_state(self):
        enabled = bool(self.json_path.text().strip()) and self.enable_matrix.isChecked()
        self.matrix_editor.setEnabled(enabled)
        self.matrix_toggle_btn.setEnabled(enabled)
        self.matrix_editor.setVisible(self.matrix_toggle_btn.isChecked() and enabled)

    def _update_pad_filter_editor_state(self):
        enabled = bool(self.json_path.text().strip()) and self.filter_pads.isChecked()
        self.pad_filter_editor.setEnabled(enabled)
        self.pad_filter_toggle_btn.setEnabled(enabled)
        self.pad_filter_editor.setVisible(self.pad_filter_toggle_btn.isChecked() and enabled)

    def set_step2_enabled(self, enabled):
        widgets = [
            self.proc_output_folder, self.proc_output_folder_btn,
            self.trim_silence, self.normalize,
            self.run_process_btn, self.sample_rate, self.bit_depth,
            self.include_preview, self.skip_existing,
        ]
        for w in widgets:
            w.setEnabled(enabled)
        self.enable_matrix.setEnabled(enabled)
        self.filter_pads.setEnabled(enabled)
        self._update_matrix_editor_state()
        self._update_pad_filter_editor_state()

    def on_json_path_changed(self):
        enabled = bool(self.json_path.text().strip())
        self.set_step2_enabled(enabled)
        self._update_matrix_editor_state()
        self._update_pad_filter_editor_state()

    # ── Folder/file choosers ─────────────────────────────────────────────────

    def choose_input_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Input Folder", self.input_folder.text()
        )
        if folder:
            self.input_folder.setText(folder)

    def choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.output_folder.text()
        )
        if folder:
            self.output_folder.setText(folder)

    def choose_json_file(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select JSON File", self.json_path.text(), "JSON Files (*.json)"
        )
        if file:
            self.json_path.setText(file)

    def choose_proc_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.proc_output_folder.text()
        )
        if folder:
            self.proc_output_folder.setText(folder)

    # ── Workers ──────────────────────────────────────────────────────────────

    def run_build_json(self):
        input_folder = self.input_folder.text().strip()
        output_folder = self.output_folder.text().strip()
        generate_txt = self.generate_txt.isChecked()

        if not input_folder:
            QMessageBox.warning(self, "Input Error", "Please select an input folder for .nbkt files.")
            return
        if not output_folder:
            QMessageBox.warning(self, "Input Error", "Please select an output folder for the JSON file.")
            return

        builder = KitsJsonBuilder(
            input_folder=input_folder,
            output_folder=output_folder,
            generate_txt=generate_txt,
        )
        self.log_output.append(f"Starting JSON build process for input folder: {input_folder}")
        self.show_loading("Processing kits...")

        json_path = os.path.join(output_folder, "all_kits.json")
        self.json_path.setText(json_path)
        self.last_built_json_path = json_path
        self.run_worker(builder.run, {}, logger_name="KitsBuilder")

    def run_process_py(self):
        json_path = self.json_path.text().strip()
        output_folder = self.proc_output_folder.text().strip()

        if not json_path or not os.path.exists(json_path):
            QMessageBox.warning(self, "Input Error", "Please select a valid JSON file.")
            return
        if not output_folder:
            QMessageBox.warning(self, "Input Error", "Please select an output folder for the exported kits.")
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

        processor = KitsProcessor(
            json_path=json_path,
            output_folder=output_folder,
            trim_silence=self.config.kits_exporter.trim_silence,
            normalize=self.config.kits_exporter.normalize,
            sample_rate=sample_rate_val,
            bit_depth=bit_depth_val,
            matrix=self.matrix_editor.get_matrix() if self.config.kits_exporter.enable_matrix else None,
            enable_matrix=self.config.kits_exporter.enable_matrix,
            filter_pads=self.config.kits_exporter.filter_pads,
            pad_filter=self.pad_filter_editor.get_pad_filter() if self.config.kits_exporter.filter_pads else None,
            include_preview=self.config.kits_exporter.include_preview,
            skip_existing=self.config.kits_exporter.skip_existing,
        )
        self.log_output.append(f"Starting kits export process for JSON: {json_path}")
        self.show_loading("Exporting kits...")
        self.run_worker(processor.run, {}, logger_name="KitsProcessor")


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    gui = KitsExporterGUI()
    gui.show()
    sys.exit(app.exec())
