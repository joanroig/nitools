from processors.groups.build_groups_json import GroupsJsonBuilder
from utils.style_utils import apply_style
from utils.bundle_utils import get_bundled_path
from utils import config_utils
from processors.groups.process_groups_json import GroupsProcessor
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


class GroupsExporterGUI(ExporterWorkflow, QtWidgets.QDialog):

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
        self.active_operation = None
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
        step1_label = QtWidgets.QLabel("Choose your Maschine library")
        step1_label.setStyleSheet("font-weight: bold;")
        process_layout.addWidget(step1_label)

        # Scrollable content
        scroll_content = QtWidgets.QWidget()
        build_layout = QtWidgets.QFormLayout(scroll_content)

        self.input_folder = QtWidgets.QLineEdit()
        self.input_folder.setToolTip('Select the folder containing your .mxgrp files.')
        self.input_folder.setPlaceholderText('e.g., C:/Users/YourName/Documents/Native Instruments/Maschine 2/Groups')
        self.input_folder_btn = QtWidgets.QPushButton('Choose')
        self.input_folder_btn.setToolTip('Browse for the input folder.')
        self.input_folder_btn.clicked.connect(self.choose_input_folder)
        input_folder_layout = QtWidgets.QHBoxLayout()
        input_folder_layout.addWidget(self.input_folder)
        input_folder_layout.addWidget(self.input_folder_btn)
        build_layout.addRow('Library folder', input_folder_layout)

        self.output_folder = QtWidgets.QLineEdit()
        self.output_folder.setToolTip('Select the folder where the generated JSON and optional TXT files will be saved.')
        self.output_folder.setPlaceholderText('e.g., C:/Users/YourName/Documents/NITools/GroupsJSON')
        self.output_folder_btn = QtWidgets.QPushButton('Choose')
        self.output_folder_btn.setToolTip('Browse for the output folder.')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        output_folder_layout = QtWidgets.QHBoxLayout()
        output_folder_layout.addWidget(self.output_folder)
        output_folder_layout.addWidget(self.output_folder_btn)
        build_layout.addRow('Index folder', output_folder_layout)

        self.generate_txt = QtWidgets.QCheckBox('Generate TXT files')
        self.generate_txt.setToolTip('Save decoded Sound names, sample references and source offsets for each group.')
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
        export_note = QtWidgets.QLabel('Choose an index, destination and audio settings.')
        export_note.setWordWrap(True)
        export_layout.addWidget(export_note)

        # Scrollable content for Tab 2
        scrollable_content_export = QtWidgets.QWidget()
        scrollable_content_export_layout = QtWidgets.QVBoxLayout()

        export_form_layout = QtWidgets.QFormLayout()
        self.json_path = QtWidgets.QLineEdit()
        self.json_path.setToolTip('Select the JSON file generated in Step 1 (e.g., all_groups.json).')
        self.json_path.setPlaceholderText('e.g., C:/Users/YourName/Documents/NITools/GroupsJSON/all_groups.json')
        self.json_path_btn = QtWidgets.QPushButton('Choose')
        self.json_path_btn.setToolTip('Browse for the JSON file.')
        self.json_path_btn.clicked.connect(self.choose_json_file)
        json_path_layout = QtWidgets.QHBoxLayout()
        json_path_layout.addWidget(self.json_path)
        json_path_layout.addWidget(self.json_path_btn)
        export_form_layout.addRow('Index file', json_path_layout)
        self.proc_output_folder = QtWidgets.QLineEdit()
        self.proc_output_folder.setToolTip('Select the folder where the processed group samples will be exported.')
        self.proc_output_folder.setPlaceholderText('e.g., C:/Users/YourName/Documents/NITools/ExportedGroups')
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
        self.include_preview = QtWidgets.QCheckBox('Include preview samples')
        self.include_preview.setToolTip('Include the existing group preview as a WAV file when available.')
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

        render_group = QtWidgets.QGroupBox('Instrument rendering · experimental')
        render_layout = QtWidgets.QFormLayout(render_group)
        self.render_instruments = QtWidgets.QCheckBox('Render external VST2 instruments')
        self.render_instruments.setToolTip('Render one note using the instrument state saved in the original kit. Requires Windows and the matching installed VST2 plug-in and content.')
        render_layout.addRow(self.render_instruments)
        self.render_maschine = QtWidgets.QCheckBox('Render internal instruments with Maschine 3')
        self.render_maschine.setToolTip('Requires the installed Maschine 3 VST3. Kits can be prepared automatically. Uses each pad’s saved pitch and the kit’s effects.')
        render_layout.addRow(self.render_maschine)
        render_help = QtWidgets.QLabel('Windows 64-bit. External VST2 rendering loads saved presets directly. Maschine rendering also supports internal synths and automatically caches kits for later exports. Installed instruments and content are required.')
        render_help.setWordWrap(True)
        render_layout.addRow(render_help)
        self.render_settings = QtWidgets.QWidget()
        render_form = QtWidgets.QFormLayout(self.render_settings)
        render_form.setContentsMargins(0, 0, 0, 0)
        self.vst2_folder = QtWidgets.QLineEdit()
        self.vst2_folder.setPlaceholderText('Automatic · standard VST2 folders')
        self.vst2_folder_btn = QtWidgets.QPushButton('Browse…')
        self.vst2_folder_btn.clicked.connect(self.choose_vst2_folder)
        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(self.vst2_folder)
        folder_row.addWidget(self.vst2_folder_btn)
        render_form.addRow('Additional VST2 folder', folder_row)
        self.native_settings = QtWidgets.QWidget()
        native_form = QtWidgets.QFormLayout(self.native_settings)
        native_form.setContentsMargins(0, 0, 0, 0)
        self.maschine_plugin = QtWidgets.QLineEdit()
        self.maschine_plugin.setPlaceholderText('Automatic · installed Maschine 3.vst3')
        plugin_row = QtWidgets.QHBoxLayout()
        plugin_row.addWidget(self.maschine_plugin)
        plugin_button = QtWidgets.QPushButton('Browse…')
        plugin_button.clicked.connect(self.choose_maschine_plugin)
        plugin_row.addWidget(plugin_button)
        native_form.addRow('Maschine VST3', plugin_row)
        self.auto_prepare = QtWidgets.QCheckBox('Automatically prepare uncached kits during export')
        self.auto_prepare.setChecked(True)
        native_form.addRow(self.auto_prepare)
        self.prepare_timeout = QtWidgets.QSpinBox()
        self.prepare_timeout.setRange(5, 900)
        self.prepare_timeout.setValue(120)
        self.prepare_timeout.setSuffix(' s')
        self.prepare_timeout.setToolTip('Maximum loading time per kit. A stalled kit is reported and the queue continues with a fresh host.')
        native_form.addRow('Kit loading timeout', self.prepare_timeout)
        prepare_row = QtWidgets.QHBoxLayout()
        self.prepare_all_btn = QtWidgets.QPushButton('Prepare indexed kits…')
        self.prepare_all_btn.clicked.connect(self.prepare_maschine_index)
        prepare_row.addWidget(self.prepare_all_btn)
        self.prepare_kit_btn = QtWidgets.QPushButton('Assisted single kit…')
        self.prepare_kit_btn.clicked.connect(self.prepare_maschine_kit)
        prepare_row.addWidget(self.prepare_kit_btn)
        native_form.addRow('', prepare_row)
        render_form.addRow(self.native_settings)
        self.render_note = QtWidgets.QSpinBox()
        self.render_note.setRange(0, 127)
        self.render_note.setToolTip('MIDI note number. 60 is middle C.')
        self.render_velocity = QtWidgets.QSpinBox()
        self.render_velocity.setRange(1, 127)
        self.render_hold = QtWidgets.QDoubleSpinBox()
        self.render_tail = QtWidgets.QDoubleSpinBox()
        for control in (self.render_hold, self.render_tail):
            control.setRange(0.05, 30)
            control.setSingleStep(0.25)
            control.setSuffix(' s')
        notes_row = QtWidgets.QHBoxLayout()
        for label, control in (('VST2 note', self.render_note), ('Velocity', self.render_velocity),
                               ('Hold', self.render_hold), ('Release', self.render_tail)):
            notes_row.addWidget(QtWidgets.QLabel(label))
            notes_row.addWidget(control)
        render_form.addRow(notes_row)
        render_layout.addRow(self.render_settings)
        for checkbox in (self.render_instruments, self.render_maschine):
            checkbox.toggled.connect(self.update_render_settings)
        self.update_render_settings()

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

        self.advanced_options = ExpandableOptions('Pad and instrument options', [render_group, matrix_group, pad_filter_group, fill_group], [self.render_instruments, self.render_maschine, self.enable_matrix, self.filter_pads, self.fill_blanks])
        self.render_options_panel = render_group
        export_form_layout.addRow(self.advanced_options)

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
        self.log_output = AnsiTextEdit(self.config.max_log_lines)
        self.log_output.setReadOnly(True)

        # Create a splitter to make the log_output resizable
        self.activity_panel = activity_panel(self)
        splitter = ResizableLogSplitter(self.config, self.tabs, self.activity_panel)
        main_layout.addWidget(splitter)

        # --- Bottom banner ---
        self.bottom_banner = BottomBanner(self.config.groups_exporter.show_terminal)
        self.bottom_banner.terminal_toggled.connect(self.toggle_terminal_visibility)
        main_layout.addWidget(self.bottom_banner)

        self.setLayout(main_layout)
        finish_layout(self, 'Maschine Groups', 'Export the samples in your Maschine groups.')
        self.set_step2_enabled(False)
        self.json_path.textChanged.connect(self.on_json_path_changed)
        self.setup_config_signals()
        # Connect enable checkboxes to update UI state
        self.enable_matrix.stateChanged.connect(self._update_matrix_editor_state)
        self.filter_pads.stateChanged.connect(self._update_pad_filter_editor_state)
        self.on_json_path_changed()  # Call once to set initial state based on json_path
        self.toggle_terminal_visibility(self.config.groups_exporter.show_terminal)

    def closeEvent(self, event):
        if self.stop_before_close(event):
            return
        # Save current window size to config
        self.config.groups_exporter.width = self.width()
        self.config.groups_exporter.height = self.height()
        config_utils.save_config(self.config)
        super().closeEvent(event)

    def toggle_terminal_visibility(self, state):
        self.activity_panel.setVisible(state)
        self.config.groups_exporter.show_terminal = state
        config_utils.save_config(self.config)


    def setup_config_signals(self):
        self.render_instruments.toggled.connect(lambda value: self.on_render_config_changed('enabled', value))
        self.render_maschine.toggled.connect(lambda value: self.on_render_config_changed('native_enabled', value))
        self.auto_prepare.toggled.connect(lambda value: self.on_render_config_changed('auto_prepare', value))
        self.prepare_timeout.valueChanged.connect(lambda value: self.on_render_config_changed('prepare_timeout', value))
        self.maschine_plugin.textChanged.connect(lambda value: self.on_render_config_changed('maschine_plugin', value))
        self.vst2_folder.textChanged.connect(lambda value: self.on_render_config_changed('plugin_folder', value))
        for widget, key in ((self.render_note, 'note'), (self.render_velocity, 'velocity'),
                            (self.render_hold, 'hold'), (self.render_tail, 'tail')):
            widget.valueChanged.connect(lambda value, key=key: self.on_render_config_changed(key, value))
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
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(lambda _, k=key, w=widget: self.on_config_changed(k, w.currentData()))
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

    def on_render_config_changed(self, key, value):
        setattr(self.config.groups_exporter.instrument_render, key, value)
        config_utils.save_config(self.config)

    def choose_vst2_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose an additional VST2 folder', self.vst2_folder.text())
        if path:
            self.vst2_folder.setText(path)

    def update_render_settings(self):
        external, native = self.render_instruments.isChecked(), self.render_maschine.isChecked()
        self.render_settings.setVisible(external or native)
        self.native_settings.setVisible(native)
        for control in (self.vst2_folder, self.vst2_folder_btn, self.render_note):
            control.setEnabled(external)

    def choose_maschine_plugin(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Choose Maschine 3 VST3', self.maschine_plugin.text(), 'VST3 (*.vst3)')
        if path:
            self.maschine_plugin.setText(path)

    def prepare_maschine_kit(self):
        from components.prepare_maschine_dialog import PrepareMaschineDialog
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Choose the original kit to prepare', self.input_folder.text(), 'Maschine Group (*.mxgrp)')
        if path:
            PrepareMaschineDialog(path, self.config.groups_exporter.instrument_render, self).exec()

    def prepare_maschine_index(self):
        from components.prepare_maschine_batch_dialog import PrepareMaschineBatchDialog
        PrepareMaschineBatchDialog(self.json_path.text().strip(), self.config.groups_exporter.instrument_render, self).exec()

    def on_matrix_config_changed(self):
        self.config.groups_exporter.matrix_config = self.matrix_editor.get_matrix()
        config_utils.save_config(self.config)

    def on_pad_filter_config_changed(self):
        self.config.groups_exporter.pad_filter_config = self.pad_filter_editor.get_pad_filter()
        config_utils.save_config(self.config)

    def normalize_path(self, path: str) -> str:
        return os.path.normpath(path) if path else path

    def load_config_to_ui(self):
        c = self.config.groups_exporter
        render = c.instrument_render.model_copy()
        self.auto_prepare.setChecked(render.auto_prepare)
        self.prepare_timeout.setValue(int(render.prepare_timeout))
        self.render_note.setValue(render.note)
        self.render_velocity.setValue(render.velocity)
        self.render_hold.setValue(render.hold)
        self.render_tail.setValue(render.tail)
        self.vst2_folder.setText(render.plugin_folder)
        self.render_instruments.setChecked(render.enabled)
        self.maschine_plugin.setText(render.maschine_plugin)
        self.render_maschine.setChecked(render.native_enabled)
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
        self.render_options_panel.setEnabled(enabled)

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

        json_path = os.path.join(output_folder, 'all_groups.json')
        self.json_path.setText(json_path)
        self.last_built_json_path = json_path
        self.run_worker(builder.run, {}, logger_name="GroupsBuilder")

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
            skip_existing=self.config.groups_exporter.skip_existing,
            render_options=self.config.groups_exporter.instrument_render,
        )
        self.log_output.append(f"Starting group export process for JSON: {json_path}")
        self.show_loading('Exporting groups...')
        self.run_worker(processor.run, {}, logger_name="GroupsProcessor")


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    app = QtWidgets.QApplication(sys.argv)
    gui = GroupsExporterGUI()
    gui.show()
    sys.exit(app.exec())
