import logging
import platform
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                             QDialogButtonBox, QFormLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QSpinBox, QVBoxLayout)

from models.config import Config
from utils.config_utils import load_config, save_config
from utils.constants import LOGS_PATH, get_data_dir
from utils.enums import Style
from utils.logger import Logger
from utils.style_utils import apply_style

logger = Logger.get_logger("ConfigurationDialog", logging.DEBUG)

class ConfigurationDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Configuration")
        self.setMinimumWidth(800)

        main_layout = QVBoxLayout()
        self.buttons = []  # Store buttons for uniform sizing

        # Paths Section
        paths_group_box = QGroupBox("Paths")
        paths_layout = QFormLayout()
        paths_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Logs Path
        logs_path_layout = QHBoxLayout()
        self.logs_path_edit = QLineEdit()
        self.logs_path_edit.setText(LOGS_PATH)
        self.logs_path_edit.setReadOnly(True)
        logs_path_layout.addWidget(self.logs_path_edit)

        open_logs_button = QPushButton("Open Logs")
        open_logs_button.clicked.connect(self.open_logs_path)
        logs_path_layout.addWidget(open_logs_button)
        self.buttons.append(open_logs_button)
        paths_layout.addRow("Logs Path:", logs_path_layout)

        # Configuration Path
        config_path_layout = QHBoxLayout()
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setText(get_data_dir())
        self.config_path_edit.setReadOnly(True)
        config_path_layout.addWidget(self.config_path_edit)

        open_config_button = QPushButton("Open Folder")
        open_config_button.clicked.connect(self.open_config_path)
        config_path_layout.addWidget(open_config_button)
        self.buttons.append(open_config_button)
        paths_layout.addRow("Config Path:", config_path_layout)
        paths_group_box.setLayout(paths_layout)
        main_layout.addWidget(paths_group_box)

        # Logging Section
        logging_group_box = QGroupBox("Logging")
        logging_layout = QFormLayout()
        logging_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Max Log Lines
        self.max_log_lines_spinbox = QSpinBox()
        self.max_log_lines_spinbox.setRange(50, 10000)
        self.max_log_lines_spinbox.setSingleStep(50)
        logging_layout.addRow("Max Log Lines:", self.max_log_lines_spinbox)
        logging_group_box.setLayout(logging_layout)
        main_layout.addWidget(logging_group_box)

        # UI Section
        ui_group_box = QGroupBox("User Interface")
        ui_layout = QFormLayout()
        ui_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # UI Style
        self.style_dropdown = QComboBox()
        self.style_dropdown.addItems([style.value for style in Style])
        ui_layout.addRow("UI Style:", self.style_dropdown)

        # Custom Color Section (reorganized into a single horizontal line)
        custom_color_widgets_layout = QHBoxLayout()

        # Enable Custom Color Checkbox (moved to the beginning)
        self.enable_custom_color_checkbox = QCheckBox("Enable Custom Primary Color")
        self.enable_custom_color_checkbox.toggled.connect(self.toggle_custom_color_widgets)
        custom_color_widgets_layout.addWidget(self.enable_custom_color_checkbox)

        custom_color_widgets_layout.addStretch()  # Spacer to push the color box and button to the right

        self.custom_color_label = QLabel()
        self.custom_color_label.setFixedSize(80, 26)
        self.custom_color_label.setAutoFillBackground(True)
        self.custom_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        custom_color_widgets_layout.addWidget(self.custom_color_label)

        self.pick_color_button = QPushButton("Pick Primary Color")
        self.pick_color_button.clicked.connect(self.pick_color)
        custom_color_widgets_layout.addWidget(self.pick_color_button)
        self.buttons.append(self.pick_color_button)

        ui_layout.addRow("Custom Colors:", custom_color_widgets_layout)
        ui_group_box.setLayout(ui_layout)
        main_layout.addWidget(ui_group_box)

        # Import/Export buttons at bottom-left
        bottom_layout = QHBoxLayout()

        self.import_button = QPushButton("Import Config")
        self.import_button.clicked.connect(self.import_config)
        bottom_layout.addWidget(self.import_button)
        self.buttons.append(self.import_button)

        self.reset_button = QPushButton("Reset Config")
        self.reset_button.clicked.connect(self.reset_config)
        bottom_layout.addWidget(self.reset_button)
        self.buttons.append(self.reset_button)

        # Spacer between left and right buttons
        bottom_layout.addStretch()

        # Ok/Cancel buttons on the right
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)  # Changed to main_layout

        # Normalize button widths
        self.equalize_button_widths()

        # Set the initial values in the fields
        self.populate_fields()

    def populate_fields(self):
        self.config = load_config()
        self.style_dropdown.setCurrentText(self.config.style.capitalize())
        self.max_log_lines_spinbox.setValue(self.config.max_log_lines)
        self.set_custom_color_display(self.config.custom_color)
        self.enable_custom_color_checkbox.setChecked(self.config.enable_custom_color)
        self.toggle_custom_color_widgets(self.config.enable_custom_color)  # Call to set initial state

    def set_custom_color_display(self, hex_color: str):
        """Sets the background color of the label and updates the internal color."""
        self.current_custom_color = hex_color
        palette = self.custom_color_label.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(hex_color))
        self.custom_color_label.setPalette(palette)
        self.custom_color_label.setText(hex_color)
        self.custom_color_label.setStyleSheet(f"background-color: {hex_color}; color: {'white' if QColor(hex_color).lightness() < 128 else 'black'};")

    def pick_color(self):
        """Opens a QColorDialog to pick a custom color."""
        initial_color = QColor(self.current_custom_color)
        color = QColorDialog.getColor(initial_color, self, "Select Custom Color")
        if color.isValid():
            self.set_custom_color_display(color.name())

    def toggle_custom_color_widgets(self, enabled: bool):
        """Enables or disables custom color related widgets and updates the color label's appearance."""
        self.custom_color_label.setEnabled(enabled)
        self.pick_color_button.setEnabled(enabled)

        if enabled:
            # If enabled, apply the actual custom color
            self.set_custom_color_display(self.current_custom_color)
        else:
            # If disabled, apply a gray stylesheet to visually indicate it's inactive
            self.custom_color_label.setStyleSheet("background-color: #E0E0E0; color: #A0A0A0;")

    def equalize_button_widths(self):
        max_width = max(button.sizeHint().width() for button in self.buttons)
        for button in self.buttons:
            button.setFixedWidth(max_width)

    def open_backups_path(self):
        self._open_path(self.path_backups_edit.text())

    def open_logs_path(self):
        self._open_path(LOGS_PATH)

    def open_config_path(self):
        self._open_path(get_data_dir())

    def _open_path(self, path):
        if not path:
            logger.warning("Path is empty.")
            return
        path = path.strip()
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path], shell=True)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                logger.error("Unsupported platform for opening file explorer.")
        except Exception as e:
            logger.error(f"Failed to open path: {path}. Error: {e}")

    def save(self):
        # Load the current config
        self.config = load_config()

        # Save the UI Style
        selected_style = self.style_dropdown.currentText()
        self.config.style = Style(selected_style)

        # Save Max Log Lines
        self.config.max_log_lines = self.max_log_lines_spinbox.value()

        # Save Custom Color
        self.config.custom_color = self.current_custom_color
        self.config.enable_custom_color = self.enable_custom_color_checkbox.isChecked()

        # Save the config
        save_config(self.config)

        # Apply the selected style
        apply_style(selected_style)

        self.accept()

    def import_config(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Import Configuration", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                imported_data = json.load(f)

            # Replace current config
            self.config.__dict__.update(imported_data)

            # Save the config
            save_config(self.config)

            # Apply the selected style
            apply_style(self.config.style)

            # Update the UI fields
            self.populate_fields()
            QMessageBox.information(self, "Import Successful", "Configuration imported.\nEncrypted fields were cleared for security.")

        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            QMessageBox.critical(self, "Import Failed", f"Failed to import configuration:\n{e}")

    def reset_config(self):
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset all configuration settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Create a new default config instance
                default_config = Config()
                save_config(default_config)
                self.config = default_config

                # Apply the default style
                apply_style(self.config.style)

                # Update the UI fields to reflect default values
                self.populate_fields()
                QMessageBox.information(self, "Reset Successful", "Configuration has been reset to default values.")
            except Exception as e:
                logger.error(f"Failed to reset config: {e}")
                QMessageBox.critical(self, "Reset Failed", f"Failed to reset configuration:\n{e}")
